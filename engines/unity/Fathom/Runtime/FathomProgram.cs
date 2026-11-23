// A .fathom file in Assets.
using UnityEngine;

public class FathomProgram : ScriptableObject
{
    public string pluginName;  // its plugin is StreamingAssets/Fathom/<pluginName>.dll
    [TextArea(5, 30)] public string words;  // the script itself, to read in the Inspector
}
