// Copyright Cyber Warden. All Rights Reserved.

#include "PrisonActivityComponent.h"
#include "PrisonActivityMath.h"
#include "PrisonScheduleManager.h"
#include "CyberWarden.h"
#include "Animation/AnimInstance.h"
#include "Animation/AnimMontage.h"
#include "Animation/AnimSequence.h"
#include "AIController.h"
#include "Navigation/PathFollowingComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "EngineUtils.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"

UPrisonActivityComponent::UPrisonActivityComponent()
{
	PrimaryComponentTick.bCanEverTick = true;
	PrimaryComponentTick.bStartWithTickEnabled = true;
}

double UPrisonActivityComponent::Now() const
{
	return GetWorld() ? GetWorld()->GetTimeSeconds() : 0.0;
}

UAnimInstance* UPrisonActivityComponent::GetAnimInstance() const
{
	const AActor* Owner = GetOwner();
	if (!Owner)
	{
		return nullptr;
	}
	const ACharacter* Character = Cast<ACharacter>(Owner);
	USkeletalMeshComponent* Mesh = Character ? Character->GetMesh() : Owner->FindComponentByClass<USkeletalMeshComponent>();
	return Mesh ? Mesh->GetAnimInstance() : nullptr;
}

UPrisonActivityData* UPrisonActivityComponent::ResolveData()
{
	if (ActivityDataOverride)
	{
		return ActivityDataOverride;
	}
	if (UWorld* World = GetWorld())
	{
		for (TActorIterator<APrisonScheduleManager> It(World); It; ++It)
		{
			return It->ActivityData.Get();
		}
	}
	return nullptr;
}

