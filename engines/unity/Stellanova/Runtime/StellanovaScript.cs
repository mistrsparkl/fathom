// Runs a Stellanova program on this object.
using UnityEngine;

public class StellanovaScript : MonoBehaviour
{
    [Tooltip("A .stella file from the Assets folder (it is made into a plugin each time it is saved).")]
    public StellanovaProgram program;

    StellanovaPlugin plugin;

    void Start()
    {
        if (!program)
        {
            Debug.LogError($"Stellanova: {name} has a Stellanova Script without a program: drag a .stella file onto it.", this);
            enabled = false;
            return;
        }
        plugin = StellanovaPlugin.Load(program.pluginName);
        if (plugin == null)
        {
            enabled = false;
            return;
        }
        plugin.Call("begin", gameObject);
    }

    void Update() => plugin?.Call("every frame", gameObject, Time.deltaTime);

    void OnCollisionEnter(Collision bump) => plugin?.Call("touched", gameObject, StellanovaObjects.Of(bump.gameObject));

    void OnTriggerEnter(Collider other) => plugin?.Call("touched", gameObject, StellanovaObjects.Of(other.gameObject));
}
