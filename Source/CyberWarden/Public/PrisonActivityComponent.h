// Copyright Cyber Warden. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "Math/RandomStream.h"
#include "PrisonActivityData.h"
#include "PrisonActivityComponent.generated.h"

class UAnimInstance;
class UAnimMontage;

UENUM(BlueprintType)
enum class EPrisonActivityState : uint8
{
	/** No activity: the NPC moves normally. */
	Idle,
	/** Turning towards the interaction point (the NPC stands still, movement is held). */
	Aligning,
	/** Playing the optional enter animation. */
	Entering,
	/** Looping the activity (or simply standing, when the activity has no animation). */
	Performing,
	/** Playing the optional exit animation / blending out; movement is held until it ends. */
	Exiting
};

/**
 * Activity execution for one NPC (M2.3 Stage A). It is independent of the NPC, the schedule and the StateTree: whoever
 * knows the NPC stands at a schedule destination calls RequestActivity(MarkerId); the component looks the marker up in the
 * sector's interaction points and runs that point's activity:
 *
 *   RequestActivity -> Aligning (smooth yaw turn, nothing else moves) -> [Entering] -> Performing -> ReleaseActivity -> [Exiting] -> Idle
 *
 * It never moves the NPC to the marker (no teleport, no snapping): the NPC must already be within the point's arrival
 * tolerance, otherwise the request fails with a reason. While busy the character's movement is held (MOVE_None) and is
 * restored when the activity ends, is interrupted or the component is destroyed.
 */
UCLASS(ClassGroup = (CyberWarden), meta = (BlueprintSpawnableComponent))
class CYBERWARDEN_API UPrisonActivityComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	UPrisonActivityComponent();

	// ---- Configuration -----------------------------------------------------------------------------------------
	/** Activity data. If empty, the sector's schedule manager (tag S01F1ScheduleManager) supplies it. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Activity")
	TObjectPtr<UPrisonActivityData> ActivityDataOverride;

	/**
	 * After ReleaseActivity the activity keeps running this long. A request for the same point within the window continues it
	 * seamlessly (single-stop destinations re-plan every idle cycle and must not restart the animation).
	 */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Activity", meta = (ClampMin = "0.0"))
	double ReleaseGraceSeconds = 0.25;

	// ---- Diagnostics (Blueprint / Python readable) ---------------------------------------------------------------
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Diagnostics")
	EPrisonActivityState State = EPrisonActivityState::Idle;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Diagnostics")
	FName ActiveActivityId;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Diagnostics")
	FName ActiveMarkerId;

	/** Number of activities actually started (an accepted request for a new arrival). */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Diagnostics")
	int32 StartCount = 0;

	/** Requests for the activity that was already running (or pending release): no restart. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Diagnostics")
	int32 ContinuationCount = 0;

	/** Activities cut short while aligning or entering. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Diagnostics")
	int32 InterruptCount = 0;

	/** The loop montage ended without being asked to (restarted, bounded). */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Diagnostics")
	int32 UnexpectedStopCount = 0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Diagnostics")
	FString LastFailureReason;

	/** Target yaw minus current yaw while aligning, in degrees. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Diagnostics")
	double YawErrorDegrees = 0.0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Diagnostics")
	double TargetYawDegrees = 0.0;

	/** Horizontal distance to the active marker (cm). */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Diagnostics")
	double DistanceToMarker = 0.0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Diagnostics")
	bool bMontagePlaying = false;

	/** Weight of the animation slot node: proves the animation Blueprint really processes the montage. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Diagnostics")
	double SlotNodeWeight = 0.0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Diagnostics")
	bool bMovementHeld = false;

	/** The activity has no usable loop animation: the NPC stands in its normal idle pose. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Diagnostics")
	bool bUsingFallbackIdle = false;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Diagnostics")
	bool bReleasePending = false;

	/** A request received while another activity was exiting; started when the NPC is free. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Diagnostics")
	FName PendingMarkerId;

	// ---- API ---------------------------------------------------------------------------------------------------
	/**
	 * Starts, continues or queues the activity of the interaction point of MarkerId. Returns true when the request is accepted
	 * (started, continuing, or queued behind an exit). Returns false with LastFailureReason set when there is no data, no
	 * interaction point for the marker, the marker is not in the level, or the NPC is farther than the point's tolerance.
	 */
	UFUNCTION(BlueprintCallable, Category = "Activity")
	bool RequestActivity(FName MarkerId);

	/**
	 * Ends the activity. Returns the seconds until the NPC is free to move (grace + exit animation / blend out), 0 when nothing
	 * needs to finish. Aligning is cancelled immediately; entering blends out; performing waits ReleaseGraceSeconds first so a
	 * re-request for the same point continues without a restart.
	 */
	UFUNCTION(BlueprintCallable, Category = "Activity")
	double ReleaseActivity();

	/** Stops everything now and restores movement (used when the owner is destroyed or something must interrupt hard). */
	UFUNCTION(BlueprintCallable, Category = "Activity")
	void AbortActivity();

	/** True from the accepted request until movement is restored. */
	UFUNCTION(BlueprintPure, Category = "Activity")
	bool IsBusy() const { return State != EPrisonActivityState::Idle; }

	/** The interaction point for a marker exists in the activity data. */
	UFUNCTION(BlueprintCallable, Category = "Activity")
	bool HasInteractionPoint(FName MarkerId);

	virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;

protected:
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

private:
	UPrisonActivityData* ResolveData();
	AActor* ResolveMarker(FName MarkerId);
	UAnimInstance* GetAnimInstance() const;
	double Now() const;

	bool TryStart(FName MarkerId);
	void StartLoop();
	void BeginExit();
	void FinishActivity();
	void StopMontage(float BlendOutSeconds);
	double ExitSeconds() const;
	void HoldMovement();
	void ReleaseMovement();
	void SetState(EPrisonActivityState NewState);
	void UpdateDiagnostics();
	void Fail(const FString& Reason);

	FPrisonInteractionPoint ActivePoint;
	FPrisonActivityDefinition ActiveDef;
	UPROPERTY(Transient)
	TObjectPtr<UAnimMontage> ActiveMontage;
	double PhaseEndAt = 0.0;
	double ReleaseAt = 0.0;
	int32 LoopRestarts = 0;
	TEnumAsByte<EMovementMode> SavedMovementMode = MOVE_Walking;
	uint8 SavedCustomMode = 0;
	FRandomStream RandomStream;
	bool bRandomInitialized = false;
	TMap<FName, TWeakObjectPtr<AActor>> MarkerCache;
};
