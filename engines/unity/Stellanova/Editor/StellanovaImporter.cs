// Builds each .stella file into StreamingAssets/Stellanova when saved.
using System.Diagnostics;
using System.IO;
using UnityEditor;
using UnityEditor.AssetImporters;
using UnityEngine;

[ScriptedImporter(1, "stella")]
public class StellanovaImporter : ScriptedImporter
{
    public override void OnImportAsset(AssetImportContext ctx)
    {
        var program = ScriptableObject.CreateInstance<StellanovaProgram>();
        program.pluginName = Path.GetFileNameWithoutExtension(ctx.assetPath);
        program.words = File.ReadAllText(ctx.assetPath);
        ctx.AddObjectToAsset("program", program);
        ctx.SetMainObject(program);

        string problem = Build(Path.GetFullPath(ctx.assetPath), program.pluginName);
        if (problem != null)
            ctx.LogImportError($"Stellanova: {problem}");
    }

    // Makes the plugin; the mistake if it can't be made, or null.
    static string Build(string script, string name)
    {
        string home = Home();
        if (home == null)
            return "I can't find Stellanova. Run 'stellanova unity <this project's folder>' again, or put the folder holding stellanova.py in Assets/Stellanova/home.txt.";
        bool windows = Application.platform == RuntimePlatform.WindowsEditor;
        var run = new ProcessStartInfo(windows ? "py" : "python3", (windows ? "-3 " : "") + $"\"{Path.Combine(home, "stellanova.py")}\" plugin \"{script}\"")
        {
            UseShellExecute = false, RedirectStandardOutput = true, RedirectStandardError = true, CreateNoWindow = true,
            WorkingDirectory = Path.GetDirectoryName(script),
        };
        string said;
        int code;
        try
        {
            using (var p = Process.Start(run))
            {
                said = (p.StandardOutput.ReadToEnd() + p.StandardError.ReadToEnd()).Trim();
                p.WaitForExit();
                code = p.ExitCode;
            }
        }
        catch (System.ComponentModel.Win32Exception)
        {
            return windows ? "Python 3 isn't installed (it gives the 'py' command): get it from python.org." : "python3 isn't installed.";
        }
        if (code != 0)
            return said;
        string made = Path.ChangeExtension(script, windows ? ".dll" : ".so");
        string folder = Path.Combine(Application.streamingAssetsPath, "Stellanova");
        Directory.CreateDirectory(folder);
        string kept = Path.Combine(folder, name + Path.GetExtension(made));
        File.Copy(made, kept, true);
        File.Delete(made);
        return null;
    }

    static string Home()
    {
        string note = Path.Combine(Application.dataPath, "Stellanova", "home.txt");
        string home = File.Exists(note) ? File.ReadAllText(note).Trim() : System.Environment.GetEnvironmentVariable("STELLANOVA_HOME");
        return home != null && File.Exists(Path.Combine(home, "stellanova.py")) ? home : null;
    }
}

// When play stops, let the programs go.
[InitializeOnLoad]
static class StellanovaPlayMode
{
    static StellanovaPlayMode()
    {
        EditorApplication.playModeStateChanged += change =>
        {
            if (change == PlayModeStateChange.EnteredEditMode)
                StellanovaPlugin.UnloadAll();
        };
    }
}
