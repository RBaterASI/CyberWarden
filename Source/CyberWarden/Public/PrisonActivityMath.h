// Copyright Cyber Warden. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"

/** Pure yaw helpers for aligning an NPC with an interaction point (unit tested without a world). */
namespace PrisonActivityMath
{
	/** Wraps degrees into (-180, 180]. */
	CYBERWARDEN_API double NormalizeYaw(double Degrees);

	/** Shortest signed rotation from From to To, in (-180, 180]. */
	CYBERWARDEN_API double DeltaYaw(double FromDegrees, double ToDegrees);

	/** World yaw (degrees) of the direction from one XY position to another; 0 when they coincide. */
	CYBERWARDEN_API double YawToPoint(double FromX, double FromY, double ToX, double ToY);

	/** Moves Current towards Target by at most MaxDelta degrees along the shortest way, never overshooting. */
	CYBERWARDEN_API double StepYaw(double CurrentDegrees, double TargetDegrees, double MaxDeltaDegrees);
}
