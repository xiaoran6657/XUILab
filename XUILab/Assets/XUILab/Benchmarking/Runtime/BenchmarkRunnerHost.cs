using UnityEngine;

namespace XUILab.Benchmarking
{
    [DisallowMultipleComponent]
    public sealed class BenchmarkRunnerHost : MonoBehaviour
    {
        private BenchmarkRunner runner;
        private bool quitIssued;

        public bool IsReady { get; private set; }

        public int ObservedFrameCount { get; private set; }

        public bool IsRunActive { get { return runner != null && !runner.IsTerminal; } }

        public BenchmarkRunResult LastResult { get { return runner == null ? null : runner.Result; } }

        private void Awake()
        {
            IsReady = true;
        }

        private void Start()
        {
            BenchmarkRunConfig config;
            string error;
            string[] args = System.Environment.GetCommandLineArgs();
            if (BenchmarkCommandLine.TryCreateRunConfig(args, out config, out error))
            {
                StartRun(config);
            }
            else if (Contains(args, "--xuilab-run") && !string.IsNullOrEmpty(error))
            {
                Debug.LogError("XUILab benchmark command line rejected: " + error);
                if (Contains(args, "--xuilab-quit"))
                {
                    Application.Quit(2);
                }
            }
            else if (BenchmarkCommandLine.TryReadEditorRequest(out config, out error))
            {
                StartRun(config);
            }
            else if (!string.IsNullOrEmpty(error))
            {
                Debug.LogError("XUILab editor benchmark request rejected: " + error);
            }
        }

        private void Update()
        {
            if (!IsReady)
            {
                return;
            }

            ObservedFrameCount++;
            if (runner == null || runner.IsTerminal)
            {
                if (!quitIssued && runner != null && runner.Result != null && runner.Result.Config.quitWhenDone)
                {
                    quitIssued = true;
                    Application.Quit(runner.Result.ExitCode);
                }

                return;
            }

            runner.Tick(Time.unscaledDeltaTime * 1000.0, Time.frameCount);
        }

        private void OnApplicationFocus(bool hasFocus)
        {
            if (!hasFocus && IsRunActive)
            {
                runner.MarkFocusLost();
            }
        }

        private void OnApplicationPause(bool pauseStatus)
        {
            if (pauseStatus && IsRunActive)
            {
                runner.MarkPaused();
            }
        }

        private void OnDestroy()
        {
            if (runner != null)
            {
                runner.Dispose();
            }
        }

        public void StartRun(BenchmarkRunConfig config)
        {
            if (runner != null)
            {
                throw new System.InvalidOperationException("BenchmarkRunnerHost already owns a runner.");
            }

            runner = new BenchmarkRunner();
            runner.Start(config);
        }

        public void CancelRun()
        {
            if (runner != null)
            {
                runner.RequestCancel();
            }
        }

        private static bool Contains(string[] values, string expected)
        {
            if (values == null)
            {
                return false;
            }

            for (int i = 0; i < values.Length; i++)
            {
                if (string.Equals(values[i], expected, System.StringComparison.Ordinal))
                {
                    return true;
                }
            }

            return false;
        }
    }
}
