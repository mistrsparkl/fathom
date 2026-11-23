using System.Diagnostics;
using System.IO;
using UnrealBuildTool;

public class Fathom : ModuleRules
{
	public Fathom(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
		PublicDependencyModuleNames.AddRange(new string[] { "Core", "CoreUObject", "Engine", "InputCore" });
		// Packaged games get the built programs.
		if (Target.ProjectFile != null)
		{
			string programs = Path.Combine(Target.ProjectFile.Directory.FullName, "Fathom");
			MakeChanged(programs);
			RuntimeDependencies.Add(Path.Combine(programs, "*.dll"), StagedFileType.NonUFS);
		}
	}

	// Rebuilds .fathom files newer than their plugin.
	static void MakeChanged(string programs)
	{
		string home = Path.Combine(programs, "home.txt");  // Fathom's folder, then the Python that runs it
		if (!File.Exists(home))
			return;
		string[] lines = File.ReadAllLines(home);
		if (lines.Length < 2)
			return;
		foreach (string script in Directory.GetFiles(programs, "*.fathom"))
		{
			string made = Path.ChangeExtension(script, ".dll");
			if (File.Exists(made) && File.GetLastWriteTimeUtc(made) >= File.GetLastWriteTimeUtc(script))
				continue;
			var how = new ProcessStartInfo(lines[1].Trim(), $"\"{Path.Combine(lines[0].Trim(), "fathom.py")}\" plugin \"{script}\"")
				{ UseShellExecute = false, RedirectStandardOutput = true, RedirectStandardError = true, RedirectStandardInput = true };
			using Process run = Process.Start(how);
			string said = run.StandardOutput.ReadToEnd() + run.StandardError.ReadToEnd();
			run.WaitForExit();
			if (run.ExitCode != 0)
				throw new BuildException($"Fathom: {Path.GetFileName(script)} has mistakes:\n{said}");
		}
	}
}
