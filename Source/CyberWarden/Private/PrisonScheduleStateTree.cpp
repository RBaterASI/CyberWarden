// Copyright Cyber Warden. All Rights Reserved.

#include "PrisonScheduleStateTree.h"
#include "PrisonScheduleComponent.h"
#include "PrisonActivityComponent.h"
#include "CyberWarden.h"
#include "StateTreeExecutionContext.h"
#include "GameFramework/Actor.h"

FPrisonPlanDestinationTask::FPrisonPlanDestinationTask()
{
	// Runs once on entering the root state and keeps running: the state ends only through transitions.
	bShouldCallTick = false;
	bShouldStateChangeOnReselect = true;
#if WITH_EDITORONLY_DATA
	bConsideredForCompletion = false;
	bCanEditConsideredForCompletion = false;
#endif
}

EStateTreeRunStatus FPrisonPlanDestinationTask::EnterState(FStateTreeExecutionContext& Context, const FStateTreeTransitionResult& Transition) const
{
	FInstanceDataType& Data = Context.GetInstanceData(*this);
	Data.TargetActor = nullptr;
	Data.bMoveRequired = false;
	Data.bPlanValid = false;
	Data.StartDelaySeconds = 0.f;
	Data.IdleSeconds = 5.f;
	Data.MarkerId = NAME_None;
	Data.PeriodIndex = INDEX_NONE;

	UPrisonScheduleComponent* Schedule = Data.Actor ? Data.Actor->FindComponentByClass<UPrisonScheduleComponent>() : nullptr;
	if (!Schedule)
	{
		UE_LOG(LogCyberWarden, Warning, TEXT("Prison: Plan Destination: %s has no PrisonScheduleComponent"), *GetNameSafe(Data.Actor));
		return EStateTreeRunStatus::Running; // invalid plan: the routine falls through to Recover
	}

	const FPrisonDestination Plan = Schedule->PlanForCurrentPeriod();
	Data.PeriodIndex = Plan.PeriodIndex;
	Data.bPlanValid = Plan.bValid;
	Data.StartDelaySeconds = static_cast<float>(Plan.StartDelaySeconds);
	Data.ArrivalTolerance = 60.f;
	if (Plan.bValid)
	{
		Data.TargetActor = Plan.Marker;
		Data.MarkerId = Plan.MarkerId;
		Data.IdleSeconds = static_cast<float>(Plan.IdleSeconds);
		Data.bMoveRequired = Plan.bMoveRequired;
		if (UPrisonActivityComponent* Activity = Data.Actor->FindComponentByClass<UPrisonActivityComponent>())
		{
			Data.ArrivalTolerance = static_cast<float>(Activity->GetMoveAcceptableRadius(Plan.MarkerId, 60.0));
			// If the NPC is still leaving an activity, wait for its predicted exit before walking (the component keeps movement held until
			// it is really free, so a wrong prediction can never make the NPC slide out of the pose). Continuing the same activity needs no wait.
			const float Exit = static_cast<float>(Activity->GetSecondsUntilFreeFor(Plan.MarkerId, Plan.bMoveRequired));
			Data.StartDelaySeconds = FMath::Max(Data.StartDelaySeconds, Exit);
		}
	}
	return EStateTreeRunStatus::Running;
}

bool FPrisonReplanRequestedCondition::TestCondition(FStateTreeExecutionContext& Context) const
{
	const FInstanceDataType& Data = Context.GetInstanceData(*this);
	const UPrisonScheduleComponent* Schedule = Data.Actor ? Data.Actor->FindComponentByClass<UPrisonScheduleComponent>() : nullptr;
	const bool bRequested = Schedule && Schedule->IsReplanRequested();
	return bRequested != bInvert;
}

FPrisonPerformActivityTask::FPrisonPerformActivityTask()
{
	// Background task: it never ends the state and does no per-tick work.
	bShouldCallTick = false;
	bShouldStateChangeOnReselect = true;
#if WITH_EDITORONLY_DATA
	bConsideredForCompletion = false;
	bCanEditConsideredForCompletion = false;
#endif
}

EStateTreeRunStatus FPrisonPerformActivityTask::EnterState(FStateTreeExecutionContext& Context, const FStateTreeTransitionResult& Transition) const
{
	FInstanceDataType& Data = Context.GetInstanceData(*this);
	Data.bActivityAccepted = false;
	if (UPrisonActivityComponent* Activity = Data.Actor ? Data.Actor->FindComponentByClass<UPrisonActivityComponent>() : nullptr; Activity && !Data.MarkerId.IsNone())
	{
		Data.bActivityAccepted = Activity->RequestActivity(Data.MarkerId); // false (with a reason on the component) for ordinary stops
	}
	return EStateTreeRunStatus::Running;
}

void FPrisonPerformActivityTask::ExitState(FStateTreeExecutionContext& Context, const FStateTreeTransitionResult& Transition) const
{
	const FInstanceDataType& Data = Context.GetInstanceData(*this);
	if (UPrisonActivityComponent* Activity = Data.Actor ? Data.Actor->FindComponentByClass<UPrisonActivityComponent>() : nullptr)
	{
		Activity->ReleaseActivity(); // starts the grace window and the exit; the component restores movement itself
	}
}
