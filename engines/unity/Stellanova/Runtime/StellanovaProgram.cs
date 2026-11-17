// A .stella file in the Assets folder, as Unity keeps it (made by StellanovaImporter).
using UnityEngine;

public class StellanovaProgram : ScriptableObject
{
    public string pluginName;  // its plugin is StreamingAssets/Stellanova/<pluginName>.dll
    [TextArea(5, 30)] public string words;  // the script itself, to read in the Inspector
}
