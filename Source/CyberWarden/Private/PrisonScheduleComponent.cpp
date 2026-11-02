// Copyright Cyber Warden. All Rights Reserved.

#include "PrisonScheduleComponent.h"
#include "PrisonScheduleManager.h"
#include "PrisonScheduleData.h"
#include "PrisonScheduleSelect.h"
#include "CyberWarden.h"
#include "EngineUtils.h"
#include "GameFramework/Actor.h"

UPrisonScheduleComponent::UPrisonScheduleComponent()
{
	PrimaryComponentTick.bCanEverTick = true;
	PrimaryComponentTick.bStartWithTickEnabled = true;
	PrimaryComponentTick.TickInterval = 0.05f;
}

UPrisonScheduleData* UPrisonScheduleComponent::GetData() const
{
	return ScheduleManager ? ScheduleManager->ScheduleData.Get() : nullptr;
}

void UPrisonScheduleComponent::BeginPlay()
{
	Super::BeginPlay();
	ResolveContext();
}

bool UPrisonScheduleComponent::ResolveContext()
{
	if (!ScheduleManager)
	{
		if (UWorld* World = GetWorld())
		{
			for (TActorIterator<APrisonScheduleManager> It(World); It; ++It)
			{
				ScheduleManager = *It;
				break;
			}
		}
	}
	if (!ScheduleManager)
	{
		if (!bWarnedNoManager)
		{
			bWarnedNoManager = true;
			LastDiagnostic = TEXT("no schedule manager in the world");
			UE_LOG(LogCyberWarden, Verbose, TEXT("%s: no schedule manager found; schedule component inactive"), *GetNameSafe(GetOwner()));
		}
		return false;
	}

	ResolvedNpcId = NpcIdOverride;
	if (ResolvedNpcId.IsNone() && GetOwner())
	{
		if (const FStrProperty* Prop = FindFProperty<FStrProperty>(GetOwner()->GetClass(), TEXT("NpcId")))
		{
			ResolvedNpcId = FName(*Prop->GetPropertyValue_InContainer(GetOwner()));
		}
	}
	const UPrisonScheduleData* Data = GetData();
	bHasSchedule = Data && Data->FindNpc(ResolvedNpcId) != nullptr;
	if (bHasSchedule)
	{
		StaggerGameSeconds = PrisonScheduleSelect::StaggerGameSeconds(Data->FindNpc(ResolvedNpcId)->StaggerFraction, ScheduleManager->StaggerMaxGameMinutes);
		LastDiagnostic = TEXT("ok");
	}
	else
	{
		StaggerGameSeconds = 0.0;
		LastDiagnostic = FString::Printf(TEXT("no schedule data for NPC '%s'"), *ResolvedNpcId.ToString());
	}
	RandomStream.Initialize(static_cast<int32>(GetTypeHash(ResolvedNpcId)));
	RebuildMarkerCache();
	bContextResolved = true;
	return true;
}

void UPrisonScheduleComponent::RebuildMarkerCache()
{
	MarkerCache.Reset();
	UWorld* World = GetWorld();
	if (!World)
	{
		return;
	}
	for (TActorIterator<AActor> It(World); It; ++It)
	{
		for (const FName& Tag : It->Tags)
		{
			const FString TagStr = Tag.ToString();
			if (TagStr.StartsWith(TEXT("MarkerId:")))
			{
				MarkerCache.Add(FName(*TagStr.RightChop(9)), *It);
			}
		}
	}
}

AActor* UPrisonScheduleComponent::ResolveMarker(FName MarkerId)
{
	if (TWeakObjectPtr<AActor>* Found = MarkerCache.Find(MarkerId); Found && Found->IsValid())
	{
		return Found->Get();
	}
	RebuildMarkerCache(); // the marker may have been (re)spawned since the last build
	TWeakObjectPtr<AActor>* Found = MarkerCache.Find(MarkerId);
	return (Found && Found->IsValid()) ? Found->Get() : nullptr;
}

void UPrisonScheduleComponent::RefreshContext()
{
	bContextResolved = false;
	bWarnedNoManager = false;
	ResolveContext();
}

double UPrisonScheduleComponent::GetStaggerRealSeconds() const
{
	return (ScheduleManager && ScheduleManager->TimeScale > 0.0) ? StaggerGameSeconds / ScheduleManager->TimeScale : 0.0;
}

void UPrisonScheduleComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);
	if (!bContextResolved && !ResolveContext())
	{
		return;
	}
	ManagerPeriodIndex = ScheduleManager->CurrentPeriodIndex;
	if (!bHasSchedule || AppliedPeriodIndex == INDEX_NONE)
	{
		return; // nothing to compare against until the first plan has been made
	}

	const double Now = ScheduleManager->GameSecondsTotal;
	if (ManagerPeriodIndex == AppliedPeriodIndex)
	{
		bStaggerPending = false; // changed back before the stagger elapsed: nothing to do
		return;
	}
	if (bReplanRequested)
	{
		return; // one request per change: the plan made on acknowledgement uses the latest period
	}
	if (!bStaggerPending)
	{
		bStaggerPending = true;
		PeriodChangeObservedAt = Now;
	}
	if (Now < PeriodChangeObservedAt)
	{
		PeriodChangeObservedAt = Now; // the clock was moved backwards: restart the stagger
	}
	if (Now - PeriodChangeObservedAt >= StaggerGameSeconds)
	{
		bStaggerPending = false;
		bReplanRequested = true;
		++ReplanSerial;
	}
}

