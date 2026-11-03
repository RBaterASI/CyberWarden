// Copyright Cyber Warden. All Rights Reserved.

#include "Misc/AutomationTest.h"
#include "Animation/AnimSequence.h"
#include "PrisonActivityData.h"
#include "PrisonActivityMath.h"

#if WITH_DEV_AUTOMATION_TESTS && !defined(CW_EXCLUDE_AUTOMATION_TESTS)

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FPrisonActivityMathTest, "CyberWarden.Prison.ActivityMath",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::ProductFilter)

bool FPrisonActivityMathTest::RunTest(const FString& Parameters)
{
	using namespace PrisonActivityMath;
	TestEqual(TEXT("normalize 190 -> -170"), NormalizeYaw(190.0), -170.0);
	TestEqual(TEXT("normalize -190 -> 170"), NormalizeYaw(-190.0), 170.0);
	TestEqual(TEXT("normalize 180 stays 180"), NormalizeYaw(180.0), 180.0);
	TestEqual(TEXT("normalize -180 -> 180"), NormalizeYaw(-180.0), 180.0);
	TestEqual(TEXT("normalize 720 -> 0"), NormalizeYaw(720.0), 0.0);
	TestEqual(TEXT("delta takes the short way across +-180"), DeltaYaw(170.0, -170.0), 20.0);
	TestEqual(TEXT("delta the other way"), DeltaYaw(-170.0, 170.0), -20.0);
	TestEqual(TEXT("yaw to +X is 0"), YawToPoint(0, 0, 100, 0), 0.0);
	TestEqual(TEXT("yaw to +Y is 90"), YawToPoint(0, 0, 0, 100), 90.0);
	TestEqual(TEXT("yaw to -X is 180"), YawToPoint(0, 0, -100, 0), 180.0);
	TestEqual(TEXT("yaw to -Y is -90"), YawToPoint(0, 0, 0, -100), -90.0);
	TestEqual(TEXT("coincident points give 0"), YawToPoint(5, 5, 5, 5), 0.0);
	// Rec_TV: an NPC at (3935, 3150) faces the TV centre (4000, 3365): mostly +Y
	TestTrue(TEXT("Rec_TV bearing is close to north"), FMath::Abs(YawToPoint(3935, 3150, 4000, 3365) - 73.2) < 0.5);

	// Constant-rate stepping never overshoots and converges.
	double Yaw = 170.0;
	const double Target = -170.0; // 20 degrees away across the wrap
	double Previous = FMath::Abs(DeltaYaw(Yaw, Target));
	bool bMonotonic = true;
	bool bNoOvershoot = true;
	for (int32 i = 0; i < 20; ++i)
	{
		Yaw = StepYaw(Yaw, Target, 7.0);
		const double Err = FMath::Abs(DeltaYaw(Yaw, Target));
		bMonotonic &= (Err <= Previous + KINDA_SMALL_NUMBER);
		bNoOvershoot &= (Err <= Previous);
		Previous = Err;
	}
	TestTrue(TEXT("step is monotonic and never overshoots"), bMonotonic && bNoOvershoot);
	TestEqual(TEXT("step converges exactly"), Previous, 0.0);
	TestEqual(TEXT("one step moves at most the allowed amount"), StepYaw(0.0, 90.0, 5.0), 5.0);
	TestEqual(TEXT("one step across the wrap"), StepYaw(179.0, -179.0, 1.0), 180.0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FPrisonActivityTimingTest, "CyberWarden.Prison.ActivityTiming",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::ProductFilter)

bool FPrisonActivityTimingTest::RunTest(const FString& Parameters)
{
	using namespace PrisonActivityMath;
	TestEqual(TEXT("a set blend wins"), ResolveBlend(0.25f, 0.4f), 0.25f);
	TestEqual(TEXT("zero is a real value, not 'inherit'"), ResolveBlend(0.f, 0.4f), 0.f);
	TestEqual(TEXT("negative inherits"), ResolveBlend(-1.f, 0.4f), 0.4f);

	TestEqual(TEXT("remaining time at rate 1"), RemainingPlaySeconds(2.233, 1.0, 1.0), 1.233);
	TestEqual(TEXT("remaining time at double speed is halved"), RemainingPlaySeconds(2.0, 0.0, 2.0), 1.0);
	TestEqual(TEXT("remaining time never negative"), RemainingPlaySeconds(2.0, 2.5, 1.0), 0.0);
	TestEqual(TEXT("a zero play rate is clamped, not divided by"), RemainingPlaySeconds(1.0, 0.0, 0.0), 100.0);

	TestFalse(TEXT("hand-off not due with 1 s left and a 0.25 s cross-fade"), HandoffDue(1.0, 0.25));
	TestTrue(TEXT("hand-off due exactly one cross-fade before the end"), HandoffDue(0.25, 0.25));
	TestTrue(TEXT("hand-off due when already late"), HandoffDue(0.1, 0.25));
	TestTrue(TEXT("a zero cross-fade hands off at the end"), HandoffDue(0.0, 0.0));
	TestFalse(TEXT("a zero cross-fade does not hand off early"), HandoffDue(0.05, 0.0));

	TestFalse(TEXT("exit not complete before the planned end, even if the animation says so"), ExitComplete(1.0, 2.0, true, 1.0));
	TestFalse(TEXT("exit not complete at the planned end while the animation still plays"), ExitComplete(2.0, 2.0, false, 1.0));
	TestTrue(TEXT("exit complete at the planned end once the animation finished"), ExitComplete(2.0, 2.0, true, 1.0));
	TestFalse(TEXT("still waiting inside the safety margin"), ExitComplete(2.9, 2.0, false, 1.0));
	TestTrue(TEXT("a stuck animation frees the NPC after the safety margin"), ExitComplete(3.0, 2.0, false, 1.0));

	FPrisonActivityDefinition Def;
	Def.BlendInSeconds = 0.3f;
	Def.BlendOutSeconds = 0.2f;
	TestEqual(TEXT("default definition inherits blend in (enter)"), Def.GetEnterBlendIn(), 0.3f);
	TestEqual(TEXT("default definition inherits blend in (loop)"), Def.GetLoopBlendIn(), 0.3f);
	TestEqual(TEXT("default definition inherits blend in (exit)"), Def.GetExitBlendIn(), 0.3f);
	TestEqual(TEXT("default definition inherits blend out (exit)"), Def.GetExitBlendOut(), 0.2f);
	TestFalse(TEXT("enter is not committed by default"), Def.bCommitEnter);
	TestTrue(TEXT("release grace is inherited by default"), Def.ReleaseGraceSeconds < 0.f);
	Def.EnterBlendInSeconds = 0.4f;
	Def.LoopBlendInSeconds = 0.25f;
	Def.ExitBlendInSeconds = 0.35f;
	Def.ExitBlendOutSeconds = 0.5f;
	TestEqual(TEXT("explicit enter blend"), Def.GetEnterBlendIn(), 0.4f);
	TestEqual(TEXT("explicit loop blend"), Def.GetLoopBlendIn(), 0.25f);
	TestEqual(TEXT("explicit exit blend in"), Def.GetExitBlendIn(), 0.35f);
	TestEqual(TEXT("explicit exit blend out"), Def.GetExitBlendOut(), 0.5f);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FPrisonActivityDataTest, "CyberWarden.Prison.ActivityData",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::ProductFilter)

bool FPrisonActivityDataTest::RunTest(const FString& Parameters)
{
	UPrisonActivityData* Data = NewObject<UPrisonActivityData>(GetTransientPackage());
	FPrisonActivityDefinition Watch;
	Watch.Id = TEXT("WatchTV");
	Data->Activities.Add(Watch);
	FPrisonInteractionPoint Point;
	Point.MarkerId = TEXT("Rec_TV");
	Point.ActivityId = TEXT("WatchTV");
	Point.FacingMode = EPrisonFacingMode::Point;
	Point.FacingPoint = FVector(4000, 3365, 0);
	Data->Points.Add(Point);

	TestEqual(TEXT("valid data has no errors"), Data->ValidateData().Num(), 0);
	TestNotNull(TEXT("FindActivity"), Data->FindActivity(TEXT("WatchTV")));
	TestNull(TEXT("FindActivity unknown"), Data->FindActivity(TEXT("Nope")));
	TestNotNull(TEXT("FindPoint"), Data->FindPoint(TEXT("Rec_TV")));
	TestNull(TEXT("FindPoint unknown"), Data->FindPoint(TEXT("Nope")));

	Data->Points[0].ActivityId = TEXT("Missing");
	TestTrue(TEXT("unknown activity is reported"), Data->ValidateData().Num() > 0);
	Data->Points[0].ActivityId = TEXT("WatchTV");
	Data->Points[0].ArrivalToleranceCm = 0.f;
	TestTrue(TEXT("zero tolerance is reported"), Data->ValidateData().Num() > 0);
	Data->Points[0].ArrivalToleranceCm = 150.f;
	Data->Points[0].Capacity = 0;
	TestTrue(TEXT("zero capacity is reported"), Data->ValidateData().Num() > 0);
	Data->Points[0].Capacity = 1;
	const FPrisonInteractionPoint PointCopy = Data->Points[0]; // copy first: adding an element of the array to itself is an engine assertion
	Data->Points.Add(PointCopy);
	TestTrue(TEXT("duplicate point is reported"), Data->ValidateData().Num() > 0);
	Data->Points.RemoveAt(1);
	Data->Activities.Add(Watch);
	TestTrue(TEXT("duplicate activity is reported"), Data->ValidateData().Num() > 0);
	Data->Activities.RemoveAt(1);
	Data->Activities[0].AlignYawRateDegPerSec = 0.f;
	TestTrue(TEXT("zero align rate is reported"), Data->ValidateData().Num() > 0);
	Data->Activities[0].AlignYawRateDegPerSec = 120.f;
	Data->Activities[0].SlotName = NAME_None;
	TestTrue(TEXT("missing slot is reported"), Data->ValidateData().Num() > 0);
	Data->Activities[0].SlotName = TEXT("DefaultSlot");
	Data->Activities[0].bCommitEnter = true;
	TestTrue(TEXT("commit enter without an enter animation is reported"), Data->ValidateData().Num() > 0);
	Data->Activities[0].EnterAnimation = TSoftObjectPtr<UAnimSequence>(FSoftObjectPath(TEXT("/Game/Test/Enter.Enter")));
	TestEqual(TEXT("commit enter with an enter animation is valid"), Data->ValidateData().Num(), 0);
	Data->Activities[0].bCommitEnter = false;
	Data->Activities[0].EnterAnimation.Reset();
	TestEqual(TEXT("restored data is valid again"), Data->ValidateData().Num(), 0);
	return true;
}

#endif
