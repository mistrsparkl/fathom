// A Fathom plugin, and Unity's answers to its engine words.
using System;
using System.Collections.Generic;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using UnityEngine;
#if ENABLE_INPUT_SYSTEM
using UnityEngine.InputSystem;
using UnityEngine.InputSystem.Controls;
#endif

public sealed class FathomPlugin
{
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate void OutputFn(IntPtr text, int isProblem);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate double EngineFn(IntPtr word, IntPtr numbers, int count, IntPtr text, IntPtr answers, IntPtr answerText, int room);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate int StartFn(IntPtr output, IntPtr engine);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate int CallFn(byte[] name, double me, double[] numbers, int count, out double answer);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate int HasFn(byte[] name, int count);

    static readonly OutputFn output = Output;  // (kept here, so they aren't collected while the programs hold them)
    static readonly EngineFn engine = Engine;
    static readonly Dictionary<string, FathomPlugin> loaded = new Dictionary<string, FathomPlugin>();

    readonly string name;
    IntPtr library;
    CallFn call;
    HasFn has;
    readonly Dictionary<string, bool> commands = new Dictionary<string, bool>();

    FathomPlugin(string name) { this.name = name; }

    // Loads the program called name, or null.
    public static FathomPlugin Load(string name)
    {
        if (loaded.TryGetValue(name, out var known))
            return known;
        var plugin = new FathomPlugin(name);
        loaded[name] = plugin;
        string path = Path.Combine(Application.streamingAssetsPath, "Fathom", name + Native.Suffix);
        if (!File.Exists(path))
        {
            Debug.LogError($"Fathom: {name} isn't built yet ({path} is missing). Look in the Console for its mistakes.");
            return loaded[name] = null;
        }
#if UNITY_EDITOR
        // Loads a copy, so the program can be rebuilt.
        string copy = Path.Combine(Application.temporaryCachePath, $"{name}_{DateTime.Now.Ticks}{Native.Suffix}");
        File.Copy(path, copy, true);
        path = copy;
#endif
        plugin.library = Native.Open(path);
        if (plugin.library == IntPtr.Zero)
        {
            Debug.LogError($"Fathom: {name} couldn't be loaded on this computer.");
            return loaded[name] = null;
        }
        var start = Marshal.GetDelegateForFunctionPointer<StartFn>(Native.Find(plugin.library, "fathom_start"));
        plugin.call = Marshal.GetDelegateForFunctionPointer<CallFn>(Native.Find(plugin.library, "fathom_call"));
        plugin.has = Marshal.GetDelegateForFunctionPointer<HasFn>(Native.Find(plugin.library, "fathom_has"));
        start(Marshal.GetFunctionPointerForDelegate(output), Marshal.GetFunctionPointerForDelegate(engine));
        return plugin;
    }

    // Calls a command for an object, if the program has it.
    public void Call(string command, GameObject me, params double[] numbers)
    {
        string key = command + "/" + numbers.Length;
        if (!commands.TryGetValue(key, out bool there))
            commands[key] = there = has(Utf8(command), numbers.Length) == 1;
        if (there)
            call(Utf8(command), FathomObjects.Of(me), numbers, numbers.Length, out _);
    }

