using System.IO;
using UnrealBuildTool;

public class FathomWorld : ModuleRules
{
	public FathomWorld(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
		bEnableExceptions = true;  // Fathom's problems are C++ exceptions, caught by 'try:'
		bUseUnity = false;
		CppCompileWarningSettings.ShadowVariableWarningLevel = WarningLevel.Off;
		CppCompileWarningSettings.UndefinedIdentifierWarningLevel = WarningLevel.Off;
		PublicDefinitions.Add("FATHOM_IN_UNREAL=1");
		PublicIncludePaths.Add(ModuleDirectory);
		PublicIncludePaths.Add(Path.Combine(ModuleDirectory, "Generated"));
		PublicDependencyModuleNames.AddRange(new string[] { "Core", "CoreUObject", "Engine", "InputCore", "Slate", "SlateCore" });
	}
}
