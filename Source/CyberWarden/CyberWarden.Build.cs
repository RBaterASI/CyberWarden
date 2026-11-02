// Copyright Cyber Warden. All Rights Reserved.

using UnrealBuildTool;

public class CyberWarden : ModuleRules
{
	public CyberWarden(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

		// Proof of concept (prison clock) needs nothing beyond the basic engine modules.
		// StateTree / AI modules are added when the NPC schedule nodes are migrated.
		PublicDependencyModuleNames.AddRange(new string[] { "Core", "CoreUObject", "Engine" });
	}
}
