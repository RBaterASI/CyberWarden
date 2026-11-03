// Copyright Cyber Warden. All Rights Reserved.

#include "PrisonClockMath.h"

namespace PrisonClockMath
{
	double WrapSeconds(double TotalSeconds)
	{
		double Wrapped = FMath::Fmod(TotalSeconds, SecondsPerDay);
		if (Wrapped < 0.0)
		{
			Wrapped += SecondsPerDay;
		}
		return Wrapped;
	}

	int32 SlotOf(double TotalSeconds)
	{
		return FMath::Clamp(static_cast<int32>(FMath::FloorToDouble(WrapSeconds(TotalSeconds) / SlotSeconds)), 0, SlotCount - 1);
	}

	TArray<int32> BuildSlotTable(const TArray<double>& PeriodStartHours)
	{
		TArray<int32> Table;
		if (PeriodStartHours.Num() < 1)
		{
			return Table;
		}
		for (int32 i = 0; i < PeriodStartHours.Num(); ++i)
		{
			const double Hours = PeriodStartHours[i];
			const bool bOnGrid = FMath::Fmod(Hours * 3600.0, SlotSeconds) == 0.0;
			if (Hours < 0.0 || Hours >= 24.0 || !bOnGrid || (i > 0 && Hours <= PeriodStartHours[i - 1]))
			{
				return TArray<int32>();
			}
		}
		Table.SetNum(SlotCount);
		for (int32 Slot = 0; Slot < SlotCount; ++Slot)
		{
			const double SlotStartHours = Slot * SlotSeconds / 3600.0;
			int32 Index = PeriodStartHours.Num() - 1; // overnight carry-over from the last period
			for (int32 i = 0; i < PeriodStartHours.Num(); ++i)
			{
				if (PeriodStartHours[i] <= SlotStartHours)
				{
					Index = i;
				}
			}
			Table[Slot] = Index;
		}
		return Table;
	}

	int32 PeriodAt(const TArray<int32>& SlotTable, double TotalSeconds)
	{
		return SlotTable.Num() == SlotCount ? SlotTable[SlotOf(TotalSeconds)] : INDEX_NONE;
	}

	FString FormatClock(double TotalSeconds)
	{
		const int32 S = static_cast<int32>(WrapSeconds(TotalSeconds));
		return FString::Printf(TEXT("%02d:%02d:%02d"), S / 3600, (S % 3600) / 60, S % 60);
	}
}
