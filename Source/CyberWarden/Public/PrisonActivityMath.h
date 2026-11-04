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

	/** A per-phase blend time: Specific, or Inherited when Specific is negative ("not set"). */
	CYBERWARDEN_API float ResolveBlend(float Specific, float Inherited);

	/** Real seconds a montage still has to play, from its play length, current position and play rate (never negative). */
	CYBERWARDEN_API double RemainingPlaySeconds(double LengthSeconds, double PositionSeconds, double PlayRate);

	/** The next montage must start now so that it cross-fades in while the current one fades out over CrossfadeSeconds. */
	CYBERWARDEN_API bool HandoffDue(double RemainingSeconds, double CrossfadeSeconds);

	/**
	 * The exit may be declared finished (movement may be restored): the planned end has passed and the animation reports it is done, or
	 * the planned end plus the safety margin has passed (so a montage that never reports completion cannot hold the NPC for ever).
	 */
	CYBERWARDEN_API bool ExitComplete(double NowSeconds, double PlannedEndSeconds, bool bAnimationFinished, double SafetyMarginSeconds);

	/** A final approach may be attempted from this horizontal distance (at most MaxDistanceCm). */
	CYBERWARDEN_API bool ApproachInReach(double DistanceCm, double MaxDistanceCm);

	/** The final position is confirmed: the NPC stands within ToleranceCm of the marker. */
	CYBERWARDEN_API bool ApproachConfirmed(double DistanceCm, double ToleranceCm);

	/** The final approach has run for TimeoutSeconds without finishing. */
	CYBERWARDEN_API bool ApproachTimedOut(double NowSeconds, double StartedAtSeconds, double TimeoutSeconds);

	/** A point whose final approach failed at FailedAtSeconds is not retried until LockoutSeconds have passed. */
	CYBERWARDEN_API bool ApproachLockedOut(double NowSeconds, double FailedAtSeconds, double LockoutSeconds);
}
