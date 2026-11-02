// Copyright Cyber Warden. All Rights Reserved.

#include "PrisonScheduleStateTree.h"
#include "PrisonScheduleComponent.h"
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
	if (Plan.bValid)
	{
		Data.TargetActor = Plan.Marker;
		Data.MarkerId = Plan.MarkerId;
		Data.IdleSeconds = static_cast<float>(Plan.IdleSeconds);
		Data.bMoveRequired = Plan.bMoveRequired;
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
