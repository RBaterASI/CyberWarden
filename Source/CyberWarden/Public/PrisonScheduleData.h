// Copyright Cyber Warden. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Engine/DataAsset.h"
#include "PrisonScheduleData.generated.h"

/** One institutional period (Wake-up, Breakfast ...). Order must be ascending by StartHours. */
USTRUCT(BlueprintType)
struct CYBERWARDEN_API FPrisonPeriodDef
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Schedule")
	FName Id;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Schedule")
	FString Name;

	/** Start time in hours on the half-hour grid (0..24). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Schedule")
	double StartHours = 0.0;
};

/** What one NPC does during one period: ordered candidate stops (marker ids) and the idle range in REAL seconds. */
USTRUCT(BlueprintType)
struct CYBERWARDEN_API FPrisonPeriodAssignment
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Schedule")
	FName PeriodId;

	/** Marker ids as tagged in the level ("MarkerId:<id>"). All must be NavDest:Yes markers. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Schedule")
	TArray<FName> StopMarkerIds;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Schedule")
	double IdleMin = 5.0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Schedule")
	double IdleMax = 10.0;
};

/** The full daily schedule of one NPC. */
USTRUCT(BlueprintType)
struct CYBERWARDEN_API FPrisonNpcSchedule
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Schedule")
	FName NpcId;

	/** 0..1: fraction of the manager's StaggerMaxGameMinutes this NPC waits after a period change (deterministic). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Schedule")
	double StaggerFraction = 0.0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Schedule")
	TArray<FPrisonPeriodAssignment> Periods;
};

/**
 * The single in-engine representation of a sector's periods and per-NPC assignments. It is generated from
 * Docs/Layout/S01_LW_F1_schedule.json by Tools/ConfigureSchedule.py; the JSON remains the source of truth.
 * The schedule manager takes its periods from this asset and NPC schedule components read their assignments from it.
 */
UCLASS(BlueprintType)
class CYBERWARDEN_API UPrisonScheduleData : public UDataAsset
{
	GENERATED_BODY()

public:
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Schedule")
	FName SectorId;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Schedule")
	TArray<FPrisonPeriodDef> Periods;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Schedule")
	TArray<FPrisonNpcSchedule> Npcs;

	const FPrisonNpcSchedule* FindNpc(FName NpcId) const;
	const FPrisonPeriodAssignment* FindAssignment(FName NpcId, FName PeriodId) const;

	/** Structural validation. Returns true when there are no errors; markers are validated against the level elsewhere. */
	bool Validate(TArray<FString>& OutErrors) const;

	/** Blueprint/Python friendly validation: returns the list of errors (empty = valid). */
	UFUNCTION(BlueprintCallable, Category = "Schedule")
	TArray<FString> ValidateData() const;
};