void UPrisonScheduleComponent::AcknowledgeReplan()
{
	if (bReplanRequested)
	{
		++ReplanAckCount;
	}
	bReplanRequested = false;
	bStaggerPending = false;
	if (ScheduleManager)
	{
		AppliedPeriodIndex = ScheduleManager->CurrentPeriodIndex;
		AppliedPeriodName = ScheduleManager->CurrentPeriodName;
	}
}

FPrisonDestination UPrisonScheduleComponent::PlanForCurrentPeriod()
{
	FPrisonDestination Out;
	if (!bContextResolved && !ResolveContext())
	{
		Out.Reason = LastDiagnostic = TEXT("no schedule manager");
		return Out;
	}
	AcknowledgeReplan();
	++PlanCount;
	ManagerPeriodIndex = ScheduleManager->CurrentPeriodIndex;
	Out.PeriodIndex = AppliedPeriodIndex;

	const UPrisonScheduleData* Data = GetData();
	if (!Data)
	{
		Out.Reason = LastDiagnostic = TEXT("schedule manager has no schedule data");
		return Out;
	}
	if (!ScheduleManager->PeriodIds.IsValidIndex(AppliedPeriodIndex))
	{
		Out.Reason = LastDiagnostic = TEXT("current period index has no id");
		return Out;
	}
	const FName PeriodId = ScheduleManager->PeriodIds[AppliedPeriodIndex];
	const FPrisonPeriodAssignment* Assignment = Data->FindAssignment(ResolvedNpcId, PeriodId);
	FPrisonStopChoice Choice = PrisonScheduleSelect::Choose(Assignment, CurrentStopMarkerId, RandomStream);
	if (!Choice.bValid)
	{
		Out.Reason = LastDiagnostic = FString::Printf(TEXT("%s/%s: %s"), *ResolvedNpcId.ToString(), *PeriodId.ToString(), *Choice.Reason);
		return Out;
	}
	AActor* Marker = ResolveMarker(Choice.MarkerId);
	if (!Marker)
	{
		Out.Reason = LastDiagnostic = FString::Printf(TEXT("%s/%s: marker %s not found in the level"), *ResolvedNpcId.ToString(), *PeriodId.ToString(), *Choice.MarkerId.ToString());
		return Out;
	}

	bool bMoveRequired = true;
	if (const AActor* Owner = GetOwner())
	{
		bMoveRequired = FVector::Dist2D(Owner->GetActorLocation(), Marker->GetActorLocation()) > ArrivalRadius;
	}
	CurrentStopMarkerId = Choice.MarkerId;
	CurrentIdleSeconds = Choice.IdleSeconds;
	Out.bValid = true;
	Out.MarkerId = Choice.MarkerId;
	Out.Marker = Marker;
	Out.IdleSeconds = Choice.IdleSeconds;
	Out.bMoveRequired = bMoveRequired;
	Out.bSingleStop = Choice.bSingleStop;
	Out.Reason = LastDiagnostic = FString::Printf(TEXT("%s/%s -> %s idle %.1fs%s"), *ResolvedNpcId.ToString(), *PeriodId.ToString(),
		*Choice.MarkerId.ToString(), Choice.IdleSeconds, bMoveRequired ? TEXT("") : TEXT(" (already there)"));
	return Out;
}

TArray<FString> UPrisonScheduleComponent::ValidateAssignments()
{
	TArray<FString> Errors;
	if (!bContextResolved && !ResolveContext())
	{
		Errors.Add(TEXT("no schedule manager"));
		return Errors;
	}
	const UPrisonScheduleData* Data = GetData();
	const FPrisonNpcSchedule* Npc = Data ? Data->FindNpc(ResolvedNpcId) : nullptr;
	if (!Npc)
	{
		Errors.Add(FString::Printf(TEXT("no schedule data for NPC '%s'"), *ResolvedNpcId.ToString()));
		return Errors;
	}
	for (const FPrisonPeriodAssignment& A : Npc->Periods)
	{
		if (A.StopMarkerIds.Num() == 0)
		{
			Errors.Add(FString::Printf(TEXT("%s/%s: no stops"), *ResolvedNpcId.ToString(), *A.PeriodId.ToString()));
		}
		for (const FName& Id : A.StopMarkerIds)
		{
			const AActor* Marker = ResolveMarker(Id);
			if (!Marker)
			{
				Errors.Add(FString::Printf(TEXT("%s/%s: marker %s not found"), *ResolvedNpcId.ToString(), *A.PeriodId.ToString(), *Id.ToString()));
			}
			else if (!Marker->Tags.Contains(FName(TEXT("NavDest:Yes"))))
			{
				Errors.Add(FString::Printf(TEXT("%s/%s: marker %s is not NavDest:Yes"), *ResolvedNpcId.ToString(), *A.PeriodId.ToString(), *Id.ToString()));
			}
		}
	}
	return Errors;
}