    // When play stops, let every program go.
    public static void UnloadAll()
    {
        foreach (var plugin in loaded.Values)
            if (plugin != null && plugin.library != IntPtr.Zero)
                Native.Close(plugin.library);
        loaded.Clear();
        FathomObjects.Clear();
    }

    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]
    static void Fresh() => UnloadAll();

    static byte[] Utf8(string s) => Encoding.UTF8.GetBytes(s + "\0");

    [AOT.MonoPInvokeCallback(typeof(OutputFn))]
    static void Output(IntPtr text, int isProblem)
    {
        string said = Marshal.PtrToStringUTF8(text);
        if (isProblem != 0)
            Debug.LogError("Fathom: " + said);
        else
            Debug.Log(said);
    }

    [AOT.MonoPInvokeCallback(typeof(EngineFn))]
    static double Engine(IntPtr wordAt, IntPtr numbersAt, int count, IntPtr textAt, IntPtr answers, IntPtr answerText, int room)
    {
        string word = Marshal.PtrToStringUTF8(wordAt);
        string text = Marshal.PtrToStringUTF8(textAt);
        var n = new double[count];
        if (count > 0)
            Marshal.Copy(numbersAt, n, 0, count);
        GameObject it = count > 0 ? FathomObjects.Get(n[0]) : null;
        if (count > 0 && it == null && word != "named")
            return 0;  // (an object that has gone: its words do nothing)
        switch (word)
        {
            case "place":
                Marshal.Copy(new double[] { it.transform.position.x, it.transform.position.y, it.transform.position.z }, 0, answers, 3);
                return 0;
            case "put": it.transform.position = new Vector3((float)n[1], (float)n[2], (float)n[3]); return 0;
            case "move": it.transform.position += new Vector3((float)n[1], (float)n[2], (float)n[3]); return 0;
            case "turn": return it.transform.eulerAngles.y;
            case "turn by": it.transform.Rotate(0, (float)n[1], 0, Space.World); return 0;
            case "named": { var found = GameObject.Find(text); return found ? FathomObjects.Of(found) : 0; }
            case "name":
            {
                byte[] bytes = Encoding.UTF8.GetBytes(it.name);
                int size = Math.Min(bytes.Length, room - 1);
                Marshal.Copy(bytes, 0, answerText, size);
                Marshal.WriteByte(answerText, size, 0);
                return 0;
            }
            case "copy":
            {
                var made = UnityEngine.Object.Instantiate(it, new Vector3((float)n[1], (float)n[2], (float)n[3]), it.transform.rotation);
                made.name = it.name;
                return FathomObjects.Of(made);
            }
            case "remove":
                if (Application.isPlaying)
                    UnityEngine.Object.Destroy(it);
                else
                    UnityEngine.Object.DestroyImmediate(it);
                return 0;
            case "colour":
            {
                var look = it.GetComponent<Renderer>();
                if (look && ColorUtility.TryParseHtmlString(text == "pink" ? "#ffc0cb" : text == "grey" ? "#808080" : text, out var colour))
                    (Application.isPlaying ? look.material : look.sharedMaterial).color = colour;
                return 0;
            }
            case "key held": return Keys.Held(text) ? 1 : 0;
            case "key pressed": return Keys.Pressed(text) ? 1 : 0;
            case "frame time": return Time.deltaTime;
        }
        return 0;
    }

    static class Keys  // Key names Fathom uses.
    {
#if ENABLE_INPUT_SYSTEM
        static KeyControl Control(string name)
        {
            var board = Keyboard.current;
            if (board == null)
                return null;
            switch (name)
            {
                case "left": return board.leftArrowKey;
                case "right": return board.rightArrowKey;
                case "up": return board.upArrowKey;
                case "down": return board.downArrowKey;
                case "space": return board.spaceKey;
                case "enter": return board.enterKey;
                case "escape": return board.escapeKey;
                case "shift": return board.leftShiftKey;
                case "control": return board.leftCtrlKey;
                case "tab": return board.tabKey;
                case "backspace": return board.backspaceKey;
            }
            return name.Length == 1 && char.IsLetterOrDigit(name[0]) ? board.TryGetChildControl<KeyControl>(name.ToLowerInvariant()) : null;
        }
        public static bool Held(string name) => Control(name)?.isPressed ?? false;
        public static bool Pressed(string name) => Control(name)?.wasPressedThisFrame ?? false;
#else
        static KeyCode Code(string name)
        {
            switch (name)
            {
                case "left": return KeyCode.LeftArrow;
                case "right": return KeyCode.RightArrow;
                case "up": return KeyCode.UpArrow;
                case "down": return KeyCode.DownArrow;
                case "space": return KeyCode.Space;
                case "enter": return KeyCode.Return;
                case "escape": return KeyCode.Escape;
                case "shift": return KeyCode.LeftShift;
                case "control": return KeyCode.LeftControl;
                case "tab": return KeyCode.Tab;
                case "backspace": return KeyCode.Backspace;
            }
            if (name.Length == 1 && char.IsDigit(name[0]))
                return KeyCode.Alpha0 + (name[0] - '0');
            if (name.Length == 1 && char.IsLetter(name[0]))
                return KeyCode.A + (char.ToLowerInvariant(name[0]) - 'a');
            return KeyCode.None;
        }
        public static bool Held(string name) => Input.GetKey(Code(name));
        public static bool Pressed(string name) => Input.GetKeyDown(Code(name));
#endif
    }

    static class Native
    {
#if UNITY_EDITOR_WIN || UNITY_STANDALONE_WIN
        public const string Suffix = ".dll";
        [DllImport("kernel32", CharSet = CharSet.Unicode, SetLastError = true)] static extern IntPtr LoadLibraryW(string path);
        [DllImport("kernel32")] static extern IntPtr GetProcAddress(IntPtr library, string name);
        [DllImport("kernel32")] static extern bool FreeLibrary(IntPtr library);
        public static IntPtr Open(string path) => LoadLibraryW(path);
        public static IntPtr Find(IntPtr library, string name) => GetProcAddress(library, name);
        public static void Close(IntPtr library) => FreeLibrary(library);
#else
        public const string Suffix = ".so";
        [DllImport("libdl.so.2")] static extern IntPtr dlopen(string path, int flags);
        [DllImport("libdl.so.2")] static extern IntPtr dlsym(IntPtr library, string name);
        [DllImport("libdl.so.2")] static extern int dlclose(IntPtr library);
        public static IntPtr Open(string path) => dlopen(path, 2);
        public static IntPtr Find(IntPtr library, string name) => dlsym(library, name);
        public static void Close(IntPtr library) => dlclose(library);
#endif
    }
}

// Each object a program knows is a number (0 is none).
public static class FathomObjects
{
    static readonly Dictionary<int, GameObject> byNumber = new Dictionary<int, GameObject>();
    static readonly Dictionary<int, int> numbers = new Dictionary<int, int>();  // Unity's instance id -> its number
    static int next = 1;

    public static double Of(GameObject g)
    {
        if (!g)
            return 0;
        int id = g.GetInstanceID();
        if (!numbers.TryGetValue(id, out int n))
        {
            numbers[id] = n = next++;
            byNumber[n] = g;
        }
        return n;
    }

    public static GameObject Get(double n) => byNumber.TryGetValue((int)n, out var g) && g ? g : null;

    public static void Clear()
    {
        byNumber.Clear();
        numbers.Clear();
        next = 1;
    }
}