AActor* UPrisonActivityComponent::ResolveMarker(FName MarkerId)
{
	if (TWeakObjectPtr<AActor>* Found = MarkerCache.Find(MarkerId); Found && Found->IsValid())
	{
		return Found->Get();
	}
	MarkerCache.Reset();
	if (UWorld* World = GetWorld())
	{
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
	TWeakObjectPtr<AActor>* Found = MarkerCache.Find(MarkerId);
	return (Found && Found->IsValid()) ? Found->Get() : nullptr;
}

void UPrisonActivityComponent::Fail(const FString& Reason)
{
	LastFailureReason = Reason;
	UE_LOG(LogCyberWarden, Verbose, TEXT("%s activity request failed: %s"), *GetNameSafe(GetOwner()), *Reason);
}

void UPrisonActivityComponent::SetState(EPrisonActivityState NewState)
{
	State = NewState;
}

bool UPrisonActivityComponent::HasInteractionPoint(FName MarkerId)
{
	const UPrisonActivityData* Data = ResolveData();
	return Data && Data->FindPoint(MarkerId) != nullptr;
}

void UPrisonActivityComponent::HoldMovement()
{
	ACharacter* Character = Cast<ACharacter>(GetOwner());
	UCharacterMovementComponent* Movement = Character ? Character->GetCharacterMovement() : nullptr;
	if (!Movement || bMovementHeld)
	{
		return;
	}
	const bool bGroundMode = Movement->MovementMode == MOVE_Walking || Movement->MovementMode == MOVE_NavWalking;
	SavedMovementMode = bGroundMode ? Movement->MovementMode.GetValue() : MOVE_Walking;
	SavedCustomMode = Movement->CustomMovementMode;
	Movement->StopMovementImmediately();
	Movement->DisableMovement();
	bMovementHeld = true;
}

void UPrisonActivityComponent::ReleaseMovement()
{
	if (!bMovementHeld)
	{
		return;
	}
	bMovementHeld = false;
	if (ACharacter* Character = Cast<ACharacter>(GetOwner()))
	{
		if (UCharacterMovementComponent* Movement = Character->GetCharacterMovement())
		{
			Movement->SetMovementMode(SavedMovementMode, SavedCustomMode);
		}
	}
}

void UPrisonActivityComponent::StopMontage(float BlendOutSeconds)
{
	if (UAnimInstance* Anim = GetAnimInstance(); Anim && ActiveMontage)
	{
		Anim->Montage_Stop(BlendOutSeconds, ActiveMontage);
	}
	ActiveMontage = nullptr;
}

double UPrisonActivityComponent::ExitSeconds() const
{
	if (const UAnimSequence* Exit = ActiveDef.ExitAnimation.IsNull() ? nullptr : ActiveDef.ExitAnimation.LoadSynchronous())
	{
		return Exit->GetPlayLength() / FMath::Max(ActiveDef.PlayRate, 0.01f);
	}
	return ActiveDef.GetExitBlendOut();
}

double UPrisonActivityComponent::GraceSeconds() const
{
	return ActiveDef.ReleaseGraceSeconds >= 0.f ? static_cast<double>(ActiveDef.ReleaseGraceSeconds) : ReleaseGraceSeconds;
}

double UPrisonActivityComponent::RemainingEnterSeconds() const
{
	const UAnimInstance* Anim = GetAnimInstance();
	UAnimInstance* MutableAnim = const_cast<UAnimInstance*>(Anim);
	if (MutableAnim && ActiveMontage && MutableAnim->Montage_IsPlaying(ActiveMontage))
	{
		return PrisonActivityMath::RemainingPlaySeconds(ActiveMontage->GetPlayLength(), MutableAnim->Montage_GetPosition(ActiveMontage), ActiveDef.PlayRate);
	}
	return FMath::Max(0.0, PhaseEndAt - Now());
}

bool UPrisonActivityComponent::ActiveMontageFinished() const
{
	UAnimInstance* Anim = GetAnimInstance();
	return !Anim || !ActiveMontage || !Anim->Montage_IsPlaying(ActiveMontage);
}

bool UPrisonActivityComponent::TryStart(FName MarkerId)
{
	const UPrisonActivityData* Data = ResolveData();
	if (!Data)
	{
		Fail(TEXT("no activity data (set ActivityDataOverride or give the schedule manager ActivityData)"));
		return false;
	}
	const FPrisonInteractionPoint* Point = Data->FindPoint(MarkerId);
	if (!Point)
	{
		Fail(FString::Printf(TEXT("no interaction point for marker %s"), *MarkerId.ToString()));
		return false;
	}
	const FPrisonActivityDefinition* Def = Data->FindActivity(Point->ActivityId);
	if (!Def)
	{
		Fail(FString::Printf(TEXT("interaction point %s uses unknown activity %s"), *MarkerId.ToString(), *Point->ActivityId.ToString()));
		return false;
	}
	const AActor* Marker = ResolveMarker(MarkerId);
	const AActor* Owner = GetOwner();
	if (!Marker || !Owner)
	{
		Fail(FString::Printf(TEXT("marker actor %s not found in the level"), *MarkerId.ToString()));
		return false;
	}
	const double Dist = FVector::Dist2D(Owner->GetActorLocation(), Marker->GetActorLocation());
	DistanceToMarker = Dist;
	if (Point->bFinalApproach)
	{
		if (const FApproachLockout* Lockout = ApproachLockouts.Find(MarkerId); Lockout && PrisonActivityMath::ApproachLockedOut(Now(), Lockout->At, ApproachRetryLockoutSeconds))
		{
			++ApproachLockoutRefusals;
			Fail(FString::Printf(TEXT("final approach to %s failed %.0f s ago (%s): not retried for %.0f s"), *MarkerId.ToString(), Now() - Lockout->At, *Lockout->Reason, ApproachRetryLockoutSeconds));
			return false;
		}
		if (!PrisonActivityMath::ApproachInReach(Dist, Point->FinalApproachMaxDistanceCm))
		{
			Fail(FString::Printf(TEXT("too far from %s for the final approach: %.0f cm > %.0f cm (navigate closer first)"), *MarkerId.ToString(), Dist, Point->FinalApproachMaxDistanceCm));
			return false;
		}
	}
	else if (Dist > Point->ArrivalToleranceCm)
	{
		Fail(FString::Printf(TEXT("too far from %s: %.0f cm > tolerance %.0f cm (navigate closer first)"), *MarkerId.ToString(), Dist, Point->ArrivalToleranceCm));
		return false;
	}

	ActivePoint = *Point;
	ActiveDef = *Def;
	ActiveMarkerId = MarkerId;
	ActiveActivityId = Def->Id;
	LoopRestarts = 0;
	bReleasePending = false;
	bUsingFallbackIdle = false;
	LastFailureReason.Empty();
	if (Point->bFinalApproach)
	{
		if (PrisonActivityMath::ApproachConfirmed(Dist, Point->FinalApproachToleranceCm))
		{
			LastApproachResult = TEXT("already there");
			LastApproachStartCm = LastApproachEndCm = Dist;
			LastApproachSeconds = LastApproachTravelCm = 0.0;
		}
		else
		{
			return BeginApproach(*Marker); // on failure the NPC stays standing, nothing started
		}
	}
	BeginAlignment();
	return true;
}

void UPrisonActivityComponent::BeginAlignment()
{
	const AActor* Owner = GetOwner();
	const FVector Loc = Owner->GetActorLocation();
	switch (ActivePoint.FacingMode)
	{
	case EPrisonFacingMode::Yaw:
		TargetYawDegrees = PrisonActivityMath::NormalizeYaw(ActivePoint.FacingYawDegrees);
		break;
	case EPrisonFacingMode::Point:
		TargetYawDegrees = PrisonActivityMath::YawToPoint(Loc.X, Loc.Y, ActivePoint.FacingPoint.X, ActivePoint.FacingPoint.Y);
		break;
	default:
		TargetYawDegrees = PrisonActivityMath::NormalizeYaw(Owner->GetActorRotation().Yaw);
		break;
	}
	++StartCount;
	ActivityStartLocation = Loc;
	MaxDisplacementCm = 0.0;
	HoldMovement();
	SetState(EPrisonActivityState::Aligning);
}

bool UPrisonActivityComponent::BeginApproach(const AActor& Marker)
{
	const ACharacter* Character = Cast<ACharacter>(GetOwner());
	AAIController* AIController = Character ? Cast<AAIController>(Character->GetController()) : nullptr;
	UPathFollowingComponent* PathFollowing = AIController ? AIController->GetPathFollowingComponent() : nullptr;
	const FVector Loc = GetOwner()->GetActorLocation();
	ApproachGoal = Marker.GetActorLocation();
	ApproachStartedAt = Now();
	ApproachStartLocation = Loc;
	LastApproachStartCm = FVector::Dist2D(Loc, ApproachGoal);
	LastApproachEndCm = LastApproachStartCm;
	LastApproachSeconds = LastApproachTravelCm = 0.0;
	LastApproachResult = TEXT("approaching");
	++ApproachStartCount;
	bApproachMoveFinished = false;
	ApproachMoveResult = EPathFollowingResult::Invalid;
	SetState(EPrisonActivityState::Approaching);
	if (!PathFollowing)
	{
		FailApproach(TEXT("the NPC has no AI controller to walk the final approach"));
		return false;
	}

	// One ordinary AI move request to the exact marker: normal navigation, collision, avoidance and locomotion animation. The acceptance radius is small and
	// the agent radius is not added (no stop-on-overlap), which is what Move To's stopping 40-47 cm out lacks. Nothing here moves the capsule directly.
	FAIMoveRequest Request(ApproachGoal);
	Request.SetAcceptanceRadius(ActivePoint.FinalApproachAcceptCm);
	Request.SetReachTestIncludesAgentRadius(false);
	Request.SetReachTestIncludesGoalRadius(false);
	Request.SetUsePathfinding(true);
	Request.SetProjectGoalLocation(true);
	Request.SetAllowPartialPath(false);
	Request.SetCanStrafe(false);
	Request.SetNavigationFilter(AIController->GetDefaultNavigationFilterClass());
	const FPathFollowingRequestResult Result = AIController->MoveTo(Request);
	switch (Result.Code)
	{
	case EPathFollowingRequestResult::Failed:
		FailApproach(TEXT("navigation refused the move request to the marker (no path or marker off the navigation mesh)"));
		return false;
	case EPathFollowingRequestResult::AlreadyAtGoal:
		bApproachMoveFinished = true; // the distance check in the tick decides whether that is accurate enough
		ApproachMoveResult = EPathFollowingResult::Success;
		break;
	default:
		ApproachRequestId = Result.MoveId;
		ApproachPathFollowing = PathFollowing;
		ApproachFinishedHandle = PathFollowing->OnRequestFinished.AddUObject(this, &UPrisonActivityComponent::OnApproachMoveFinished);
		bApproachMoveIssued = true;
		break;
	}
	return true;
}

void UPrisonActivityComponent::OnApproachMoveFinished(FAIRequestID RequestId, const FPathFollowingResult& Result)
{
	if (!bApproachMoveIssued || !ApproachRequestId.IsEquivalent(RequestId))
	{
		return;
	}
	bApproachMoveFinished = true;
	ApproachMoveResult = Result.Code;
	bApproachSuperseded = Result.HasFlag(FPathFollowingResultFlags::NewRequest);
}

void UPrisonActivityComponent::StopApproachMove()
{
	if (!bApproachMoveIssued)
	{
		return;
	}
	bApproachMoveIssued = false;
	if (UPathFollowingComponent* PathFollowing = ApproachPathFollowing.Get())
	{
		PathFollowing->OnRequestFinished.Remove(ApproachFinishedHandle);
		// Only our own request is aborted: if another one has replaced it (the routine's Move To) that request is not ours to touch.
		if (PathFollowing->GetStatus() != EPathFollowingStatus::Idle && PathFollowing->GetCurrentRequestId().IsEquivalent(ApproachRequestId))
		{
			PathFollowing->AbortMove(*this, FPathFollowingResultFlags::UserAbort, ApproachRequestId);
		}
	}
	ApproachFinishedHandle.Reset();
	ApproachPathFollowing.Reset();
}

namespace
{
	const TCHAR* PathResultName(EPathFollowingResult::Type Code)
	{
		switch (Code)
		{
		case EPathFollowingResult::Success: return TEXT("success");
		case EPathFollowingResult::Blocked: return TEXT("blocked");
		case EPathFollowingResult::OffPath: return TEXT("off path");
		case EPathFollowingResult::Aborted: return TEXT("aborted");
		default: return TEXT("invalid");
		}
	}
}

void UPrisonActivityComponent::TickApproach()
{
	const AActor* Owner = GetOwner();
	const FVector Loc = Owner->GetActorLocation();
	const double Dist = FVector::Dist2D(Loc, ApproachGoal);
	const FPrisonInteractionPoint& Point = ActivePoint;
	if (bApproachMoveFinished)
	{
		const EPathFollowingResult::Type Code = ApproachMoveResult;
		const bool bSuperseded = bApproachSuperseded;
		StopApproachMove();
		if (Code == EPathFollowingResult::Success)
		{
			// Confirm the final position with the capsule held still: the activity only starts from where the NPC really stands.
			HoldMovement();
			const double Held = FVector::Dist2D(Owner->GetActorLocation(), ApproachGoal);
			if (PrisonActivityMath::ApproachConfirmed(Held, Point.FinalApproachToleranceCm))
			{
				LastApproachEndCm = Held;
				LastApproachSeconds = Now() - ApproachStartedAt;
				LastApproachTravelCm = FVector::Dist2D(Owner->GetActorLocation(), ApproachStartLocation);
				LastApproachResult = TEXT("success");
				++ApproachSuccessCount;
				BeginAlignment();
				return;
			}
			ReleaseMovement();
			FailApproach(FString::Printf(TEXT("the NPC stopped %.1f cm from the marker (tolerance %.1f cm)"), Held, Point.FinalApproachToleranceCm));
		}
		else if (Code == EPathFollowingResult::Aborted && bSuperseded)
		{
			CancelApproach(TEXT("another move request replaced it"));
		}
		else
		{
			FailApproach(FString::Printf(TEXT("path following ended with %s %.1f cm from the marker"), PathResultName(Code), Dist));
		}
		return;
	}
	if (FVector::Dist2D(Loc, ApproachStartLocation) > Point.FinalApproachMaxDistanceCm)
	{
		FailApproach(FString::Printf(TEXT("the walk left the %.0f cm bound"), Point.FinalApproachMaxDistanceCm));
	}
	else if (PrisonActivityMath::ApproachTimedOut(Now(), ApproachStartedAt, Point.FinalApproachTimeoutSeconds))
	{
		FailApproach(FString::Printf(TEXT("timed out after %.1f s, %.1f cm from the marker"), Point.FinalApproachTimeoutSeconds, Dist));
	}
}

void UPrisonActivityComponent::CancelApproach(const FString& Why)
{
	const AActor* Owner = GetOwner();
	LastApproachEndCm = Owner ? FVector::Dist2D(Owner->GetActorLocation(), ApproachGoal) : LastApproachEndCm;
	LastApproachSeconds = Now() - ApproachStartedAt;
	LastApproachTravelCm = Owner ? FVector::Dist2D(Owner->GetActorLocation(), ApproachStartLocation) : 0.0;
	LastApproachResult = FString::Printf(TEXT("cancelled: %s"), *Why);
	++ApproachCancelCount;
	StopApproachMove();
	FinishActivity(); // starts a queued request, if any
}

void UPrisonActivityComponent::FailApproach(const FString& Reason)
{
	const AActor* Owner = GetOwner();
	const FName MarkerId = ActiveMarkerId;
	LastApproachEndCm = Owner ? FVector::Dist2D(Owner->GetActorLocation(), ApproachGoal) : LastApproachEndCm;
	LastApproachSeconds = Now() - ApproachStartedAt;
	LastApproachTravelCm = Owner ? FVector::Dist2D(Owner->GetActorLocation(), ApproachStartLocation) : 0.0;
	LastApproachResult = FString::Printf(TEXT("failed: %s"), *Reason);
	++ApproachFailCount;
	ApproachLockouts.Add(MarkerId, FApproachLockout{ Now(), Reason });
	StopApproachMove(); // the NPC stays standing; movement authority goes back to the routine (it was never held during the approach)
	PendingMarkerId = NAME_None;
	FinishActivity();
	LastFailureReason = FString::Printf(TEXT("final approach to %s failed: %s"), *MarkerId.ToString(), *Reason);
	UE_LOG(LogCyberWarden, Warning, TEXT("%s: %s"), *GetNameSafe(GetOwner()), *LastFailureReason);
}

bool UPrisonActivityComponent::RequestActivity(FName MarkerId)
{
	if (State != EPrisonActivityState::Idle)
	{
		if (MarkerId == ActiveMarkerId && State != EPrisonActivityState::Exiting)
		{
			bReleasePending = false; // continuation: same arrival, no restart
			++ContinuationCount;
			LastFailureReason.Empty();
			return true;
		}
		if (!HasInteractionPoint(MarkerId))
		{
			Fail(FString::Printf(TEXT("no interaction point for marker %s"), *MarkerId.ToString()));
			return false;
		}
		// Another point (or the same point while it is exiting): finish the current activity first, then start this one.
		PendingMarkerId = MarkerId;
		if (State == EPrisonActivityState::Approaching)
		{
			CancelApproach(TEXT("another interaction point was requested")); // also starts the queued request
		}
		else if (State == EPrisonActivityState::Aligning)
		{
			++InterruptCount;
			FinishActivity();
		}
		else if (State == EPrisonActivityState::Entering)
		{
			if (ActiveDef.bCommitEnter)
			{
				// Leaving for another point: finish sitting down (no grace: this is not a continuation), then stand up.
				bReleasePending = true;
				ReleaseAt = Now();
			}
			else
			{
				++InterruptCount;
				StopMontage(ActiveDef.BlendOutSeconds);
				PhaseEndAt = Now() + ActiveDef.BlendOutSeconds;
				SetState(EPrisonActivityState::Exiting);
			}
		}
		else if (State == EPrisonActivityState::Performing)
		{
			BeginExit();
		}
		return true;
	}
	return TryStart(MarkerId);
}

double UPrisonActivityComponent::ReleaseActivity()
{
	PendingMarkerId = NAME_None; // a release cancels any queued request
	switch (State)
	{
	case EPrisonActivityState::Idle:
		return 0.0;
	case EPrisonActivityState::Approaching:
		CancelApproach(TEXT("released")); // the NPC is not held while approaching: it is free as soon as its own move request is dropped
		return 0.0;
	case EPrisonActivityState::Aligning:
		++InterruptCount;
		FinishActivity();
		return 0.0;
	case EPrisonActivityState::Entering:
		if (ActiveDef.bCommitEnter)
		{
			// Sitting down is not cut half way: the enter animation finishes, then the (graced) release takes effect.
			if (!bReleasePending)
			{
				bReleasePending = true;
				ReleaseAt = Now() + GraceSeconds();
			}
			return GetSecondsUntilFree();
		}
		++InterruptCount;
		StopMontage(ActiveDef.BlendOutSeconds);
		PhaseEndAt = Now() + ActiveDef.BlendOutSeconds;
		SetState(EPrisonActivityState::Exiting);
		return ActiveDef.BlendOutSeconds;
	case EPrisonActivityState::Performing:
		if (!bReleasePending)
		{
			bReleasePending = true;
			ReleaseAt = Now() + GraceSeconds();
		}
		return FMath::Max(0.0, ReleaseAt - Now()) + ExitSeconds();
	case EPrisonActivityState::Exiting:
		return FMath::Max(0.0, PhaseEndAt - Now());
	}
	return 0.0;
}

double UPrisonActivityComponent::GetSecondsUntilFree() const
{
	const double T = Now();
	switch (State)
	{
	case EPrisonActivityState::Idle:
	case EPrisonActivityState::Approaching:
	case EPrisonActivityState::Aligning:
		return 0.0; // approaching and aligning are cancelled immediately
	case EPrisonActivityState::Entering:
		if (ActiveDef.bCommitEnter)
		{
			return FMath::Max(RemainingEnterSeconds(), bReleasePending ? FMath::Max(0.0, ReleaseAt - T) : GraceSeconds()) + ExitSeconds();
		}
		return ActiveDef.BlendOutSeconds;
	case EPrisonActivityState::Performing:
		return (bReleasePending ? FMath::Max(0.0, ReleaseAt - T) : GraceSeconds()) + ExitSeconds();
	case EPrisonActivityState::Exiting:
		return FMath::Max(0.0, PhaseEndAt - T);
	}
	return 0.0;
}

double UPrisonActivityComponent::GetSecondsUntilFreeFor(FName NextMarkerId, bool bNextMoveRequired) const
{
	if (State != EPrisonActivityState::Idle && State != EPrisonActivityState::Exiting && NextMarkerId == ActiveMarkerId && !bNextMoveRequired)
	{
		return 0.0; // the same activity continues
	}
	return GetSecondsUntilFree();
}

void UPrisonActivityComponent::ExpediteRelease(FName NextMarkerId, bool bNextMoveRequired)
{
	if (!bReleasePending || (NextMarkerId == ActiveMarkerId && !bNextMoveRequired))
	{
		return; // nothing to expedite, or the next plan simply continues this activity
	}
	ReleaseAt = FMath::Min(ReleaseAt, Now());
}

double UPrisonActivityComponent::GetMoveAcceptableRadius(FName MarkerId, double DefaultRadius)
{
	const UPrisonActivityData* Data = ResolveData();
	const FPrisonInteractionPoint* Point = Data ? Data->FindPoint(MarkerId) : nullptr;
	if (!Point)
	{
		return DefaultRadius;
	}
	double Capsule = 34.0;
	if (const ACharacter* Character = Cast<ACharacter>(GetOwner()))
	{
		if (const UCapsuleComponent* Cap = Character->GetCapsuleComponent())
		{
			Capsule = Cap->GetScaledCapsuleRadius();
		}
	}
	return FMath::Clamp(static_cast<double>(Point->ArrivalToleranceCm) - Capsule - 20.0, 10.0, DefaultRadius);
}

void UPrisonActivityComponent::AbortActivity()
{
	PendingMarkerId = NAME_None;
	if (State == EPrisonActivityState::Approaching)
	{
		CancelApproach(TEXT("aborted"));
	}
	else if (State != EPrisonActivityState::Idle)
	{
		++InterruptCount;
		StopMontage(0.f);
		FinishActivity();
	}
	ReleaseMovement();
}

void UPrisonActivityComponent::StartLoop()
{
	UAnimInstance* Anim = GetAnimInstance();
	UAnimSequence* Loop = ActiveDef.LoopAnimation.IsNull() ? nullptr : ActiveDef.LoopAnimation.LoadSynchronous();
	if (!Anim || !Loop)
	{
		if (!bUsingFallbackIdle)
		{
			UE_LOG(LogCyberWarden, Warning, TEXT("Activity %s has no usable loop animation (%s): %s keeps its normal idle pose"), *ActiveActivityId.ToString(),
				*ActiveDef.LoopAnimation.ToString(), *GetNameSafe(GetOwner()));
		}
		bUsingFallbackIdle = true;
		ActiveMontage = nullptr;
		SetState(EPrisonActivityState::Performing);
		return;
	}
	bUsingFallbackIdle = false;
	if (!bRandomInitialized)
	{
		RandomStream.Initialize(static_cast<int32>(GetTypeHash(GetOwner()->GetFName())));
		bRandomInitialized = true;
	}
	if (State == EPrisonActivityState::Entering)
	{
		++HandoffCount; // the enter montage is still fading out: the new montage in the same slot replaces it with a cross-fade, never via the standing pose
	}
	const float StartAt = ActiveDef.bRandomizeLoopStart ? RandomStream.FRand() * Loop->GetPlayLength() : 0.f;
	// The loop blends out over the exit cross-fade when an exit animation follows, otherwise over the plain exit blend-out.
	const float LoopBlendOut = ActiveDef.ExitAnimation.IsNull() ? ActiveDef.GetExitBlendOut() : ActiveDef.GetExitBlendIn();
	ActiveMontage = Anim->PlaySlotAnimationAsDynamicMontage(Loop, ActiveDef.SlotName, ActiveDef.GetLoopBlendIn(), LoopBlendOut, ActiveDef.PlayRate, 100000, -1.f, StartAt);
	SetState(EPrisonActivityState::Performing);
}

void UPrisonActivityComponent::BeginExit()
{
	bReleasePending = false;
	UAnimInstance* Anim = GetAnimInstance();
	UAnimSequence* Exit = ActiveDef.ExitAnimation.IsNull() ? nullptr : ActiveDef.ExitAnimation.LoadSynchronous();
	if (Anim && Exit)
	{
		// Replaces the loop (or the enter animation, after a committed enter) in the slot with a cross-fade.
		ActiveMontage = Anim->PlaySlotAnimationAsDynamicMontage(Exit, ActiveDef.SlotName, ActiveDef.GetExitBlendIn(), ActiveDef.GetExitBlendOut(), ActiveDef.PlayRate, 1);
		PhaseEndAt = Now() + Exit->GetPlayLength() / FMath::Max(ActiveDef.PlayRate, 0.01f);
	}
	else
	{
		StopMontage(ActiveDef.GetExitBlendOut());
		PhaseEndAt = Now() + (bUsingFallbackIdle ? 0.0 : ActiveDef.GetExitBlendOut());
	}
	SetState(EPrisonActivityState::Exiting);
}

void UPrisonActivityComponent::FinishActivity()
{
	StopApproachMove(); // a no-op unless a final approach is still walking
	StopMontage(0.1f);
	bMontagePlaying = false; // diagnostics must not lag behind the state
	SlotNodeWeight = 0.0;
	ReleaseMovement();
	bReleasePending = false;
	bUsingFallbackIdle = false;
	ActiveMarkerId = NAME_None;
	ActiveActivityId = NAME_None;
	SetState(EPrisonActivityState::Idle);
	if (!PendingMarkerId.IsNone())
	{
		const FName Next = PendingMarkerId;
		PendingMarkerId = NAME_None;
		TryStart(Next); // on failure LastFailureReason explains why the queued activity did not start
	}
}

void UPrisonActivityComponent::UpdateDiagnostics()
{
	UAnimInstance* Anim = GetAnimInstance();
	bMontagePlaying = Anim && ActiveMontage && Anim->Montage_IsPlaying(ActiveMontage);
	SlotNodeWeight = (Anim && State != EPrisonActivityState::Idle) ? Anim->GetSlotNodeGlobalWeight(ActiveDef.SlotName) : 0.0;
	if (const AActor* Owner = GetOwner(); Owner && State == EPrisonActivityState::Approaching)
	{
		DistanceToMarker = FVector::Dist2D(Owner->GetActorLocation(), ApproachGoal); // the activity has not started: no start location, no target yaw yet
	}
	else if (Owner && State != EPrisonActivityState::Idle)
	{
		MaxDisplacementCm = FMath::Max(MaxDisplacementCm, FVector::Dist(Owner->GetActorLocation(), ActivityStartLocation));
		YawErrorDegrees = PrisonActivityMath::DeltaYaw(Owner->GetActorRotation().Yaw, TargetYawDegrees);
		if (const AActor* Marker = ResolveMarker(ActiveMarkerId))
		{
			DistanceToMarker = FVector::Dist2D(Owner->GetActorLocation(), Marker->GetActorLocation());
		}
	}
}

void UPrisonActivityComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);
	AActor* Owner = GetOwner();
	if (!Owner || State == EPrisonActivityState::Idle)
	{
		bMontagePlaying = false;
		SlotNodeWeight = 0.0;
		return;
	}
	const double T = Now();
	switch (State)
	{
	case EPrisonActivityState::Approaching:
		TickApproach();
		break;
	case EPrisonActivityState::Aligning:
	{
		const FRotator Current = Owner->GetActorRotation();
		const double NewYaw = PrisonActivityMath::StepYaw(Current.Yaw, TargetYawDegrees, ActiveDef.AlignYawRateDegPerSec * DeltaTime);
		Owner->SetActorRotation(FRotator(Current.Pitch, NewYaw, Current.Roll));
		if (FMath::Abs(PrisonActivityMath::DeltaYaw(NewYaw, TargetYawDegrees)) <= ActiveDef.YawToleranceDegrees)
		{
			UAnimInstance* Anim = GetAnimInstance();
			UAnimSequence* Enter = ActiveDef.EnterAnimation.IsNull() ? nullptr : ActiveDef.EnterAnimation.LoadSynchronous();
			if (Anim && Enter)
			{
				// The enter montage fades out over the cross-fade to the loop, which starts that long before it ends (see the Entering case).
				ActiveMontage = Anim->PlaySlotAnimationAsDynamicMontage(Enter, ActiveDef.SlotName, ActiveDef.GetEnterBlendIn(), ActiveDef.GetLoopBlendIn(), ActiveDef.PlayRate, 1);
				PhaseEndAt = T + Enter->GetPlayLength() / FMath::Max(ActiveDef.PlayRate, 0.01f);
				SetState(EPrisonActivityState::Entering);
			}
			else
			{
				StartLoop();
			}
		}
		break;
	}
	case EPrisonActivityState::Entering:
		// The hand-off is driven by the montage itself (its real remaining time), with the planned end and "no longer playing" as fallbacks:
		// the loop starts one cross-fade before the enter animation ends, so the slot never falls back to the standing pose in between.
		if (PrisonActivityMath::HandoffDue(RemainingEnterSeconds(), ActiveDef.GetLoopBlendIn()) || ActiveMontageFinished() || T >= PhaseEndAt)
		{
			if (bReleasePending && T >= ReleaseAt)
			{
				BeginExit(); // committed enter: the NPC has sat down, now it stands up (enter cross-fades straight into the exit)
			}
			else
			{
				StartLoop();
			}
		}
		break;
	case EPrisonActivityState::Performing:
		if (bReleasePending && T >= ReleaseAt)
		{
			BeginExit();
		}
		else if (!bUsingFallbackIdle)
		{
			UAnimInstance* Anim = GetAnimInstance();
			if (Anim && (!ActiveMontage || !Anim->Montage_IsPlaying(ActiveMontage)))
			{
				++UnexpectedStopCount;
				if (++LoopRestarts <= 3)
				{
					StartLoop(); // something stopped the montage (for example another montage in the slot): restart, bounded
				}
				else
				{
					bUsingFallbackIdle = true;
				}
			}
		}
		break;
	case EPrisonActivityState::Exiting:
		// Movement is restored only when the animation reports that the exit is over (or the safety margin after the planned end has passed).
		if (PrisonActivityMath::ExitComplete(T, PhaseEndAt, ActiveMontageFinished(), ExitSafetyMarginSeconds))
		{
			++CompleteCount;
			FinishActivity();
		}
		break;
	default:
		break;
	}
	UpdateDiagnostics();
}

void UPrisonActivityComponent::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	AbortActivity();
	Super::EndPlay(EndPlayReason);
}
