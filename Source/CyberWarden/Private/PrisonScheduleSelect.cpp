// Copyright Cyber Warden. All Rights Reserved.

#include "PrisonScheduleSelect.h"

namespace PrisonScheduleSelect
{
	FPrisonStopChoice Choose(const FPrisonPeriodAssignment* Assignment, FName PreviousMarkerId, FRandomStream& Stream)
	{
		FPrisonStopChoice Out;
		if (!Assignment)
		{
			Out.Reason = TEXT("no assignment for this period");
			return Out;
		}
		TArray<int32> Candidates;
		for (int32 i = 0; i < Assignment->StopMarkerIds.Num(); ++i)
		{
			if (!Assignment->StopMarkerIds[i].IsNone())
			{
				Candidates.Add(i);
			}
		}
		if (Candidates.Num() == 0)
		{
			Out.Reason = TEXT("assignment has no stops");
			return Out;
		}
		Out.bSingleStop = Candidates.Num() == 1;
		if (Candidates.Num() > 1)
		{
			TArray<int32> Others = Candidates.FilterByPredicate([&](int32 i) { return Assignment->StopMarkerIds[i] != PreviousMarkerId; });
			if (Others.Num() > 0)
			{
				Candidates = Others;
			}
		}
		Out.Index = Candidates[Candidates.Num() == 1 ? 0 : Stream.RandRange(0, Candidates.Num() - 1)];
		Out.MarkerId = Assignment->StopMarkerIds[Out.Index];
		const double Lo = FMath::Min(Assignment->IdleMin, Assignment->IdleMax);
		const double Hi = FMath::Max(Assignment->IdleMin, Assignment->IdleMax);
		Out.IdleSeconds = FMath::Max(0.1, Lo + (Hi - Lo) * static_cast<double>(Stream.FRand()));
		Out.bValid = true;
		return Out;
	}

	double StaggerGameSeconds(double Fraction, double MaxGameMinutes)
	{
		return FMath::Clamp(Fraction, 0.0, 1.0) * FMath::Max(0.0, MaxGameMinutes) * 60.0;
	}
}
