// Copyright Cyber Warden. All Rights Reserved.

#include "PrisonActivityComponent.h"
#include "PrisonActivityMath.h"
#include "PrisonScheduleManager.h"
#include "CyberWarden.h"
#include "Animation/AnimInstance.h"
#include "Animation/AnimMontage.h"
#include "Animation/AnimSequence.h"
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
	return ActiveDef.BlendOutSeconds;
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
	if (Dist > Point->ArrivalToleranceCm)
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
	const FVector Loc = Owner->GetActorLocation();
	switch (Point->FacingMode)
	{
	case EPrisonFacingMode::Yaw:
		TargetYawDegrees = PrisonActivityMath::NormalizeYaw(Point->FacingYawDegrees);
		break;
	case EPrisonFacingMode::Point:
		TargetYawDegrees = PrisonActivityMath::YawToPoint(Loc.X, Loc.Y, Point->FacingPoint.X, Point->FacingPoint.Y);
		break;
	default:
		TargetYawDegrees = PrisonActivityMath::NormalizeYaw(Owner->GetActorRotation().Yaw);
		break;
	}
	++StartCount;
	LastFailureReason.Empty();
	HoldMovement();
	SetState(EPrisonActivityState::Aligning);
	return true;
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
		if (State == EPrisonActivityState::Aligning)
		{
			++InterruptCount;
			FinishActivity();
		}
		else if (State == EPrisonActivityState::Entering)
		{
			++InterruptCount;
			StopMontage(ActiveDef.BlendOutSeconds);
			PhaseEndAt = Now() + ActiveDef.BlendOutSeconds;
			SetState(EPrisonActivityState::Exiting);
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
	case EPrisonActivityState::Aligning:
		++InterruptCount;
		FinishActivity();
		return 0.0;
	case EPrisonActivityState::Entering:
		++InterruptCount;
		StopMontage(ActiveDef.BlendOutSeconds);
		PhaseEndAt = Now() + ActiveDef.BlendOutSeconds;
		SetState(EPrisonActivityState::Exiting);
		return ActiveDef.BlendOutSeconds;
	case EPrisonActivityState::Performing:
		if (!bReleasePending)
		{
			bReleasePending = true;
			ReleaseAt = Now() + ReleaseGraceSeconds;
		}
		return FMath::Max(0.0, ReleaseAt - Now()) + ExitSeconds();
	case EPrisonActivityState::Exiting:
		return FMath::Max(0.0, PhaseEndAt - Now());
	}
	return 0.0;
}

void UPrisonActivityComponent::AbortActivity()
{
	PendingMarkerId = NAME_None;
	if (State != EPrisonActivityState::Idle)
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
	const float StartAt = ActiveDef.bRandomizeLoopStart ? RandomStream.FRand() * Loop->GetPlayLength() : 0.f;
	ActiveMontage = Anim->PlaySlotAnimationAsDynamicMontage(Loop, ActiveDef.SlotName, ActiveDef.BlendInSeconds, ActiveDef.BlendOutSeconds, ActiveDef.PlayRate, 100000, -1.f, StartAt);
	SetState(EPrisonActivityState::Performing);
}

void UPrisonActivityComponent::BeginExit()
{
	bReleasePending = false;
	UAnimInstance* Anim = GetAnimInstance();
	UAnimSequence* Exit = ActiveDef.ExitAnimation.IsNull() ? nullptr : ActiveDef.ExitAnimation.LoadSynchronous();
	if (Anim && Exit)
	{
		ActiveMontage = Anim->PlaySlotAnimationAsDynamicMontage(Exit, ActiveDef.SlotName, ActiveDef.BlendInSeconds, ActiveDef.BlendOutSeconds, ActiveDef.PlayRate, 1);
		PhaseEndAt = Now() + Exit->GetPlayLength() / FMath::Max(ActiveDef.PlayRate, 0.01f);
	}
	else
	{
		StopMontage(ActiveDef.BlendOutSeconds);
		PhaseEndAt = Now() + (bUsingFallbackIdle ? 0.0 : ActiveDef.BlendOutSeconds);
	}
	SetState(EPrisonActivityState::Exiting);
}

void UPrisonActivityComponent::FinishActivity()
{
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
	if (const AActor* Owner = GetOwner(); Owner && State != EPrisonActivityState::Idle)
	{
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
				ActiveMontage = Anim->PlaySlotAnimationAsDynamicMontage(Enter, ActiveDef.SlotName, ActiveDef.BlendInSeconds, ActiveDef.BlendOutSeconds, ActiveDef.PlayRate, 1);
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
		if (T >= PhaseEndAt)
		{
			StartLoop();
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
		if (T >= PhaseEndAt)
		{
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
