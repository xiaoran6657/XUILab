using System;
using System.Text;
using UnityEngine;
using UnityEngine.SceneManagement;
using XUILab.Benchmarking;

namespace XUILab.Showcase
{
    // Player-only navigation. Formal sampling and existing capture entry points never install it.
    public sealed class ShowcaseNavigation : MonoBehaviour
    {
        private static ShowcaseNavigation instance;
        private BenchmarkRunner runner;
        private string selected = "Ready";
        private GUIStyle heading, body;
        public BenchmarkRunResult DiagnosticResult => runner?.Result;
        public bool DiagnosticRunning => runner != null && !runner.IsTerminal;

        public static bool AllowsNavigation(string[] args, bool editor, string scene)
        {
            if (editor || (scene != "ListLab" && scene != "GradientLab" && scene != "BenchmarkSmoke")) return false;
            foreach (string arg in args)
                if (arg == "--xuilab-run" || arg == "--list-media-dir" || arg == "--gradient-media-dir") return false;
            return true;
        }

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        private static void Install()
        {
            if (instance || !AllowsNavigation(Environment.GetCommandLineArgs(), Application.isEditor, SceneManager.GetActiveScene().name)) return;
            instance = new GameObject("Showcase Navigation").AddComponent<ShowcaseNavigation>();
            DontDestroyOnLoad(instance.gameObject);
        }

        public void OpenTheme(string scene)
        {
            if (scene != "ListLab" && scene != "GradientLab" && scene != "BenchmarkSmoke")
                throw new ArgumentOutOfRangeException(nameof(scene));
            StopDiagnostic();
            SceneManager.LoadScene(scene);
        }

        public void StartDiagnostic(string mode)
        {
            if (mode != "normal" && mode != "fail" && mode != "invalid") throw new ArgumentOutOfRangeException(nameof(mode));
            StopDiagnostic();
            selected = mode;
            var config = new BenchmarkRunConfig
            {
                runId = "interactive-" + mode,
                seriesId = "showcase-diagnostic",
                candidateId = "interactive-diagnostic-only",
                buildId = "interactive-diagnostic-only",
                sourceRevision = "see-package-manifest",
                tier = "diagnostic",
                outputDirectory = "memory-only",
                warmupFrames = 30,
                measureFrames = mode == "fail" ? 0 : 180,
                sampleCapacity = 180,
                plannedRepeatCount = 1,
                enableProfilerRecorders = false,
                optionalMetrics = Array.Empty<string>(),
                targetFrameRate = 60
            };
            runner = new BenchmarkRunner(writer: new MemoryWriter());
            runner.Start(config);
            if (mode == "invalid") runner.MarkPaused();
        }

        public void StopDiagnostic()
        {
            runner?.Dispose();
            runner = null;
        }

        private void Update()
        {
            if (DiagnosticRunning) runner.Tick(Time.unscaledDeltaTime * 1000.0, Time.frameCount);
        }
        private void OnApplicationFocus(bool focused)
        {
            if (!focused && DiagnosticRunning) runner.MarkFocusLost();
        }
        private void OnApplicationPause(bool paused)
        {
            if (paused && DiagnosticRunning) runner.MarkPaused();
        }
        private void OnDestroy()
        {
            StopDiagnostic();
            if (instance == this) instance = null;
        }

        private void OnGUI()
        {
            if (heading == null)
            {
                heading = new GUIStyle(GUI.skin.label) { fontSize = 27, wordWrap = true };
                body = new GUIStyle(GUI.skin.label) { fontSize = 18, wordWrap = true };
            }
            GUI.Box(new Rect(0, 0, Screen.width, 32), "");
            if (GUI.Button(new Rect(8, 3, 120, 26), "List Lab")) OpenTheme("ListLab");
            if (GUI.Button(new Rect(136, 3, 120, 26), "Gradient Lab")) OpenTheme("GradientLab");
            if (GUI.Button(new Rect(264, 3, 150, 26), "Agent / Runner")) OpenTheme("BenchmarkSmoke");
            GUI.Label(new Rect(430, 4, 430, 24), "XUILab  |  Interactive diagnostics");
            if (GUI.Button(new Rect(Screen.width - 72, 3, 64, 26), "Quit")) Application.Quit();
            if (SceneManager.GetActiveScene().name != "BenchmarkSmoke") return;
            Color previousColor = GUI.color;
            GUI.color = new Color(0.055f, 0.075f, 0.105f, 1f);
            GUI.DrawTexture(new Rect(0, 32, Screen.width, Screen.height - 32), Texture2D.whiteTexture);
            GUI.color = previousColor;
            float width = Mathf.Min(Screen.width - 48, 1120);
            GUILayout.BeginArea(new Rect(24, 55, width, Screen.height - 72), GUI.skin.box);
            GUILayout.Label("AGENT / CONFIGURATION-DRIVEN RUNNER", heading);
            GUILayout.Label("Run the real state machine with an idle case. These short interactive runs are diagnostics, not performance evidence. Export stays in memory.", body);
            GUILayout.Space(16);
            GUILayout.BeginHorizontal();
            if (GUILayout.Button("Normal", GUILayout.Height(38))) StartDiagnostic("normal");
            if (GUILayout.Button("Fail: invalid configuration", GUILayout.Height(38))) StartDiagnostic("fail");
            if (GUILayout.Button("Invalid: pause signal", GUILayout.Height(38))) StartDiagnostic("invalid");
            GUILayout.EndHorizontal();
            GUILayout.Space(16);
            GUILayout.Label("Prepare > Warmup > Measure > Validate > Export > Cleanup > terminal", body);
            GUILayout.Label("Selected: " + selected + " / state: " + (runner == null ? "Idle" : runner.State.ToString()), body);
            var result = DiagnosticResult;
            if (result != null)
            {
                GUILayout.Label("Correctness: " + result.Correctness + " / validity: " + result.MeasurementValidity, body);
                GUILayout.Label("Process success: " + result.IsProcessSuccess + " / exit code: " + result.ExitCode, body);
                GUILayout.Label("Failure: " + result.FailureCode + " / " + result.FailureReason, body);
                if (result.Events != null)
                {
                    var text = new StringBuilder();
                    for (int i = Mathf.Max(0, result.Events.Count - 9); i < result.Events.Count; i++) text.AppendLine(result.Events.Get(i));
                    GUILayout.Label(text.ToString(), body);
                }
            }
            GUILayout.FlexibleSpace();
            GUILayout.Label("A completed state alone does not prove success. Correctness, validity, export and cleanup must all pass. Formal evidence uses the separate frozen Development Player matrix.", body);
            GUILayout.EndArea();
        }

        private sealed class MemoryWriter : IBenchmarkArtifactWriter
        {
            public string RunDirectory => "memory://showcase-diagnostic";
            public void WriteInitial(BenchmarkRunResult result) { }
            public void WriteTerminal(BenchmarkRunResult result) { }
        }
    }
}
