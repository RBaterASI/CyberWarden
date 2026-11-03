// Copyright Cyber Warden. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "StateTreeTaskBase.h"
#include "StateTreeConditionBase.h"
#include "PrisonScheduleStateTree.generated.h"

class AActor;

/**
 * Instance data of the "Prison: Plan Destination" task. Context.Actor binds automatically to the StateTree context actor
 * (the possessed NPC). The Output properties are meant to be bound by the Delay and Move To tasks of the routine.
 * All timing outputs are real (float) numbers, unlike the legacy integer-typed Blueprint outputs.
 */
USTRUCT()
struct CYBERWARDEN_API FPrisonPlanDestinationInstanceData
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, Category = Context)
	TObjectPtr<AActor> Actor = nullptr;

	/** Marker to walk to. Null when the plan is invalid (never a stale value from an earlier plan). */
	UPROPERTY(VisibleAnywhere, Category = Output)
	TObjectPtr<AActor> TargetActor = nullptr;

	/** Idle duration at the destination in REAL seconds. */
	UPROPERTY(VisibleAnywhere, Category = Output)
	float IdleSeconds = 5.f;

	/** Delay before moving, in real seconds: the NPC's departure stagger on the first plan, a back-off after repeated retries, else 0. */
	UPROPERTY(VisibleAnywhere, Category = Output)
	float StartDelaySeconds = 0.f;

	/** False when the NPC already stands within the arrival radius of the destination: skip the Move To state. */
	UPROPERTY(VisibleAnywhere, Category = Output)
	bool bMoveRequired = false;

	/** False when the schedule produced no usable destination (the routine should fall through to Recover). */
	UPROPERTY(VisibleAnywhere, Category = Output)
	bool bPlanValid = false;

	/** Acceptable radius (cm) for the Move To task: 60 for ordinary stops, smaller when the destination is an interaction point that needs a tighter stop. */
	UPROPERTY(VisibleAnywhere, Category = Output)
	float ArrivalTolerance = 60.f;

	UPROPERTY(VisibleAnywhere, Category = Output)
	FName MarkerId;

	UPROPERTY(VisibleAnywhere, Category = Output)
	int32 PeriodIndex = INDEX_NONE;
};

/**
 * Plans the NPC's destination for the schedule manager's current period (UPrisonScheduleComponent::PlanForCurrentPeriod).
 * Runs on entering the routine's root state; acknowledging the plan clears the component's one-shot replan request, so a
 * schedule change restarts the routine exactly once. Never ends the state by itself.
 */
USTRUCT(meta = (DisplayName = "Prison: Plan Destination", Category = "Cyber Warden"))
struct CYBERWARDEN_API FPrisonPlanDestinationTask : public FStateTreeTaskCommonBase
{
	GENERATED_BODY()

	using FInstanceDataType = FPrisonPlanDestinationInstanceData;

	FPrisonPlanDestinationTask();

	virtual const UStruct* GetInstanceDataType() const override { return FInstanceDataType::StaticStruct(); }
	virtual EStateTreeRunStatus EnterState(FStateTreeExecutionContext& Context, const FStateTreeTransitionResult& Transition) const override;
};

USTRUCT()
struct CYBERWARDEN_API FPrisonReplanRequestedConditionInstanceData
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, Category = Context)
	TObjectPtr<AActor> Actor = nullptr;
};

/**
 * True when the NPC's schedule component has raised its one-shot replan request (period changed and the NPC's stagger has
 * elapsed). Use on a transition of the routine's root state with trigger "On Tick" and target "Routine".
 */
USTRUCT(meta = (DisplayName = "Prison: Replan Requested", Category = "Cyber Warden"))
struct CYBERWARDEN_API FPrisonReplanRequestedCondition : public FStateTreeConditionCommonBase
{
	GENERATED_BODY()

	using FInstanceDataType = FPrisonReplanRequestedConditionInstanceData;

	virtual const UStruct* GetInstanceDataType() const override { return FInstanceDataType::StaticStruct(); }
	virtual bool TestCondition(FStateTreeExecutionContext& Context) const override;

	UPROPERTY(EditAnywhere, Category = Parameter)
	bool bInvert = false;
};

/** Instance data of "Prison: Perform Activity". */
USTRUCT()
struct CYBERWARDEN_API FPrisonPerformActivityInstanceData
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, Category = Context)
	TObjectPtr<AActor> Actor = nullptr;

	/** Destination marker of the current stop: bind to "Prison: Plan Destination > Marker Id". */
	UPROPERTY(EditAnywhere, Category = Input)
	FName MarkerId;

	/** True when the destination is an interaction point and the activity started or continues. */
	UPROPERTY(VisibleAnywhere, Category = Output)
	bool bActivityAccepted = false;
};

/**
 * Runs the interaction point's activity (UPrisonActivityComponent) for the destination the NPC is standing at. Meant for the
 * idle state of the routine, next to the Delay task: entering the state requests the activity (a stop without an interaction
 * point is simply ignored), leaving the state releases it. The task never completes the state (the Delay decides how long the
 * activity lasts) and never moves anything; the activity component holds movement while it is busy and restores it itself.
 */
USTRUCT(meta = (DisplayName = "Prison: Perform Activity", Category = "Cyber Warden"))
struct CYBERWARDEN_API FPrisonPerformActivityTask : public FStateTreeTaskCommonBase
{
	GENERATED_BODY()

	using FInstanceDataType = FPrisonPerformActivityInstanceData;

	FPrisonPerformActivityTask();

	virtual const UStruct* GetInstanceDataType() const override { return FInstanceDataType::StaticStruct(); }
	virtual EStateTreeRunStatus EnterState(FStateTreeExecutionContext& Context, const FStateTreeTransitionResult& Transition) const override;
	virtual void ExitState(FStateTreeExecutionContext& Context, const FStateTreeTransitionResult& Transition) const override;
};
