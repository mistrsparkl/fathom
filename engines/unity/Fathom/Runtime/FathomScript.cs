// Runs a Fathom program on this object.
using UnityEngine;

public class FathomScript : MonoBehaviour
{
    [Tooltip("A .fathom file from the Assets folder (it is made into a plugin each time it is saved).")]
    public FathomProgram program;

    FathomPlugin plugin;

    void Start()
    {
        if (!program)
        {
            Debug.LogError($"Fathom: {name} has a Fathom Script without a program: drag a .fathom file onto it.", this);
            enabled = false;
            return;
        }
        plugin = FathomPlugin.Load(program.pluginName);
        if (plugin == null)
        {
            enabled = false;
            return;
        }
        plugin.Call("begin", gameObject);
    }

    void Update() => plugin?.Call("every frame", gameObject, Time.deltaTime);

    void OnCollisionEnter(Collision bump) => plugin?.Call("touched", gameObject, FathomObjects.Of(bump.gameObject));

    void OnTriggerEnter(Collider other) => plugin?.Call("touched", gameObject, FathomObjects.Of(other.gameObject));
}
