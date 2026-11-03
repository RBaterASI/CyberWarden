// Copyright Cyber Warden. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Engine/DataAsset.h"
#include "PrisonActivityData.generated.h"

class UAnimSequence;

/** How an NPC orients itself at an interaction point. */
UENUM(BlueprintType)
enum class EPrisonFacingMode : uint8
{
	/** Keep the current orientation. */
	None,
	/** Face a fixed world yaw (degrees). */
	Yaw,
	/** Face a world point (for example the centre of a TV or a table). */
	Point
};

/**
 * What an activity looks like. Pure data: nothing here is specific to an NPC or a location. Every animation is optional;
 * a missing one degrades gracefully (the NPC simply keeps its normal idle pose).
 */
USTRUCT(BlueprintType)
struct CYBERWARDEN_API FPrisonActivityDefinition
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Activity")
	FName Id;

	/** Played once after the NPC has aligned (for example sitting down). Optional. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Activity")
	TSoftObjectPtr<UAnimSequence> EnterAnimation;

	/** Looped for the whole activity. Optional (empty = keep the normal idle). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Activity")
	TSoftObjectPtr<UAnimSequence> LoopAnimation;

	/** Played once when the activity ends (for example standing up). Optional. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Activity")
	TSoftObjectPtr<UAnimSequence> ExitAnimation;

	/** Animation slot of the NPC animation Blueprint that plays the activity (ABP_PrisonNPC has "DefaultSlot"). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Activity")
	FName SlotName = TEXT("DefaultSlot");

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Activity", meta = (ClampMin = "0.0"))
	float BlendInSeconds = 0.3f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Activity", meta = (ClampMin = "0.0"))
	float BlendOutSeconds = 0.3f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Activity", meta = (ClampMin = "0.01"))
	float PlayRate = 1.f;

	/** Start the loop at a random point so NPCs sharing an activity do not animate in lockstep. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Activity")
	bool bRandomizeLoopStart = true;

	/** Turn rate while aligning to the interaction point. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Activity", meta = (ClampMin = "1.0"))
	float AlignYawRateDegPerSec = 120.f;

	/** The NPC may start the activity once its yaw is within this many degrees of the target. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Activity", meta = (ClampMin = "0.1"))
	float YawToleranceDegrees = 3.f;
};

/** A place where an activity happens, keyed by the destination marker id used in the schedule. Independent of any NPC. */
USTRUCT(BlueprintType)
struct CYBERWARDEN_API FPrisonInteractionPoint
{
	GENERATED_BODY()

	/** Marker id ("MarkerId:<id>" tag in the level) that the schedule sends NPCs to. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Interaction")
	FName MarkerId;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Interaction")
	FName ActivityId;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Interaction")
	EPrisonFacingMode FacingMode = EPrisonFacingMode::None;

	/** World yaw in degrees (FacingMode = Yaw). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Interaction")
	float FacingYawDegrees = 0.f;

	/** World point to face (FacingMode = Point). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Interaction")
	FVector FacingPoint = FVector::ZeroVector;

	/**
	 * The activity can only start when the NPC stands within this horizontal distance of the marker. The activity never moves the
	 * NPC to the marker (no snapping, no teleporting): getting closer is navigation's job.
	 */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Interaction", meta = (ClampMin = "1.0"))
	float ArrivalToleranceCm = 150.f;

	/** How many NPCs may use the point at once (validated now, enforced when shared points are added). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Interaction", meta = (ClampMin = "1"))
	int32 Capacity = 1;
};

/**
 * Activity definitions and interaction points of a sector. Generated from Docs/Layout/S01_LW_F1_activities.json by
 * Tools/ConfigureActivities.py; the JSON stays the source of truth.
 */
UCLASS(BlueprintType)
class CYBERWARDEN_API UPrisonActivityData : public UDataAsset
{
	GENERATED_BODY()

public:
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Activities")
	TArray<FPrisonActivityDefinition> Activities;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Activities")
	TArray<FPrisonInteractionPoint> Points;

	const FPrisonActivityDefinition* FindActivity(FName ActivityId) const;
	const FPrisonInteractionPoint* FindPoint(FName MarkerId) const;

	/** Structural validation; true when there are no errors. */
	bool Validate(TArray<FString>& OutErrors) const;

	UFUNCTION(BlueprintCallable, Category = "Activities")
	TArray<FString> ValidateData() const;
};
