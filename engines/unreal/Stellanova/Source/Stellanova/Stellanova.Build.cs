using System.Diagnostics;
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
			MakeChanged(programs);
			RuntimeDependencies.Add(Path.Combine(programs, "*.dll"), StagedFileType.NonUFS);
		}
	}

	// Each .stella file newer than its plugin is made again first, so a packaged game has every program as it is now.
	static void MakeChanged(string programs)
	{
		string home = Path.Combine(programs, "home.txt");  // Stellanova's folder, then the Python that runs it
		if (!File.Exists(home))
			return;
		string[] lines = File.ReadAllLines(home);
		if (lines.Length < 2)
			return;
		foreach (string script in Directory.GetFiles(programs, "*.stella"))
		{
			string made = Path.ChangeExtension(script, ".dll");
			if (File.Exists(made) && File.GetLastWriteTimeUtc(made) >= File.GetLastWriteTimeUtc(script))
				continue;
			var how = new ProcessStartInfo(lines[1].Trim(), $"\"{Path.Combine(lines[0].Trim(), "stellanova.py")}\" plugin \"{script}\"")
				{ UseShellExecute = false, RedirectStandardOutput = true, RedirectStandardError = true, RedirectStandardInput = true };
			using Process run = Process.Start(how);
			string said = run.StandardOutput.ReadToEnd() + run.StandardError.ReadToEnd();
			run.WaitForExit();
			if (run.ExitCode != 0)
				throw new BuildException($"Stellanova: {Path.GetFileName(script)} has mistakes:\n{said}");
		}
	}
}
