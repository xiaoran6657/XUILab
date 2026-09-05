using System;
using System.Globalization;
using System.IO;
using UnityEngine;

namespace XUILab.Benchmarking
{
    public static class BenchmarkCommandLine
    {
        public static string EditorRequestPath
        {
            get
            {
                return Path.GetFullPath(
                    Path.Combine(Application.dataPath, "..", "Library", "XUILabBenchmarkRequest.json"));
            }
        }

        public static bool TryCreateRunConfig(string[] args, out BenchmarkRunConfig config, out string error)
        {
            config = null;
            error = null;
            if (!HasFlag(args, "--xuilab-run"))
            {
                return false;
            }

            try
            {
                string caseId = GetValue(args, "--xuilab-case", "idle");
                string runId = GetValue(
                    args,
                    "--xuilab-run-id",
                    "m0-run-" + caseId + "-" + DateTime.UtcNow.ToString("yyyyMMddTHHmmssZ", CultureInfo.InvariantCulture));
                string outputRoot = GetValue(
                    args,
                    "--xuilab-output-root",
                    Path.Combine(Application.persistentDataPath, "XUILab", "Artifacts"));

                int measureFrames = GetInt(args, "--xuilab-measure-frames", 1800);
                config = new BenchmarkRunConfig
                {
                    protocolVersion = GetValue(args, "--xuilab-protocol-version", "xuilab.benchmark.protocol/v1"),
                    runId = runId,
                    seriesId = GetValue(args, "--xuilab-series-id", "m0-calibration"),
                    runIndex = GetInt(args, "--xuilab-run-index", 0),
                    plannedRepeatCount = GetInt(args, "--xuilab-repeat-count", 5),
                    tier = Application.isEditor ? "editor-playmode" : "windows-development-player",
                    caseId = caseId,
                    warmupFrames = GetInt(args, "--xuilab-warmup-frames", 300),
                    measureFrames = measureFrames,
                    sampleCapacity = GetInt(args, "--xuilab-sample-capacity", measureFrames),
                    readyTimeoutFrames = GetInt(args, "--xuilab-ready-timeout-frames", 300),
                    frameBudgetMs = GetDouble(args, "--xuilab-frame-budget-ms", 16.6666667),
                    targetFrameRate = GetInt(args, "--xuilab-target-frame-rate", 60),
                    vSyncCount = GetInt(args, "--xuilab-vsync-count", 0),
                    enableProfilerRecorders = !HasFlag(args, "--xuilab-disable-profiler-recorders"),
                    cpuIterationsPerFrame = GetInt(args, "--xuilab-cpu-iterations", caseId == "known-load" ? 250000 : 0),
                    allocationBytesPerFrame = GetInt(args, "--xuilab-allocation-bytes", caseId == "known-load" ? 32768 : 0),
                    outputDirectory = outputRoot,
                    candidateId = GetValue(args, "--xuilab-candidate-id", "unknown"),
                    buildId = GetValue(args, "--xuilab-build-id", "unknown"),
                    sourceRevision = GetValue(args, "--xuilab-source-revision", "unknown"),
                    dirty = !HasFlag(args, "--xuilab-clean"),
                    quitWhenDone = HasFlag(args, "--xuilab-quit"),
                    faultPlan = new BenchmarkFaultPlan
                    {
                        mode = GetValue(args, "--xuilab-fault", "none"),
                        triggerMeasureFrame = GetInt(args, "--xuilab-fault-trigger-frame", 0),
                        shortageSampleCount = GetInt(args, "--xuilab-fault-sample-count", 1)
                    }
                };

                error = config.Validate();
                if (error != null)
                {
                    config = null;
                    return false;
                }

                return true;
            }
            catch (Exception exception)
            {
                error = exception.GetType().Name + ": " + exception.Message;
                config = null;
                return false;
            }
        }

        public static bool TryReadEditorRequest(out BenchmarkRunConfig config, out string error)
        {
            config = null;
            error = null;
            if (!Application.isEditor || !File.Exists(EditorRequestPath))
            {
                return false;
            }

            try
            {
                string json = File.ReadAllText(EditorRequestPath);
                File.Delete(EditorRequestPath);
                config = JsonUtility.FromJson<BenchmarkRunConfig>(json);
                if (config == null)
                {
                    error = "Editor benchmark request did not contain a config.";
                    return false;
                }

                error = config.Validate();
                if (error != null)
                {
                    config = null;
                    return false;
                }

                return true;
            }
            catch (Exception exception)
            {
                error = exception.GetType().Name + ": " + exception.Message;
                config = null;
                return false;
            }
        }

        private static bool HasFlag(string[] args, string flag)
        {
            if (args == null)
            {
                return false;
            }

            for (int i = 0; i < args.Length; i++)
            {
                if (string.Equals(args[i], flag, StringComparison.Ordinal))
                {
                    return true;
                }
            }

            return false;
        }

        private static string GetValue(string[] args, string name, string defaultValue)
        {
            if (args == null)
            {
                return defaultValue;
            }

            for (int i = 0; i < args.Length; i++)
            {
                if (string.Equals(args[i], name, StringComparison.Ordinal))
                {
                    if (i + 1 >= args.Length || args[i + 1].StartsWith("--", StringComparison.Ordinal))
                    {
                        throw new FormatException(name + " requires a value.");
                    }

                    return args[i + 1];
                }
            }

            return defaultValue;
        }

        private static int GetInt(string[] args, string name, int defaultValue)
        {
            string text = GetValue(args, name, null);
            if (text == null)
            {
                return defaultValue;
            }

            int value;
            if (!int.TryParse(text, NumberStyles.Integer, CultureInfo.InvariantCulture, out value))
            {
                throw new FormatException(name + " requires an invariant integer.");
            }

            return value;
        }

        private static double GetDouble(string[] args, string name, double defaultValue)
        {
            string text = GetValue(args, name, null);
            if (text == null)
            {
                return defaultValue;
            }

            double value;
            if (!double.TryParse(text, NumberStyles.Float, CultureInfo.InvariantCulture, out value))
            {
                throw new FormatException(name + " requires an invariant number.");
            }

            return value;
        }
    }
}
