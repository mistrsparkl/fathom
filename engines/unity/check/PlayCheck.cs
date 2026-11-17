using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

public static class PlayCheck
{
    static string said = "";
    static int frames;

    public static void Run()
    {
        Application.logMessageReceived += (m, s, t) => said += t + ": " + m + "\n";
        AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
        EditorSceneManager.NewScene(NewSceneSetup.EmptyScene);
        var coin = GameObject.CreatePrimitive(PrimitiveType.Cube);
        coin.name = "Coin";
        coin.AddComponent<StellanovaScript>().program = AssetDatabase.LoadAssetAtPath<StellanovaProgram>("Assets/coin.stella");
        var player = GameObject.CreatePrimitive(PrimitiveType.Sphere);
        player.name = "Player";
        player.transform.position = new Vector3(0, 4, 0);
        player.AddComponent<Rigidbody>();
        EditorSettings.enterPlayModeOptionsEnabled = true;
        EditorSettings.enterPlayModeOptions = EnterPlayModeOptions.DisableDomainReload | EnterPlayModeOptions.DisableSceneReload;
        EditorApplication.update += Watch;
        EditorApplication.EnterPlaymode();
    }

    static void Watch()
    {
        if (!EditorApplication.isPlaying || (Time.time < 3 && ++frames < 100000))
            return;
        foreach (var g in Object.FindObjectsByType<GameObject>(FindObjectsSortMode.None))
            said += $"{g.name} at {g.transform.position} turn {g.transform.eulerAngles.y:0}\n";
        said += $"player colour {GameObject.Find("Player").GetComponent<Renderer>().material.color}\n";
        File.WriteAllText("check.txt", said);
        EditorApplication.update -= Watch;
        EditorApplication.Exit(0);
    }
}
