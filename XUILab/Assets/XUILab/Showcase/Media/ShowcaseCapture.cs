using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.UI;
using XUILab.ListLab;
using XUILab.GradientLab;

namespace XUILab.Showcase
{
    // Separate diagnostic process: never installed during formal measurement.
    public sealed class ShowcaseCapture : MonoBehaviour
    {
        private string directory, mode;
        private bool quit, settingsCaptured, finished;
        private int originalCapture, originalTarget, originalVsync;
        private int originalWidth, originalHeight;
        private FullScreenMode originalFullscreen;
        private readonly CaptureRecord record = new CaptureRecord();
        private ShowcaseNavigation navigation;
        [Serializable] private sealed class CaptureRecord
        {
            public string schema = "xuilab.showcase.capture/v1", mode, unityVersion, result;
            public string scope = "diagnostic only; scripted actions; no formal performance samples";
            public string timing = "15 encoded frames per second; frame-driven media actions; real-time capture may take longer";
            public int frames, fps = 15, width, height;
            public List<string> checks = new List<string>();
            public List<string> errors = new List<string>();
            public List<string> images = new List<string>();
            public string restoration = "not_run";
        }
        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        private static void Install()
        {
            var args = Environment.GetCommandLineArgs();
            int index = Array.IndexOf(args, "--showcase-capture");
            if (index < 0) return;
            if (Application.isEditor || Array.IndexOf(args, "--xuilab-run") >= 0)
                throw new InvalidOperationException("Showcase capture requires a separate interactive Player.");
            int option = Array.IndexOf(args, "--showcase-capture-mode");
            if (index + 1 >= args.Length || option < 0 || option + 1 >= args.Length)
                throw new ArgumentException("Capture directory and mode required.");
            string mode = args[option + 1];
            if (mode != "smoke" && mode != "list" && mode != "gradient" && mode != "agent")
                throw new ArgumentException("Capture mode must be smoke/list/gradient/agent.");
            string directory = Path.GetFullPath(args[index + 1]);
            if (Directory.Exists(directory)) throw new IOException("Capture directory already exists.");
            var capture = new GameObject("Showcase Capture").AddComponent<ShowcaseCapture>();
            DontDestroyOnLoad(capture.gameObject);
            capture.directory = directory; capture.mode = mode;
            capture.quit = Array.IndexOf(args, "--showcase-capture-quit") >= 0;
        }
        private IEnumerator Start()
        {
            try
            {
                bool initialized = false;
                try
                {
                    Directory.CreateDirectory(directory);
                    record.mode = mode; record.unityVersion = Application.unityVersion;
                    originalCapture = Time.captureFramerate; originalTarget = Application.targetFrameRate; originalVsync = QualitySettings.vSyncCount;
                    originalWidth = Screen.width; originalHeight = Screen.height; originalFullscreen = Screen.fullScreenMode;
                    settingsCaptured = true; Time.captureFramerate = 15; Application.targetFrameRate = 15; QualitySettings.vSyncCount = 0;
                    Application.logMessageReceived += OnLog;
                    initialized = true;
                }
                catch (Exception exception) { record.errors.Add(exception.ToString()); }
                if (initialized)
                {
                    Screen.SetResolution(1280, 720, FullScreenMode.Windowed);
                    for (int i = 0; i < 15; i++) yield return null;
                    if (Screen.width != 1280 || Screen.height != 720) record.errors.Add("Initial capture resolution is not 1280x720.");
                    // Flatten nested routines so failures reach a non-success capture record.
                    var stack = new Stack<IEnumerator>(); stack.Push(mode == "smoke" ? Smoke() : Video());
                    while (stack.Count > 0 && record.errors.Count == 0)
                    {
                        bool more; object current = null;
                        try { more = stack.Peek().MoveNext(); if (more) current = stack.Peek().Current; }
                        catch (Exception exception) { record.errors.Add(exception.ToString()); break; }
                        if (!more) { stack.Pop(); continue; }
                        if (current is IEnumerator nested) stack.Push(nested); else yield return current;
                    }
                    TryRestore();
                    for (int i = 0; i < 15; i++) yield return null;
                    bool restored = Screen.width == originalWidth && Screen.height == originalHeight && Screen.fullScreenMode == originalFullscreen
                        && Time.captureFramerate == originalCapture && Application.targetFrameRate == originalTarget && QualitySettings.vSyncCount == originalVsync;
                    record.restoration = restored ? "pass" : "fail";
                    if (!restored) record.errors.Add("Capture settings restoration did not settle.");
                }
                if (!initialized) { TryRestore(); record.restoration = "initialization_failed"; }
                WriteFinal();
            }
            finally
            {
                if (!finished)
                {
                    record.errors.Add("Capture interrupted before finalization.");
                    TryRestore(); WriteFinal();
                }
            }
        }
        private void OnLog(string message, string trace, LogType type)
        { if (type == LogType.Error || type == LogType.Exception || type == LogType.Assert) record.errors.Add(message); }
        private IEnumerator Theme(string scene)
        {
            navigation = FindObjectOfType<ShowcaseNavigation>();
            Require(navigation, "Navigation installed");
            navigation.OpenTheme(scene); yield return null; yield return null;
            Require(SceneManager.GetActiveScene().name == scene, "Theme " + scene);
        }
        private static void Click(string name)
        { FindObjectsOfType<Button>().Single(button => button.name == name).onClick.Invoke(); }
        private void Require(bool condition, string label)
        { if (!condition) throw new InvalidOperationException(label); record.checks.Add(label); }
        private IEnumerator Save(string name)
        {
            yield return new WaitForEndOfFrame();
            var image = ScreenCapture.CaptureScreenshotAsTexture();
            try { File.WriteAllBytes(Path.Combine(directory, name + ".png"), image.EncodeToPNG()); }
            finally { Destroy(image); }
            record.frames++; record.width = Screen.width; record.height = Screen.height;
            record.images.Add(name + ".png " + Screen.width + "x" + Screen.height);
        }
        private IEnumerator Smoke()
        {
            yield return Theme("ListLab"); var list = FindObjectOfType<ListLabDemo>();
            Require(list.View.Count == 1000 && list.View.Virtualized, "Cold list 1000 virtual");
            Click("Bottom"); Click("Save"); Click("Top"); Click("Restore");
            Require(Mathf.Abs(list.View.PixelOffset - list.View.MaxOffset) < .1f, "Bottom/save/top/restore");
            Click("Policy"); int binds = list.View.Pool.BindCount; Click("Update item");
            Require(list.View.Pool.BindCount == binds + 1, "TargetOnly one binding");
            Click("Backend"); yield return null; Require(!list.View.Virtualized && list.View.Pool.Leased == 1000, "Normal 1000 retained rows");
            Click("100 / 1000"); yield return null; Require(list.View.Count == 100, "Count parameter 100");
            Click("Clear / refill"); Click("Update item"); Require(list.View.Count == 0, "Empty update safe");
            Click("Clear / refill"); Click("Reopen"); Require(list.View.ValidateState(out var reason), "Reopen invariants: " + reason);
            yield return Save("list-1280");
            Screen.SetResolution(960, 540, FullScreenMode.Windowed); for (int i = 0; i < 15; i++) yield return null;
            Require(Screen.width == 960 && Screen.height == 540, "Resize 960x540"); yield return Save("list-960");
            Screen.SetResolution(1280, 720, FullScreenMode.Windowed); for (int i = 0; i < 15; i++) yield return null;
            Require(Screen.width == 1280 && Screen.height == 720, "Restore 1280x720");
            yield return Theme("GradientLab"); var gradient = FindObjectOfType<GradientLabDemo>();
            Click("Fixed / Adaptive"); yield return null; Canvas.ForceUpdateCanvases();
            Require(gradient.Effects.Any(e => e.LastMode == GradientMeshMode.AdaptiveSegments), "Adaptive actual mesh");
            Require(gradient.Effects.Count(e => e.LastMode == GradientMeshMode.VertexFallback) == 3, "Three fallback image types");
            Click("Segments"); Require(gradient.Effects.All(e => e.FixedSegments == 64), "Fixed segment parameter");
            Click("Direction"); Click("Bias"); Click("Transition"); for (int i = 0; i < 10; i++) yield return null;
            float bias = gradient.Effects[0].Bias; Require(bias > .05f, "Transition advances"); Click("Stop");
            for (int i = 0; i < 3; i++) yield return null; Require(gradient.Effects[0].Bias == bias, "Transition stops");
            yield return Save("gradient-adaptive");
            yield return Theme("BenchmarkSmoke");
            foreach (string example in new[] { "normal", "fail", "invalid" })
            {
                navigation.StartDiagnostic(example);
                for (int i = 0; i < 300 && navigation.DiagnosticRunning; i++) yield return null;
                Require(!navigation.DiagnosticRunning && navigation.DiagnosticResult != null, "Runner terminal " + example);
                Require(navigation.DiagnosticResult.IsProcessSuccess == (example == "normal"), "Runner success boundary " + example);
                record.checks.Add(example + ": " + navigation.DiagnosticResult.State + "/" + navigation.DiagnosticResult.Correctness + "/" + navigation.DiagnosticResult.MeasurementValidity + "/exit " + navigation.DiagnosticResult.ExitCode);
                yield return Save("agent-" + example);
            }
            yield return Theme("ListLab"); Require(FindObjectOfType<ListLabDemo>().View.Count == 1000, "Repeated theme entry");
        }
        private IEnumerator Video()
        {
            yield return Theme(mode == "list" ? "ListLab" : mode == "gradient" ? "GradientLab" : "BenchmarkSmoke");
            var list = FindObjectOfType<ListLabDemo>(); var gradient = FindObjectOfType<GradientLabDemo>();
            Require(mode != "list" || list != null, "List video requires ListLabDemo");
            Require(mode != "gradient" || gradient != null, "Gradient video requires GradientLabDemo");
            if (list) { Click("Backend"); yield return null; }
            for (int frame = 0; frame < 675; frame++)
            {
                if (list)
                {
                    if (frame == 225) { Click("Backend"); yield return null; }
                    if (frame < 450) list.View.SetPixelOffset((frame % 225) / 224f * list.View.MaxOffset);
                    if (frame == 450) { Click("Top"); Click("Policy"); }
                    if (frame >= 450 && frame % 15 == 0) Click("Update item");
                    if (frame == 540) { Click("Bottom"); Click("Save"); Click("Top"); }
                    if (frame == 570) Click("Restore");
                    if (frame == 615) Click("Reopen");
                }
                if (gradient)
                {
                    if (frame == 225) Click("Fixed / Adaptive");
                    if (frame == 450) Click("Direction");
                    gradient.SetTransitionProgress(Mathf.PingPong(frame / 150f, 1));
                }
                if (mode == "agent")
                {
                    if (frame == 0) navigation.StartDiagnostic("normal");
                    if (frame == 240) { Require(navigation.DiagnosticResult.IsProcessSuccess, "Video normal pass"); navigation.StartDiagnostic("fail"); }
                    if (frame == 270) { Require(!navigation.DiagnosticResult.IsProcessSuccess, "Video fail rejected"); navigation.StartDiagnostic("invalid"); }
                    if (frame == 510) Require(!navigation.DiagnosticRunning && !navigation.DiagnosticResult.IsProcessSuccess, "Video invalid rejected");
                }
                yield return Save("frame-" + frame.ToString("D4"));
            }
        }
        private void WriteFinal()
        {
            record.result = record.errors.Count == 0 ? "pass" : "fail";
            try { File.WriteAllText(Path.Combine(directory, "capture.json"), JsonUtility.ToJson(record, true)); }
            catch (Exception exception) { record.errors.Add(exception.ToString()); Debug.LogError("Capture result could not be saved: " + exception.Message); }
            finished = true;
            if (quit) Application.Quit(record.errors.Count == 0 ? 0 : 2);
        }
        private void TryRestore()
        {
            try { Restore(); }
            catch (Exception exception) { record.errors.Add("Restoration: " + exception); }
        }
        private void Restore()
        {
            Application.logMessageReceived -= OnLog;
            if (!settingsCaptured) return;
            navigation?.StopDiagnostic();
            Time.captureFramerate = originalCapture; Application.targetFrameRate = originalTarget; QualitySettings.vSyncCount = originalVsync;
            Screen.SetResolution(originalWidth, originalHeight, originalFullscreen);
            settingsCaptured = false;
        }
        private void OnDestroy() { TryRestore(); }
    }
}
