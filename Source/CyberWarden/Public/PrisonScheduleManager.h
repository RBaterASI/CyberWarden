// Copyright Cyber Warden. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "PrisonScheduleManager.generated.h"

class UPrisonScheduleData;

DECLARE_DYNAMIC_MULTICAST_DELEGATE_ThreeParams(FOnPrisonPeriodChanged, int32, OldPeriodIndex, int32, NewPeriodIndex, const FString&, NewPeriodName);

/**
 * The prison clock and institutional schedule for one sector (M2.2 proof of concept: clock only).
 *
 * The accumulated game time (GameSecondsTotal) is the single authoritative value: pausing or changing TimeScale never
 * resets it. Period lookup uses a 48-slot half-hour table derived from PeriodStartHours; slots before the first period
 * belong to the last one (overnight Lockdown). Runtime state is readable from Blueprints and Python; the control
 * functions below are the test-friendly time controls.
 */
UCLASS(BlueprintType, Blueprintable)
class CYBERWARDEN_API APrisonScheduleManager : public AActor
{
	GENERATED_BODY()

public:
	APrisonScheduleManager();

	// ---- Clock configuration ----------------------------------------------------------------------------------
	/** Game seconds per real second (30 = default, 120 = accelerated development testing). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Clock", meta = (ClampMin = "0.0"))
	double TimeScale = 30.0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Clock")
	bool bPaused = false;

	/** Unwrapped accumulated game seconds. Its default is the start time (21600 = 06:00). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Clock")
	double GameSecondsTotal = 21600.0;

	/** Maximum per-NPC departure stagger in game minutes (used by NPC logic in a later stage). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Clock")
	double StaggerMaxGameMinutes = 5.0;

	// ---- Schedule configuration -------------------------------------------------------------------------------
	/** Sector schedule data (periods + per-NPC assignments). When set, PeriodIds/PeriodNames/PeriodStartHours are taken from it. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Schedule")
	TObjectPtr<UPrisonScheduleData> ScheduleData;

	/** Derived from ScheduleData (or "P0", "P1" ... when there is none): the id of each period, parallel to PeriodNames. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Schedule")
	TArray<FName> PeriodIds;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Schedule")
	TArray<FString> PeriodNames;

	/** Ascending period start times in hours, on the half-hour grid. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Schedule")
	TArray<double> PeriodStartHours;

	/** Derived: half-hour slot (0..47) -> period index. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Schedule")
	TArray<int32> SlotToPeriod;

	// ---- Runtime state ----------------------------------------------------------------------------------------
	/** GameSecondsTotal wrapped to 0..86400. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Runtime")
	double ClockSeconds = 21600.0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Runtime")
	double CurrentHour = 6.0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Runtime")
	int32 CurrentPeriodIndex = 0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Runtime")
	FString CurrentPeriodName;

	/** Day number, 1-based, increasing every midnight. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Runtime")
	int32 DayNumber = 1;

	/** Number of period changes since play began. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Runtime")
	int32 PeriodChangeCount = 0;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Runtime")
	int32 LastPeriodIndex = 0;

	UPROPERTY(BlueprintAssignable, Category = "Runtime")
	FOnPrisonPeriodChanged OnPeriodChanged;

	// ---- Time controls (also used by automated tests) -----------------------------------------------------------
	UFUNCTION(BlueprintCallable, CallInEditor, Category = "Clock")
	void PauseClock();

	UFUNCTION(BlueprintCallable, CallInEditor, Category = "Clock")
	void ResumeClock();

	UFUNCTION(BlueprintCallable, Category = "Clock")
	void SetTimeScale(double NewTimeScale);

	/** Sets the time of day (hours 0..24) of the CURRENT day; keeps the day number. */
	UFUNCTION(BlueprintCallable, Category = "Clock")
	void SetTimeOfDayHours(double Hours);

	/** Sets the accumulated game seconds directly (may exceed one day). */
	UFUNCTION(BlueprintCallable, Category = "Clock")
	void SetGameSecondsTotal(double NewTotalSeconds);

	/** Jumps to the start of a period of the current day (plus an optional offset in game seconds, negative to land just before it). */
	UFUNCTION(BlueprintCallable, Category = "Clock")
	bool JumpToPeriod(int32 PeriodIndex, double OffsetGameSeconds = 0.0);

	/** Advances the clock by game seconds (ignores pause and TimeScale): deterministic stepping for tests. */
	UFUNCTION(BlueprintCallable, Category = "Clock")
	void AdvanceGameSeconds(double GameSeconds);

	UFUNCTION(BlueprintPure, Category = "Clock")
	FString GetClockString() const;

	/** Rebuilds SlotToPeriod from PeriodStartHours. Returns false (and leaves it empty) if the periods are invalid. */
	UFUNCTION(BlueprintCallable, CallInEditor, Category = "Schedule")
	bool RebuildSlotTable();

	virtual void Tick(float DeltaSeconds) override;

protected:
	virtual void BeginPlay() override;
	virtual void OnConstruction(const FTransform& Transform) override;
#if WITH_EDITOR
	virtual void PostEditChangeProperty(FPropertyChangedEvent& PropertyChangedEvent) override;
#endif

private:
	/** Recomputes the derived runtime state from GameSecondsTotal; fires OnPeriodChanged when the period changed. */
	void Refresh(bool bNotify);
};
