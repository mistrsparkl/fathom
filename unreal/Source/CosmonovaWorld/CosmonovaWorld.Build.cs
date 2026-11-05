using System.IO;
using UnrealBuildTool;

public class CosmonovaWorld : ModuleRules
{
	public CosmonovaWorld(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
		bEnableExceptions = true;  // Cosmonova's problems are C++ exceptions, caught by 'try:'
		bUseUnity = false;
		CppCompileWarningSettings.ShadowVariableWarningLevel = WarningLevel.Off;
		CppCompileWarningSettings.UndefinedIdentifierWarningLevel = WarningLevel.Off;
		PublicDefinitions.Add("COSMONOVA_IN_UNREAL=1");
		PublicIncludePaths.Add(ModuleDirectory);
		PublicIncludePaths.Add(Path.Combine(ModuleDirectory, "Generated"));
		PublicDependencyModuleNames.AddRange(new string[] { "Core", "CoreUObject", "Engine", "InputCore", "Slate", "SlateCore" });
	}
}
