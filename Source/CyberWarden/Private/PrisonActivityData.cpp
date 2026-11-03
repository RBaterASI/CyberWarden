// Copyright Cyber Warden. All Rights Reserved.

#include "PrisonActivityData.h"
#include "PrisonActivityMath.h"

float FPrisonActivityDefinition::GetEnterBlendIn() const { return PrisonActivityMath::ResolveBlend(EnterBlendInSeconds, BlendInSeconds); }
float FPrisonActivityDefinition::GetLoopBlendIn() const { return PrisonActivityMath::ResolveBlend(LoopBlendInSeconds, BlendInSeconds); }
float FPrisonActivityDefinition::GetExitBlendIn() const { return PrisonActivityMath::ResolveBlend(ExitBlendInSeconds, BlendInSeconds); }
float FPrisonActivityDefinition::GetExitBlendOut() const { return PrisonActivityMath::ResolveBlend(ExitBlendOutSeconds, BlendOutSeconds); }

const FPrisonActivityDefinition* UPrisonActivityData::FindActivity(FName ActivityId) const
{
	return Activities.FindByPredicate([ActivityId](const FPrisonActivityDefinition& A) { return A.Id == ActivityId; });
}

const FPrisonInteractionPoint* UPrisonActivityData::FindPoint(FName MarkerId) const
{
	return Points.FindByPredicate([MarkerId](const FPrisonInteractionPoint& P) { return P.MarkerId == MarkerId; });
}

bool UPrisonActivityData::Validate(TArray<FString>& OutErrors) const
{
	const int32 StartErrors = OutErrors.Num();
	TSet<FName> ActivityIds;
	for (const FPrisonActivityDefinition& A : Activities)
	{
		if (A.Id.IsNone())
		{
			OutErrors.Add(TEXT("activity with no id"));
		}
		else if (ActivityIds.Contains(A.Id))
		{
			OutErrors.Add(FString::Printf(TEXT("duplicate activity id %s"), *A.Id.ToString()));
		}
		ActivityIds.Add(A.Id);
		const FString Name = A.Id.ToString();
		if (A.SlotName.IsNone())
		{
			OutErrors.Add(FString::Printf(TEXT("activity %s: no animation slot"), *Name));
		}
		if (A.BlendInSeconds < 0.f || A.BlendOutSeconds < 0.f)
		{
			OutErrors.Add(FString::Printf(TEXT("activity %s: negative blend time"), *Name));
		}
		if (A.bCommitEnter && A.EnterAnimation.IsNull())
		{
			OutErrors.Add(FString::Printf(TEXT("activity %s: commit enter needs an enter animation"), *Name));
		}
		if (A.PlayRate <= 0.f)
		{
			OutErrors.Add(FString::Printf(TEXT("activity %s: play rate must be > 0"), *Name));
		}
		if (A.AlignYawRateDegPerSec <= 0.f || A.YawToleranceDegrees <= 0.f)
		{
			OutErrors.Add(FString::Printf(TEXT("activity %s: align rate and yaw tolerance must be > 0"), *Name));
		}
	}
	TSet<FName> MarkerIds;
	for (const FPrisonInteractionPoint& P : Points)
	{
		const FString Name = P.MarkerId.ToString();
		if (P.MarkerId.IsNone())
		{
			OutErrors.Add(TEXT("interaction point with no marker id"));
		}
		else if (MarkerIds.Contains(P.MarkerId))
		{
			OutErrors.Add(FString::Printf(TEXT("duplicate interaction point for marker %s"), *Name));
		}
		MarkerIds.Add(P.MarkerId);
		if (!ActivityIds.Contains(P.ActivityId))
		{
			OutErrors.Add(FString::Printf(TEXT("point %s: unknown activity '%s'"), *Name, *P.ActivityId.ToString()));
		}
		if (P.ArrivalToleranceCm <= 0.f)
		{
			OutErrors.Add(FString::Printf(TEXT("point %s: arrival tolerance must be > 0"), *Name));
		}
		if (P.Capacity < 1)
		{
			OutErrors.Add(FString::Printf(TEXT("point %s: capacity must be >= 1"), *Name));
		}
	}
	return OutErrors.Num() == StartErrors;
}

TArray<FString> UPrisonActivityData::ValidateData() const
{
	TArray<FString> Errors;
	Validate(Errors);
	return Errors;
}
