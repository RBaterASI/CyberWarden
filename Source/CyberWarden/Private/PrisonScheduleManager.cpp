// Copyright Cyber Warden. All Rights Reserved.

#include "PrisonScheduleManager.h"
#include "PrisonClockMath.h"
#include "PrisonScheduleData.h"
#include "CyberWarden.h"
#include "Components/SceneComponent.h"

APrisonScheduleManager::APrisonScheduleManager()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.bStartWithTickEnabled = true;
	SetRootComponent(CreateDefaultSubobject<USceneComponent>(TEXT("Root")));
	Tags.Add(TEXT("S01F1ScheduleManager"));

	// Defaults match Docs/Layout/S01_LW_F1_schedule.json (the JSON stays the source of truth; Tools/ConfigureSchedule.py writes it).
	PeriodNames = { TEXT("Wake-up"), TEXT("Breakfast"), TEXT("Work and activities"), TEXT("Lunch"),
		TEXT("Recreation"), TEXT("Evening meal"), TEXT("Free time"), TEXT("Lockdown") };
	PeriodStartHours = { 6.0, 7.0, 8.0, 12.0, 13.0, 18.0, 19.0, 21.0 };
	RebuildSlotTable();
	Refresh(false);
	LastPeriodIndex = CurrentPeriodIndex;
}

bool APrisonScheduleManager::RebuildSlotTable()
{
	if (ScheduleData && ScheduleData->Periods.Num() > 0)
	{
		PeriodIds.Reset();
		PeriodNames.Reset();
		PeriodStartHours.Reset();
		for (const FPrisonPeriodDef& P : ScheduleData->Periods)
		{
			PeriodIds.Add(P.Id);
			PeriodNames.Add(P.Name);
			PeriodStartHours.Add(P.StartHours);
		}
	}
	else if (PeriodIds.Num() != PeriodNames.Num())
	{
		PeriodIds.Reset();
		for (int32 i = 0; i < PeriodNames.Num(); ++i)
		{
			PeriodIds.Add(FName(*FString::Printf(TEXT("P%d"), i)));
		}
	}
	SlotToPeriod = PrisonClockMath::BuildSlotTable(PeriodStartHours);
	if (SlotToPeriod.Num() == 0)
	{
		UE_LOG(LogCyberWarden, Warning, TEXT("%s: invalid period start hours (must ascend on the half-hour grid within 0..24)"), *GetName());
		return false;
	}
	return true;
}

void APrisonScheduleManager::Refresh(bool bNotify)
{
	ClockSeconds = PrisonClockMath::WrapSeconds(GameSecondsTotal);
	CurrentHour = ClockSeconds / 3600.0;
	DayNumber = FMath::Max(0, static_cast<int32>(FMath::FloorToDouble(GameSecondsTotal / PrisonClockMath::SecondsPerDay))) + 1;
	const int32 NewIndex = PrisonClockMath::PeriodAt(SlotToPeriod, GameSecondsTotal);
	if (NewIndex == INDEX_NONE)
	{
		return;
	}
	CurrentPeriodIndex = NewIndex;
	CurrentPeriodName = PeriodNames.IsValidIndex(NewIndex) ? PeriodNames[NewIndex] : FString::Printf(TEXT("Period %d"), NewIndex);
	if (NewIndex != LastPeriodIndex)
	{
		const int32 Old = LastPeriodIndex;
		LastPeriodIndex = NewIndex;
		++PeriodChangeCount;
		if (bNotify)
		{
			OnPeriodChanged.Broadcast(Old, NewIndex, CurrentPeriodName);
		}
	}
}

void APrisonScheduleManager::BeginPlay()
{
	Super::BeginPlay();
	RebuildSlotTable();
	Refresh(false);
	LastPeriodIndex = CurrentPeriodIndex; // no spurious change at start
	PeriodChangeCount = 0;
}

void APrisonScheduleManager::OnConstruction(const FTransform& Transform)
{
	Super::OnConstruction(Transform);
	RebuildSlotTable();
	Refresh(false);
	LastPeriodIndex = CurrentPeriodIndex;
}

#if WITH_EDITOR
void APrisonScheduleManager::PostEditChangeProperty(FPropertyChangedEvent& PropertyChangedEvent)
{
	Super::PostEditChangeProperty(PropertyChangedEvent);
	RebuildSlotTable();
	Refresh(false);
	LastPeriodIndex = CurrentPeriodIndex;
}
#endif

void APrisonScheduleManager::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	if (!bPaused)
	{
		GameSecondsTotal += static_cast<double>(DeltaSeconds) * TimeScale;
	}
	Refresh(true);
}

void APrisonScheduleManager::PauseClock()
{
	bPaused = true;
}

void APrisonScheduleManager::ResumeClock()
{
	bPaused = false;
}

void APrisonScheduleManager::SetTimeScale(double NewTimeScale)
{
	TimeScale = FMath::Max(0.0, NewTimeScale); // GameSecondsTotal is untouched: changing the scale never resets the time
}

void APrisonScheduleManager::SetTimeOfDayHours(double Hours)
{
	const double DayStart = FMath::FloorToDouble(GameSecondsTotal / PrisonClockMath::SecondsPerDay) * PrisonClockMath::SecondsPerDay;
	SetGameSecondsTotal(DayStart + FMath::Clamp(Hours, 0.0, 24.0) * 3600.0);
}

void APrisonScheduleManager::SetGameSecondsTotal(double NewTotalSeconds)
{
	GameSecondsTotal = NewTotalSeconds;
	Refresh(true);
}

bool APrisonScheduleManager::JumpToPeriod(int32 PeriodIndex, double OffsetGameSeconds)
{
	if (!PeriodStartHours.IsValidIndex(PeriodIndex))
	{
		return false;
	}
	const double DayStart = FMath::FloorToDouble(GameSecondsTotal / PrisonClockMath::SecondsPerDay) * PrisonClockMath::SecondsPerDay;
	SetGameSecondsTotal(DayStart + PeriodStartHours[PeriodIndex] * 3600.0 + OffsetGameSeconds);
	return true;
}

void APrisonScheduleManager::AdvanceGameSeconds(double GameSeconds)
{
	SetGameSecondsTotal(GameSecondsTotal + GameSeconds);
}

FString APrisonScheduleManager::GetClockString() const
{
	return PrisonClockMath::FormatClock(GameSecondsTotal);
}
