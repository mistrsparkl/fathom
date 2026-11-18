// Writes what was logged and every object to check.txt after 3 seconds.
using System.IO;
using UnityEngine;

public class CheckReport : MonoBehaviour
{
    string said = "";
    bool done;

    void Awake() => Application.logMessageReceived += Keep;

    void Keep(string message, string stack, LogType type)
    {
        if (type == LogType.Log)
            said += "SAID " + message + "\n";
        else if (type == LogType.Error && message.StartsWith("Stellanova: "))
            said += "SAID problem: " + message.Substring("Stellanova: ".Length) + "\n";
        else if (type != LogType.Warning)
            said += "BAD " + type + ": " + message.Replace("\n", " ") + "\n";
    }

    void Update()
    {
        if (done || Time.time < 3)
            return;
        done = true;
        foreach (var g in FindObjectsByType<GameObject>(FindObjectsSortMode.None))
        {
            if (g == gameObject)
                continue;
            var look = g.GetComponent<Renderer>();
            var colour = look == null || look.material.color == Color.white ? "none" : look.material.color == Color.red ? "red" : look.material.color == Color.blue ? "blue" : "other";
            var p = g.transform.position;
            said += $"CHECK {g.name}|{p.x}|{p.y}|{p.z}|{g.transform.eulerAngles.y}|{colour}\n";
        }
        File.WriteAllText(Path.Combine(Application.dataPath, "..", "check.txt"), said);
        if (!Application.isEditor)
            Application.Quit();
    }
}
