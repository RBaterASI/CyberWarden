// Copyright Cyber Warden. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "Math/RandomStream.h"
#include "PrisonScheduleComponent.generated.h"

class APrisonScheduleManager;
class UPrisonScheduleData;

/** Result of planning a destination. Safe to use when bValid is false (all other fields are then neutral). */
USTRUCT(BlueprintType)
struct CYBERWARDEN_API FPrisonDestination
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Schedule")
	bool bValid = false;

	UPROPERTY(BlueprintReadOnly, Category = "Schedule")
	FName MarkerId;

	/** The marker actor to walk to (null when invalid). */
	UPROPERTY(BlueprintReadOnly, Category = "Schedule")
	TObjectPtr<AActor> Marker = nullptr;

	/** Idle duration after arriving, in REAL seconds. */
	UPROPERTY(BlueprintReadOnly, Category = "Schedule")
	double IdleSeconds = 0.0;

	/** False when the NPC already stands within ArrivalRadius of the marker: skip the movement request. */
	UPROPERTY(BlueprintReadOnly, Category = "Schedule")
	bool bMoveRequired = false;

	/** The period has exactly one candidate stop. */
	UPROPERTY(BlueprintReadOnly, Category = "Schedule")
	bool bSingleStop = false;

	UPROPERTY(BlueprintReadOnly, Category = "Schedule")
	int32 PeriodIndex = INDEX_NONE;

	/** Real seconds to wait before moving: the departure stagger on the very first plan, a back-off after quick repeated
	 *  retries of the same movement, otherwise 0 (the stagger was already waited for before a replan request was raised). */
	UPROPERTY(BlueprintReadOnly, Category = "Schedule")
	double StartDelaySeconds = 0.0;

	/** Why the plan is invalid, or a short description of the choice. */
	UPROPERTY(BlueprintReadOnly, Category = "Schedule")
	FString Reason;
};

/**
 * Per-NPC daily schedule logic (M2.2 Checkpoint A). Reads the NPC's assignments from the sector schedule data
 * (through the schedule manager), detects period changes, applies a deterministic departure stagger, raises a ONE-SHOT
 * replan request and chooses destinations. It never moves the NPC and does not touch the StateTree: a later StateTree
 * task calls PlanForCurrentPeriod() (which also acknowledges the request) and polls IsReplanRequested().
 */
UCLASS(ClassGroup = (CyberWarden), meta = (BlueprintSpawnableComponent))
class CYBERWARDEN_API UPrisonScheduleComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	UPrisonScheduleComponent();

	// ---- Configuration -----------------------------------------------------------------------------------------
	/** The sector's schedule manager. If empty, the component finds the manager tagged S01F1ScheduleManager. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Schedule")
	TObjectPtr<APrisonScheduleManager> ScheduleManager;

	/** NPC id in the schedule data. If None, the owner's "NpcId" string variable (BP_PrisonNPC) is used. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Schedule")
	FName NpcIdOverride;

	/** Within this horizontal distance of the marker the NPC counts as already there (no movement request needed). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Schedule", meta = (ClampMin = "0.0"))
	double ArrivalRadius = 150.0;

	// ---- Diagnostics (Blueprint / Python readable) --------------------------------------------------------------
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Diagnostics")
	FName ResolvedNpcId;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Diagnostics")
	bool bHasSchedule = false;

	/** Period the current plan was made for (INDEX_NONE until the first PlanForCurrentPeriod). */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Diagnostics")
	int32 AppliedPeriodIndex = INDEX_NONE;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Diagnostics")
	FString AppliedPeriodName;

	/** Period the manager reports right now. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Diagnostics")
	int32 ManagerPeriodIndex = INDEX_NONE;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Diagnostics")
	FName CurrentStopMarkerId;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Diagnostics")
	double CurrentIdleSeconds = 0.0;

	/** This NPC's departure stagger, in game seconds (StaggerFraction x StaggerMaxGameMinutes x 60). */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Diagnostics")
	double StaggerGameSeconds = 0.0;

	/** True while a period change has been seen but the stagger has not elapsed yet. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Diagnostics")
	bool bStaggerPending = false;

	/** One-shot: raised once per schedule change after the stagger, cleared by AcknowledgeReplan / PlanForCurrentPeriod. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Diagnostics")
	bool bReplanRequested = false;

	/** Number of replan requests raised so far (never decreases). */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Diagnostics")
	int32 ReplanSerial = 0;

	/** Number of requests acknowledged. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Diagnostics")
	int32 ReplanAckCount = 0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Diagnostics")
	int32 PlanCount = 0;

	/** Consecutive quick re-plans of the same required movement (0 = healthy). */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Diagnostics")
	int32 RetryStreakCount = 0;

	/** Game seconds (manager total) at which the pending change was first seen. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Diagnostics")
	double PeriodChangeObservedAt = 0.0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Diagnostics")
	FString LastDiagnostic;

	// ---- API ---------------------------------------------------------------------------------------------------
	/**
	 * Plans a destination for the manager's CURRENT period: picks a stop (avoiding the previous one when several exist),
	 * draws the idle time, and acknowledges any pending replan request (AppliedPeriodIndex becomes the current period).
	 * Never throws: with no manager, data, NPC entry or stops it returns bValid = false and records LastDiagnostic.
	 */
	UFUNCTION(BlueprintCallable, Category = "Schedule")
	FPrisonDestination PlanForCurrentPeriod();

	/** Acknowledges a pending request without planning (clears the one-shot and adopts the current period). */
	UFUNCTION(BlueprintCallable, Category = "Schedule")
	void AcknowledgeReplan();

	UFUNCTION(BlueprintPure, Category = "Schedule")
	bool IsReplanRequested() const { return bReplanRequested; }

	/** Real seconds of stagger at the manager's current time scale. */
	UFUNCTION(BlueprintPure, Category = "Schedule")
	double GetStaggerRealSeconds() const;

	/** Re-reads the manager, NPC id and schedule data (after changing NpcIdOverride or ScheduleManager at runtime). */
	UFUNCTION(BlueprintCallable, Category = "Schedule")
	void RefreshContext();

	/** Finds a marker actor by id (tag "MarkerId:<id>"), or null. */
	UFUNCTION(BlueprintCallable, Category = "Schedule")
	AActor* ResolveMarker(FName MarkerId);

	/** Checks every stop of this NPC's whole schedule resolves to an existing NavDest:Yes marker. Returns the errors. */
	UFUNCTION(BlueprintCallable, Category = "Schedule")
	TArray<FString> ValidateAssignments();

	virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;

protected:
	virtual void BeginPlay() override;

private:
	bool ResolveContext();
	void RebuildMarkerCache();
	UPrisonScheduleData* GetData() const;

	bool bContextResolved = false;
	bool bWarnedNoManager = false;
	/** Quick re-plans of the same movement (a Move To that keeps failing): drives the back-off. */
	int32 RetryStreak = 0;
	double LastPlanRealSeconds = -1000.0;
	FName LastPlanMarkerId;
	bool bLastPlanMoveRequired = false;
	FRandomStream RandomStream;
	TMap<FName, TWeakObjectPtr<AActor>> MarkerCache;
};
