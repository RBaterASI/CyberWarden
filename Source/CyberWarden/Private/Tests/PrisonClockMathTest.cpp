// Copyright Cyber Warden. All Rights Reserved.

#include "Misc/AutomationTest.h"
#include "PrisonClockMath.h"

#if WITH_DEV_AUTOMATION_TESTS && !defined(CW_EXCLUDE_AUTOMATION_TESTS)

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FPrisonClockMathTest, "CyberWarden.Prison.ClockMath",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::ClientContext | EAutomationTestFlags::ProductFilter)

bool FPrisonClockMathTest::RunTest(const FString& Parameters)
{
	const TArray<double> Starts = { 6.0, 7.0, 8.0, 12.0, 13.0, 18.0, 19.0, 21.0 };
	const TArray<int32> Table = PrisonClockMath::BuildSlotTable(Starts);
	TestEqual(TEXT("table has 48 slots"), Table.Num(), 48);
	const int32 Wake = 0;
	const int32 Free = 6;
	const int32 Lockdown = 7;
	auto At = [&Table](double H, double M = 0.0, double S = 0.0)
	{
		return PrisonClockMath::PeriodAt(Table, H * 3600.0 + M * 60.0 + S);
	};
	TestEqual(TEXT("06:00 wake-up"), At(6), Wake);
	TestEqual(TEXT("05:59:59 lockdown (overnight carry)"), At(5, 59, 59), Lockdown);
	TestEqual(TEXT("00:00 lockdown (midnight wrap)"), At(0), Lockdown);
	TestEqual(TEXT("23:59:59 lockdown"), At(23, 59, 59), Lockdown);
	TestEqual(TEXT("86400 s wraps to lockdown"), PrisonClockMath::PeriodAt(Table, PrisonClockMath::SecondsPerDay), Lockdown);
	TestEqual(TEXT("20:59:59 free time"), At(20, 59, 59), Free);
	TestEqual(TEXT("21:00 lockdown"), At(21), Lockdown);
	TestEqual(TEXT("second day 06:00 (unwrapped total) wake-up"), PrisonClockMath::PeriodAt(Table, PrisonClockMath::SecondsPerDay + 6.0 * 3600.0), Wake);
	for (int32 i = 0; i < Starts.Num(); ++i)
	{
		TestEqual(*FString::Printf(TEXT("boundary %d start"), i), PrisonClockMath::PeriodAt(Table, Starts[i] * 3600.0), i);
		TestNotEqual(*FString::Printf(TEXT("boundary %d one second before"), i), PrisonClockMath::PeriodAt(Table, Starts[i] * 3600.0 - 1.0), i);
	}
	TestEqual(TEXT("negative total wraps"), PrisonClockMath::WrapSeconds(-60.0), PrisonClockMath::SecondsPerDay - 60.0);
	TestEqual(TEXT("format"), PrisonClockMath::FormatClock(21600.0 + 61.0), FString(TEXT("06:01:01")));
	TestEqual(TEXT("off-grid start rejected"), PrisonClockMath::BuildSlotTable({ 6.0, 7.25 }).Num(), 0);
	TestEqual(TEXT("descending rejected"), PrisonClockMath::BuildSlotTable({ 8.0, 7.0 }).Num(), 0);
	return true;
}

#endif
