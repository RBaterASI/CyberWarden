// Copyright Cyber Warden. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"

/**
 * Pure clock / schedule lookup math (no UObject dependencies) so it can be unit tested.
 * The schedule is a 48-slot (half-hour) lookup table. Slots before the first period start belong to the LAST period,
 * which gives the overnight wrap (Lockdown 21:00 -> 06:00).
 */
namespace PrisonClockMath
{
	constexpr double SecondsPerDay = 86400.0;
	constexpr double SlotSeconds = 1800.0;
	constexpr int32 SlotCount = 48;

	/** Wrap accumulated game seconds into 0..86400 (negative totals wrap forward). */
	CYBERWARDEN_API double WrapSeconds(double TotalSeconds);

	/** Half-hour slot (0..47) containing the given wrapped or unwrapped game seconds. */
	CYBERWARDEN_API int32 SlotOf(double TotalSeconds);

	/** Builds the 48-slot table from ascending period start hours. Returns an empty array if the input is invalid. */
	CYBERWARDEN_API TArray<int32> BuildSlotTable(const TArray<double>& PeriodStartHours);

	/** Period index active at the given game seconds, or INDEX_NONE if the table is not built. */
	CYBERWARDEN_API int32 PeriodAt(const TArray<int32>& SlotTable, double TotalSeconds);

	/** "HH:MM:SS" for game seconds (wrapped to one day). */
	CYBERWARDEN_API FString FormatClock(double TotalSeconds);
}
