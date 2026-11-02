// Copyright Cyber Warden. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Math/RandomStream.h"
#include "PrisonScheduleData.h"

/** Result of choosing a stop from an assignment (pure logic, unit-tested without a world). */
struct CYBERWARDEN_API FPrisonStopChoice
{
	bool bValid = false;
	int32 Index = INDEX_NONE;
	FName MarkerId;
	double IdleSeconds = 0.0;
	bool bSingleStop = false;
	FString Reason;
};

namespace PrisonScheduleSelect
{
	/**
	 * Picks a stop for one period. A null or empty assignment is a safe failure (bValid = false, with a reason).
	 * With several stops the previously used stop is avoided; with a single stop it is returned with bSingleStop set.
	 * The idle time is drawn from [IdleMin, IdleMax] (swapped if reversed).
	 */
	CYBERWARDEN_API FPrisonStopChoice Choose(const FPrisonPeriodAssignment* Assignment, FName PreviousMarkerId, FRandomStream& Stream);

	/** Real seconds to wait before retrying a movement that keeps being re-planned: 0, 2, 4, 8, 16, capped at 30. */
	CYBERWARDEN_API double RetryBackoffSeconds(int32 RetryStreak);

	/** Departure stagger in game seconds for a fraction (0..1, clamped) of the manager's maximum in game minutes. */
	CYBERWARDEN_API double StaggerGameSeconds(double Fraction, double MaxGameMinutes);
}
