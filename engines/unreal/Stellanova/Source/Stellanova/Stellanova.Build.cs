using System.IO;
using UnrealBuildTool;

public class Stellanova : ModuleRules
{
	public Stellanova(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
		PublicDependencyModuleNames.AddRange(new string[] { "Core", "CoreUObject", "Engine", "InputCore" });
		// The programs' plugins go with a packaged game (they are made into the project's Stellanova folder).
		if (Target.ProjectFile != null)
		{
			string programs = Path.Combine(Target.ProjectFile.Directory.FullName, "Stellanova");
			RuntimeDependencies.Add(Path.Combine(programs, "*.dll"), StagedFileType.NonUFS);
		}
	}
}
