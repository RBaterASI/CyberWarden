// Copyright Cyber Warden. All Rights Reserved.

#include "Misc/AutomationTest.h"
#include "PrisonScheduleData.h"
#include "PrisonScheduleSelect.h"

#if WITH_DEV_AUTOMATION_TESTS && !defined(CW_EXCLUDE_AUTOMATION_TESTS)

namespace
{
	FPrisonPeriodAssignment MakeAssignment(std::initializer_list<const TCHAR*> Stops, double Min, double Max)
	{
		FPrisonPeriodAssignment A;
		A.PeriodId = TEXT("work");
		for (const TCHAR* S : Stops)
		{
			A.StopMarkerIds.Add(FName(S));
		}
		A.IdleMin = Min;
		A.IdleMax = Max;
		return A;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FPrisonScheduleSelectTest, "CyberWarden.Prison.ScheduleSelect",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::ProductFilter)

bool FPrisonScheduleSelectTest::RunTest(const FString& Parameters)
{
	FRandomStream Stream(1234);

	// Empty or missing assignments fail safely.
	TestFalse(TEXT("null assignment is invalid"), PrisonScheduleSelect::Choose(nullptr, NAME_None, Stream).bValid);
	const FPrisonPeriodAssignment Empty = MakeAssignment({}, 5.0, 10.0);
	const FPrisonStopChoice EmptyChoice = PrisonScheduleSelect::Choose(&Empty, NAME_None, Stream);
	TestFalse(TEXT("empty stop list is invalid"), EmptyChoice.bValid);
	TestTrue(TEXT("empty stop list explains why"), !EmptyChoice.Reason.IsEmpty());
	FPrisonPeriodAssignment OnlyNone;
	OnlyNone.StopMarkerIds.Add(NAME_None);
	TestFalse(TEXT("a list of only None is invalid"), PrisonScheduleSelect::Choose(&OnlyNone, NAME_None, Stream).bValid);

	// A single destination is returned every time and flagged, even when it is the previous one.
	const FPrisonPeriodAssignment Single = MakeAssignment({ TEXT("Seat_Table_2_1") }, 40.0, 70.0);
	for (int32 i = 0; i < 20; ++i)
	{
		const FPrisonStopChoice C = PrisonScheduleSelect::Choose(&Single, FName(TEXT("Seat_Table_2_1")), Stream);
		TestTrue(TEXT("single stop valid"), C.bValid);
		TestTrue(TEXT("single stop flagged"), C.bSingleStop);
		TestEqual(TEXT("single stop id"), C.MarkerId, FName(TEXT("Seat_Table_2_1")));
		TestTrue(TEXT("idle within range"), C.IdleSeconds >= 40.0 && C.IdleSeconds <= 70.0);
	}

	// With several stops the previous stop is never repeated, and all stops are used.
	const FPrisonPeriodAssignment Multi = MakeAssignment({ TEXT("A"), TEXT("B"), TEXT("C") }, 4.0, 10.0);
	FName Previous = TEXT("A");
	TSet<FName> Seen;
	bool bRepeated = false;
	for (int32 i = 0; i < 300; ++i)
	{
		const FPrisonStopChoice C = PrisonScheduleSelect::Choose(&Multi, Previous, Stream);
		bRepeated |= (C.MarkerId == Previous);
		Seen.Add(C.MarkerId);
		Previous = C.MarkerId;
		TestFalse(TEXT("multi-stop is not flagged single"), C.bSingleStop);
	}
	TestFalse(TEXT("previous stop is never repeated"), bRepeated);
	TestEqual(TEXT("all stops get used"), Seen.Num(), 3);

	// Same seed -> same sequence (deterministic); reversed idle range is repaired.
	FRandomStream S1(77), S2(77);
	for (int32 i = 0; i < 20; ++i)
	{
		TestEqual(TEXT("deterministic choice"), PrisonScheduleSelect::Choose(&Multi, NAME_None, S1).MarkerId, PrisonScheduleSelect::Choose(&Multi, NAME_None, S2).MarkerId);
	}
	const FPrisonPeriodAssignment Reversed = MakeAssignment({ TEXT("A") }, 9.0, 3.0);
	const FPrisonStopChoice R = PrisonScheduleSelect::Choose(&Reversed, NAME_None, Stream);
	TestTrue(TEXT("reversed idle range is swapped"), R.IdleSeconds >= 3.0 && R.IdleSeconds <= 9.0);

	// Stagger: fraction x 5 game minutes (default) in game seconds, clamped.
	TestEqual(TEXT("stagger 0.2 x 5 min = 60 s"), PrisonScheduleSelect::StaggerGameSeconds(0.2, 5.0), 60.0);
	TestEqual(TEXT("stagger 0.8 x 5 min = 240 s"), PrisonScheduleSelect::StaggerGameSeconds(0.8, 5.0), 240.0);
	TestEqual(TEXT("stagger 0 = 0 s"), PrisonScheduleSelect::StaggerGameSeconds(0.0, 5.0), 0.0);
	TestEqual(TEXT("stagger 0.5 x 5 min = 150 s"), PrisonScheduleSelect::StaggerGameSeconds(0.5, 5.0), 150.0);
	TestEqual(TEXT("backoff 0 = 0 s"), PrisonScheduleSelect::RetryBackoffSeconds(0), 0.0);
	TestEqual(TEXT("backoff 1 = 2 s"), PrisonScheduleSelect::RetryBackoffSeconds(1), 2.0);
	TestEqual(TEXT("backoff 2 = 4 s"), PrisonScheduleSelect::RetryBackoffSeconds(2), 4.0);
	TestEqual(TEXT("backoff 4 = 16 s"), PrisonScheduleSelect::RetryBackoffSeconds(4), 16.0);
	TestEqual(TEXT("backoff is capped at 30 s"), PrisonScheduleSelect::RetryBackoffSeconds(50), 30.0);
	TestEqual(TEXT("fraction above 1 is clamped"), PrisonScheduleSelect::StaggerGameSeconds(3.0, 5.0), 300.0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FPrisonScheduleDataTest, "CyberWarden.Prison.ScheduleData",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::ProductFilter)

bool FPrisonScheduleDataTest::RunTest(const FString& Parameters)
{
	UPrisonScheduleData* Data = NewObject<UPrisonScheduleData>(GetTransientPackage());
	Data->Periods = { { TEXT("wake"), TEXT("Wake-up"), 6.0 }, { TEXT("lockdown"), TEXT("Lockdown"), 21.0 } };
	FPrisonNpcSchedule N;
	N.NpcId = TEXT("EXP01");
	N.StaggerFraction = 0.2;
	N.Periods.Add(MakeAssignment({ TEXT("A") }, 4.0, 8.0));
	N.Periods.Last().PeriodId = TEXT("wake");
	N.Periods.Add(MakeAssignment({ TEXT("B") }, 4.0, 8.0));
	N.Periods.Last().PeriodId = TEXT("lockdown");
	Data->Npcs.Add(N);

	TestEqual(TEXT("valid data has no errors"), Data->ValidateData().Num(), 0);
	TestNotNull(TEXT("FindNpc"), Data->FindNpc(TEXT("EXP01")));
	TestNull(TEXT("FindNpc unknown"), Data->FindNpc(TEXT("NOPE")));
	TestNotNull(TEXT("FindAssignment"), Data->FindAssignment(TEXT("EXP01"), TEXT("lockdown")));

	Data->Npcs[0].Periods[1].StopMarkerIds.Reset();
	TestTrue(TEXT("empty stop list is reported"), Data->ValidateData().Num() > 0);
	Data->Npcs[0].Periods[1].StopMarkerIds.Add(TEXT("B"));
	Data->Npcs[0].Periods.RemoveAt(0);
	TestTrue(TEXT("missing period assignment is reported"), Data->ValidateData().Num() > 0);
	Data->Npcs[0].Periods.Insert(MakeAssignment({ TEXT("A") }, 4.0, 8.0), 0);
	Data->Npcs[0].Periods[0].PeriodId = TEXT("wake");
	TestEqual(TEXT("restored data is valid again"), Data->ValidateData().Num(), 0);
	Data->Npcs[0].StaggerFraction = 1.5;
	TestTrue(TEXT("bad stagger fraction is reported"), Data->ValidateData().Num() > 0);
	Data->Npcs[0].StaggerFraction = 0.2;
	Data->Periods[1].StartHours = 5.0;
	TestTrue(TEXT("non-ascending periods are reported"), Data->ValidateData().Num() > 0);
	return true;
}

#endif
