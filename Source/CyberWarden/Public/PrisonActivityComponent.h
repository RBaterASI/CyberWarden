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
 *
 * Animation sequencing (M2.3 Stage C1, for example sitting down at a table): the enter, loop and exit animations are dynamic montages in one slot.
 * The loop starts one cross-fade before the enter animation ends (driven by the montage's real remaining time), so the standing pose never shows
 * between them; the exit cross-fades out of the loop. A definition with bCommitEnter finishes sitting down even if it is released meanwhile. The exit
 * ends, and movement is restored, when the animation reports it is finished (the planned duration is only the earliest time, with a safety margin
 * after it). All per-phase blends, the release grace and the commit flag come from the activity definition; nothing is specific to an NPC or a point.
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
	double ReleaseGraceSeconds = 0.5;

	/**
	 * Movement is restored when the exit animation reports it has finished. If it never does (a montage that is stuck or was cut), the NPC is
	 * freed this long after the planned end of the exit, so the hold can never last for ever.
	 */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Activity", meta = (ClampMin = "0.0"))
	double ExitSafetyMarginSeconds = 1.0;

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

	/** Activities that ran their whole exit and freed the NPC (not counting interrupts and aborts). */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Diagnostics")
	int32 CompleteCount = 0;

	/** Enter animations that cross-faded into their loop. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Diagnostics")
	int32 HandoffCount = 0;

	/** Farthest the NPC has been from where the current (or last) activity started, in cm (3D): activities never move the capsule. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Diagnostics")
	double MaxDisplacementCm = 0.0;

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

	/**
	 * The NPC is about to leave for NextMarkerId (a different point, or the same one but it has to walk): skip what is left of the release grace
	 * window so the exit starts now. Does nothing when the next plan simply continues this activity, or when nothing is pending release.
	 * Called by the plan task after the Perform Activity task released the activity.
	 */
	UFUNCTION(BlueprintCallable, Category = "Activity")
	void ExpediteRelease(FName NextMarkerId, bool bNextMoveRequired);

	/**
	 * Seconds until the NPC is free to move: 0 when idle, the remaining grace + exit time while a release is pending or the exit
	 * is playing. A prediction for planning only: the movement hold (released by the component itself) is the authority.
	 */
	UFUNCTION(BlueprintCallable, Category = "Activity")
	double GetSecondsUntilFree() const;

	/**
	 * Like GetSecondsUntilFree, but 0 when the NPC is about to continue the same activity (same marker and no movement needed),
	 * which is the case for single-stop destinations that re-plan every idle cycle.
	 */
	UFUNCTION(BlueprintCallable, Category = "Activity")
	double GetSecondsUntilFreeFor(FName NextMarkerId, bool bNextMoveRequired) const;

	/**
	 * Acceptable radius for the Move To task when walking to a destination: DefaultRadius, or smaller when the interaction point
	 * needs a tighter stop (point tolerance minus the capsule radius minus a 20 cm margin, never below 10 cm).
	 */
	UFUNCTION(BlueprintCallable, Category = "Activity")
	double GetMoveAcceptableRadius(FName MarkerId, double DefaultRadius = 60.0);

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
	double GraceSeconds() const;
	/** Real seconds the enter animation still has to play, read from the montage itself (falls back to the planned end). */
	double RemainingEnterSeconds() const;
	/** True when there is no active montage, or the animation instance reports it is no longer playing. */
	bool ActiveMontageFinished() const;
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
	FVector ActivityStartLocation = FVector::ZeroVector;
	int32 LoopRestarts = 0;
	TEnumAsByte<EMovementMode> SavedMovementMode = MOVE_Walking;
	uint8 SavedCustomMode = 0;
	FRandomStream RandomStream;
	bool bRandomInitialized = false;
	TMap<FName, TWeakObjectPtr<AActor>> MarkerCache;
};
