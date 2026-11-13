using System.IO;
using UnrealBuildTool;

public class StellanovaWorld : ModuleRules
{
	public StellanovaWorld(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
		bEnableExceptions = true;  // Stellanova's problems are C++ exceptions, caught by 'try:'
		bUseUnity = false;
		CppCompileWarningSettings.ShadowVariableWarningLevel = WarningLevel.Off;
		CppCompileWarningSettings.UndefinedIdentifierWarningLevel = WarningLevel.Off;
		PublicDefinitions.Add("STELLANOVA_IN_UNREAL=1");
		PublicIncludePaths.Add(ModuleDirectory);
		PublicIncludePaths.Add(Path.Combine(ModuleDirectory, "Generated"));
		PublicDependencyModuleNames.AddRange(new string[] { "Core", "CoreUObject", "Engine", "InputCore", "Slate", "SlateCore" });
	}
}
