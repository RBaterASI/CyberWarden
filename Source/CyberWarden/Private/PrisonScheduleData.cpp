// Copyright Cyber Warden. All Rights Reserved.

#include "PrisonScheduleData.h"
#include "PrisonClockMath.h"

const FPrisonNpcSchedule* UPrisonScheduleData::FindNpc(FName NpcId) const
{
	return Npcs.FindByPredicate([NpcId](const FPrisonNpcSchedule& N) { return N.NpcId == NpcId; });
}

const FPrisonPeriodAssignment* UPrisonScheduleData::FindAssignment(FName NpcId, FName PeriodId) const
{
	const FPrisonNpcSchedule* Npc = FindNpc(NpcId);
	return Npc ? Npc->Periods.FindByPredicate([PeriodId](const FPrisonPeriodAssignment& A) { return A.PeriodId == PeriodId; }) : nullptr;
}

bool UPrisonScheduleData::Validate(TArray<FString>& OutErrors) const
{
	const int32 StartErrors = OutErrors.Num();

	TArray<double> Starts;
	TSet<FName> PeriodIds;
	for (const FPrisonPeriodDef& P : Periods)
	{
		if (P.Id.IsNone())
		{
			OutErrors.Add(TEXT("period with no id"));
		}
		else if (PeriodIds.Contains(P.Id))
		{
			OutErrors.Add(FString::Printf(TEXT("duplicate period id %s"), *P.Id.ToString()));
		}
		PeriodIds.Add(P.Id);
		Starts.Add(P.StartHours);
	}
	if (Periods.Num() < 2)
	{
		OutErrors.Add(TEXT("at least two periods are required"));
	}
	else if (PrisonClockMath::BuildSlotTable(Starts).Num() == 0)
	{
		OutErrors.Add(TEXT("period start hours must ascend on the half-hour grid within 0..24"));
	}

	TSet<FName> NpcIds;
	for (const FPrisonNpcSchedule& N : Npcs)
	{
		if (N.NpcId.IsNone() || NpcIds.Contains(N.NpcId))
		{
			OutErrors.Add(FString::Printf(TEXT("missing or duplicate NPC id '%s'"), *N.NpcId.ToString()));
		}
		NpcIds.Add(N.NpcId);
		if (N.StaggerFraction < 0.0 || N.StaggerFraction > 1.0)
		{
			OutErrors.Add(FString::Printf(TEXT("%s: stagger fraction must be 0..1"), *N.NpcId.ToString()));
		}
		for (const FPrisonPeriodDef& P : Periods)
		{
			const FPrisonPeriodAssignment* A = N.Periods.FindByPredicate([&P](const FPrisonPeriodAssignment& X) { return X.PeriodId == P.Id; });
			if (!A)
			{
				OutErrors.Add(FString::Printf(TEXT("%s: no assignment for period %s"), *N.NpcId.ToString(), *P.Id.ToString()));
				continue;
			}
			if (A->StopMarkerIds.Num() == 0)
			{
				OutErrors.Add(FString::Printf(TEXT("%s/%s: no stops"), *N.NpcId.ToString(), *P.Id.ToString()));
			}
			if (!(A->IdleMin > 0.0 && A->IdleMin <= A->IdleMax))
			{
				OutErrors.Add(FString::Printf(TEXT("%s/%s: idle range must satisfy 0 < min <= max"), *N.NpcId.ToString(), *P.Id.ToString()));
			}
		}
		for (const FPrisonPeriodAssignment& A : N.Periods)
		{
			if (!PeriodIds.Contains(A.PeriodId))
			{
				OutErrors.Add(FString::Printf(TEXT("%s: assignment for unknown period %s"), *N.NpcId.ToString(), *A.PeriodId.ToString()));
			}
		}
	}
	return OutErrors.Num() == StartErrors;
}

TArray<FString> UPrisonScheduleData::ValidateData() const
{
	TArray<FString> Errors;
	Validate(Errors);
	return Errors;
}
