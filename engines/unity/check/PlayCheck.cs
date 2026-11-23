// The check scene: Run plays it, Build makes a game.
using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

public static class PlayCheck
{
    static void MakeScene()
    {
        AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
        EditorSceneManager.NewScene(NewSceneSetup.EmptyScene);
        var program = AssetDatabase.LoadAssetAtPath<FathomProgram>("Assets/words.fathom");
        Shape(PrimitiveType.Cube, "Box", new Vector3(8, 0, 0));
        Shape(PrimitiveType.Cube, "Target", Vector3.zero).AddComponent<FathomScript>().program = program;
        Shape(PrimitiveType.Sphere, "Player", new Vector3(0, 4, 0)).AddComponent<Rigidbody>();
        Shape(PrimitiveType.Cube, "Mover", new Vector3(1, 2, 3)).AddComponent<FathomScript>().program = program;
        new GameObject("Report").AddComponent<CheckReport>();
        EditorSceneManager.SaveScene(EditorSceneManager.GetActiveScene(), "Assets/Check.unity");
    }

    static GameObject Shape(PrimitiveType shape, string name, Vector3 at)
    {
        var made = GameObject.CreatePrimitive(shape);
        made.name = name;
        made.transform.position = at;
        return made;
    }

    public static void Run()
    {
        MakeScene();
        File.Delete("check.txt");
        EditorSettings.enterPlayModeOptionsEnabled = true;
        EditorSettings.enterPlayModeOptions = EnterPlayModeOptions.DisableDomainReload | EnterPlayModeOptions.DisableSceneReload;
        EditorApplication.update += () =>
        {
            if (File.Exists("check.txt"))
                EditorApplication.Exit(0);
        };
        EditorApplication.EnterPlaymode();
    }

    public static void Build()
    {
        MakeScene();
        var made = BuildPipeline.BuildPlayer(new[] { "Assets/Check.unity" }, "game/Check.exe", BuildTarget.StandaloneWindows64, BuildOptions.None);
        EditorApplication.Exit(made.summary.result == UnityEditor.Build.Reporting.BuildResult.Succeeded ? 0 : 1);
    }
}
