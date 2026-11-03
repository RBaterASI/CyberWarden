// Copyright Cyber Warden. All Rights Reserved.

using UnrealBuildTool;
using System.Collections.Generic;

public class CyberWardenEditorTarget : TargetRules
{
	public CyberWardenEditorTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Editor;
		DefaultBuildSettings = BuildSettingsVersion.V7;
		IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_8;
		ExtraModuleNames.Add("CyberWarden");
	}
}
