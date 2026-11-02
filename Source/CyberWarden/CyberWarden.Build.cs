// Copyright Cyber Warden. All Rights Reserved.

using UnrealBuildTool;

public class CyberWarden : ModuleRules
{
	public CyberWarden(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

		// Proof of concept (prison clock) needs nothing beyond the basic engine modules.
		// StateTree / AI modules are added when the NPC schedule nodes are migrated.
		// Crash A/B experiment: CW_NO_TESTS=1 compiles the native automation tests out (default: tests are built).
		if (System.Environment.GetEnvironmentVariable("CW_NO_TESTS") == "1")
		{
			PublicDefinitions.Add("CW_EXCLUDE_AUTOMATION_TESTS=1");
		}

		PublicDependencyModuleNames.AddRange(new string[] { "Core", "CoreUObject", "Engine", "AIModule", "GameplayTasks", "StateTreeModule", "GameplayStateTreeModule", "PropertyBindingUtils" });
	}
}
