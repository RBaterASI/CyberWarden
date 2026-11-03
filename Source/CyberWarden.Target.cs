// Copyright Cyber Warden. All Rights Reserved.

using UnrealBuildTool;
using System.Collections.Generic;

public class CyberWardenTarget : TargetRules
{
	public CyberWardenTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Game;
		DefaultBuildSettings = BuildSettingsVersion.V7;
		IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_8;
		ExtraModuleNames.Add("CyberWarden");
	}
}
