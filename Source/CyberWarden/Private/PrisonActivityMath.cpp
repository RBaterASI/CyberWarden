// Copyright Cyber Warden. All Rights Reserved.

#include "PrisonActivityMath.h"

namespace PrisonActivityMath
{
	double NormalizeYaw(double Degrees)
	{
		double D = FMath::Fmod(Degrees, 360.0);
		if (D > 180.0)
		{
			D -= 360.0;
		}
		else if (D <= -180.0)
		{
			D += 360.0;
		}
		return D;
	}

	double DeltaYaw(double FromDegrees, double ToDegrees)
	{
		return NormalizeYaw(ToDegrees - FromDegrees);
	}

	double YawToPoint(double FromX, double FromY, double ToX, double ToY)
	{
		const double DX = ToX - FromX;
		const double DY = ToY - FromY;
		if (FMath::IsNearlyZero(DX) && FMath::IsNearlyZero(DY))
		{
			return 0.0;
		}
		return FMath::RadiansToDegrees(FMath::Atan2(DY, DX));
	}

	double StepYaw(double CurrentDegrees, double TargetDegrees, double MaxDeltaDegrees)
	{
		const double Delta = DeltaYaw(CurrentDegrees, TargetDegrees);
		const double Step = FMath::Clamp(Delta, -FMath::Abs(MaxDeltaDegrees), FMath::Abs(MaxDeltaDegrees));
		return NormalizeYaw(CurrentDegrees + Step);
	}

	float ResolveBlend(float Specific, float Inherited)
	{
		return Specific >= 0.f ? Specific : Inherited;
	}

	double RemainingPlaySeconds(double LengthSeconds, double PositionSeconds, double PlayRate)
	{
		return FMath::Max(0.0, LengthSeconds - PositionSeconds) / FMath::Max(PlayRate, 0.01);
	}

	bool HandoffDue(double RemainingSeconds, double CrossfadeSeconds)
	{
		return RemainingSeconds <= FMath::Max(CrossfadeSeconds, 0.0) + KINDA_SMALL_NUMBER;
	}

	bool ExitComplete(double NowSeconds, double PlannedEndSeconds, bool bAnimationFinished, double SafetyMarginSeconds)
	{
		if (NowSeconds < PlannedEndSeconds)
		{
			return false;
		}
		return bAnimationFinished || NowSeconds >= PlannedEndSeconds + FMath::Max(SafetyMarginSeconds, 0.0);
	}
}
