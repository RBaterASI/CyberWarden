// Copyright Cyber Warden. All Rights Reserved.

#include "Misc/AutomationTest.h"
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
	TestEqual(TEXT("restored data is valid again"), Data->ValidateData().Num(), 0);
	return true;
}

#endif
