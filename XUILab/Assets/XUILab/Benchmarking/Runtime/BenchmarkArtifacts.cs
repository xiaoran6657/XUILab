using System;
using System.Globalization;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using UnityEngine;

namespace XUILab.Benchmarking
{
    [Serializable]
    public sealed class BenchmarkEnvironmentRecord
    {
        public string schemaVersion = "xuilab.benchmark.environment/v1";
        public string tier;
        public string unityVersion;
        public string operatingSystem;
        public string processorType;
        public int processorCount;
        public string graphicsDeviceName;
        public string graphicsDeviceType;
        public string graphicsDeviceVersion;
        public int screenWidth;
        public int screenHeight;
        public string qualityLevel;
        public int vSyncCount;
        public int targetFrameRate;
        public string scriptingBackend;
        public string buildType;
        public BenchmarkMetricCapability[] metricCapabilities;
    }

    [Serializable]
    public sealed class BenchmarkIdentityRecord
    {
        public string schemaVersion = "xuilab.benchmark.identity/v1";
        public string runId;
        public string candidateId;
        public string buildId;
        public string sourceRevision;
        public bool dirty;
        public string runnerVersion = "1";
        public string configSha256;
        public string createdUtc;
    }

    public sealed class BenchmarkEventBuffer
    {
        private readonly string[] entries;

        public BenchmarkEventBuffer(int capacity)
        {
            entries = new string[capacity];
        }

        public int Count { get; private set; }

        public void Add(string value)
        {
            if (Count >= entries.Length)
            {
                return;
            }

            entries[Count] = DateTime.UtcNow.ToString("O", CultureInfo.InvariantCulture) + " " + value;
            Count++;
        }

        public string Get(int index)
        {
            return entries[index];
        }
    }

    public sealed class BenchmarkRunResult
    {
        public BenchmarkRunConfig Config;
        public BenchmarkEnvironmentRecord Environment;
        public BenchmarkIdentityRecord Identity;
        public BenchmarkRunState State;
        public BenchmarkFailureCode FailureCode;
        public string FailureReason;
        public BenchmarkCorrectnessStatus Correctness;
        public BenchmarkMeasurementValidity MeasurementValidity;
        public BenchmarkComparisonStatus PerformanceComparison;
        public bool EnteredMeasure;
        public bool ExportSucceeded;
        public bool CleanupSucceeded;
        public BenchmarkSampleBuffer Samples;
        public BenchmarkSummaryStatistics Statistics;
        public BenchmarkEventBuffer Events;

        public bool IsProcessSuccess
        {
            get
            {
                return State == BenchmarkRunState.Completed &&
                       Correctness == BenchmarkCorrectnessStatus.Pass &&
                       MeasurementValidity == BenchmarkMeasurementValidity.Valid &&
                       ExportSucceeded &&
                       CleanupSucceeded;
            }
        }

        public int ExitCode
        {
            get
            {
                if (IsProcessSuccess)
                {
                    return 0;
                }

                if (State == BenchmarkRunState.Cancelled)
                {
                    return 2;
                }

                return State == BenchmarkRunState.Completed ? 3 : 1;
            }
        }
    }

    public interface IBenchmarkArtifactWriter
    {
        string RunDirectory { get; }
        void WriteInitial(BenchmarkRunResult result);
        void WriteTerminal(BenchmarkRunResult result);
    }

    public sealed class FileBenchmarkArtifactWriter : IBenchmarkArtifactWriter
    {
        public string RunDirectory { get; private set; }

        public void WriteInitial(BenchmarkRunResult result)
        {
            if (result == null || result.Config == null)
            {
                throw new ArgumentNullException("result");
            }

            string root = Path.GetFullPath(result.Config.outputDirectory);
            string runDirectory = Path.GetFullPath(Path.Combine(root, result.Config.runId));
            string rootPrefix = root.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar) + Path.DirectorySeparatorChar;
            if (!runDirectory.StartsWith(rootPrefix, StringComparison.OrdinalIgnoreCase))
            {
                throw new InvalidOperationException("Run directory escapes output root.");
            }

            if (Directory.Exists(runDirectory))
            {
                throw new IOException("Run directory already exists: " + result.Config.runId);
            }

            Directory.CreateDirectory(runDirectory);
            RunDirectory = runDirectory;

            if (result.Identity == null)
            {
                throw new ArgumentException("Result identity is required.", "result");
            }

            string configArtifact = SerializeConfigArtifact(result.Config);
            result.Identity.configSha256 = ComputeSha256(configArtifact);
            WriteText("config.json", configArtifact);
            WriteText("environment.json", JsonUtility.ToJson(result.Environment, true) + Environment.NewLine);
            WriteText("identity.json", JsonUtility.ToJson(result.Identity, true) + Environment.NewLine);
            if (result.EnteredMeasure)
            {
                WriteSamples(result.Samples);
            }
        }

        public void WriteTerminal(BenchmarkRunResult result)
        {
            if (string.IsNullOrEmpty(RunDirectory) || !Directory.Exists(RunDirectory))
            {
                throw new InvalidOperationException("Initial artifacts were not written.");
            }

            WriteText("report.md", BuildReport(result));
            WriteEvents(result.Events);
            WriteTextAtomically("summary.json", BuildSummaryJson(result));
        }

        private void WriteSamples(BenchmarkSampleBuffer samples)
        {
            var builder = new StringBuilder(256 + (samples.Count * 96));
            builder.AppendLine("sample_index,unity_frame,elapsed_ms,frame_interval_ms,main_thread_ns,gc_allocated_bytes,system_used_memory_bytes");
            for (int i = 0; i < samples.Count; i++)
            {
                BenchmarkFrameSample sample = samples[i];
                builder.Append(sample.SampleIndex).Append(',');
                builder.Append(sample.UnityFrame).Append(',');
                builder.Append(BenchmarkInvariant.Number(sample.ElapsedMs)).Append(',');
                builder.Append(BenchmarkInvariant.Number(sample.FrameIntervalMs)).Append(',');
                if (sample.MainThreadAvailable)
                {
                    builder.Append(sample.MainThreadNanoseconds.ToString(CultureInfo.InvariantCulture));
                }

                builder.Append(',');
                if (sample.GcAllocatedAvailable)
                {
                    builder.Append(sample.GcAllocatedBytes.ToString(CultureInfo.InvariantCulture));
                }

                builder.Append(',');
                if (sample.SystemUsedMemoryAvailable)
                {
                    builder.Append(sample.SystemUsedMemoryBytes.ToString(CultureInfo.InvariantCulture));
                }

                builder.AppendLine();
            }

            WriteText("samples.csv", builder.ToString());
        }

        private void WriteEvents(BenchmarkEventBuffer eventsBuffer)
        {
            var builder = new StringBuilder();
            for (int i = 0; i < eventsBuffer.Count; i++)
            {
                builder.AppendLine(eventsBuffer.Get(i));
            }

            WriteText("events.log", builder.ToString());
        }

        private void WriteText(string name, string content)
        {
            File.WriteAllText(Path.Combine(RunDirectory, name), content, new UTF8Encoding(false));
        }

        private void WriteTextAtomically(string name, string content)
        {
            string destination = Path.Combine(RunDirectory, name);
            string temporary = destination + ".tmp";
            try
            {
                File.WriteAllText(temporary, content, new UTF8Encoding(false));
                File.Move(temporary, destination);
            }
            finally
            {
                if (File.Exists(temporary))
                {
                    File.Delete(temporary);
                }
            }
        }

        private static string BuildSummaryJson(BenchmarkRunResult result)
        {
            BenchmarkSummaryStatistics stats = result.Statistics ?? new BenchmarkSummaryStatistics();
            var builder = new StringBuilder(1024);
            builder.AppendLine("{");
            AppendJsonString(builder, "schemaVersion", "xuilab.benchmark.summary/v1", true);
            AppendJsonString(builder, "runId", result.Config.runId, true);
            AppendJsonString(builder, "state", Snake(result.State), true);
            AppendJsonString(builder, "failureCode", Snake(result.FailureCode), true);
            AppendJsonString(builder, "failureReason", result.FailureReason ?? string.Empty, true);
            AppendJsonString(builder, "correctness", Snake(result.Correctness), true);
            AppendJsonString(builder, "measurementValidity", Snake(result.MeasurementValidity), true);
            AppendJsonString(builder, "performanceComparison", Snake(result.PerformanceComparison), true);
            builder.Append("  \"processSuccess\": ").Append(result.IsProcessSuccess ? "true" : "false").AppendLine(",");
            builder.Append("  \"exitCode\": ").Append(result.ExitCode.ToString(CultureInfo.InvariantCulture)).AppendLine(",");
            builder.Append("  \"enteredMeasure\": ").Append(result.EnteredMeasure ? "true" : "false").AppendLine(",");
            builder.Append("  \"exportSucceeded\": ").Append(result.ExportSucceeded ? "true" : "false").AppendLine(",");
            builder.Append("  \"cleanupSucceeded\": ").Append(result.CleanupSucceeded ? "true" : "false").AppendLine(",");
            builder.Append("  \"sampleCount\": ").Append(stats.SampleCount).AppendLine(",");
            AppendJsonNumber(builder, "p50FrameIntervalMs", stats.SampleCount > 0, stats.P50FrameIntervalMs, true);
            AppendJsonNumber(builder, "p95FrameIntervalMs", stats.SampleCount > 0, stats.P95FrameIntervalMs, true);
            AppendJsonNumber(builder, "p99FrameIntervalMs", stats.SampleCount > 0, stats.P99FrameIntervalMs, true);
            AppendJsonNumber(builder, "maxFrameIntervalMs", stats.SampleCount > 0, stats.MaxFrameIntervalMs, true);
            AppendJsonNumber(builder, "overBudgetRatio", stats.SampleCount > 0, stats.OverBudgetRatio, true);
            AppendJsonNumber(builder, "meanMainThreadNanoseconds", stats.HasMainThreadSamples, stats.MeanMainThreadNanoseconds, true);
            AppendJsonLong(builder, "totalGcAllocatedBytes", stats.HasGcAllocatedSamples, stats.TotalGcAllocatedBytes, true);
            AppendJsonLong(builder, "lastSystemUsedMemoryBytes", stats.HasSystemMemorySamples, stats.LastSystemUsedMemoryBytes, false);
            builder.AppendLine("}");
            return builder.ToString();
        }

        private static string BuildReport(BenchmarkRunResult result)
        {
            BenchmarkSummaryStatistics stats = result.Statistics ?? new BenchmarkSummaryStatistics();
            var builder = new StringBuilder();
            builder.AppendLine("# XUILab Benchmark Run " + result.Config.runId);
            builder.AppendLine();
            builder.AppendLine("- case: `" + result.Config.caseId + "`");
            builder.AppendLine("- tier: `" + result.Config.tier + "`");
            builder.AppendLine("- state: `" + Snake(result.State) + "`");
            builder.AppendLine("- correctness: `" + Snake(result.Correctness) + "`");
            builder.AppendLine("- measurement validity: `" + Snake(result.MeasurementValidity) + "`");
            builder.AppendLine("- performance comparison: `" + Snake(result.PerformanceComparison) + "`");
            builder.AppendLine("- process success / exit code: `" + (result.IsProcessSuccess ? "true" : "false") + "` / `" + result.ExitCode.ToString(CultureInfo.InvariantCulture) + "`");
            builder.AppendLine("- samples: " + stats.SampleCount.ToString(CultureInfo.InvariantCulture));
            if (stats.SampleCount > 0)
            {
                builder.AppendLine("- frame interval p50 / p95 / p99 / max ms: " +
                    BenchmarkInvariant.Number(stats.P50FrameIntervalMs) + " / " +
                    BenchmarkInvariant.Number(stats.P95FrameIntervalMs) + " / " +
                    BenchmarkInvariant.Number(stats.P99FrameIntervalMs) + " / " +
                    BenchmarkInvariant.Number(stats.MaxFrameIntervalMs));
            }

            if (!string.IsNullOrEmpty(result.FailureReason))
            {
                builder.AppendLine("- failure: `" + Snake(result.FailureCode) + "` — " + result.FailureReason.Replace("\r", " ").Replace("\n", " "));
            }

            builder.AppendLine();
            builder.AppendLine("This is an exploratory single-case run. It does not establish an A/B performance improvement.");
            return builder.ToString();
        }

        private static void AppendJsonString(StringBuilder builder, string name, string value, bool comma)
        {
            builder.Append("  \"").Append(JsonEscape(name)).Append("\": \"").Append(JsonEscape(value ?? string.Empty)).Append('"');
            builder.AppendLine(comma ? "," : string.Empty);
        }

        private static void AppendJsonNumber(StringBuilder builder, string name, bool available, double value, bool comma)
        {
            builder.Append("  \"").Append(JsonEscape(name)).Append("\": ");
            builder.Append(available ? BenchmarkInvariant.Number(value) : "null");
            builder.AppendLine(comma ? "," : string.Empty);
        }

        private static void AppendJsonLong(StringBuilder builder, string name, bool available, long value, bool comma)
        {
            builder.Append("  \"").Append(JsonEscape(name)).Append("\": ");
            builder.Append(available ? value.ToString(CultureInfo.InvariantCulture) : "null");
            builder.AppendLine(comma ? "," : string.Empty);
        }

        private static string JsonEscape(string value)
        {
            return (value ?? string.Empty)
                .Replace("\\", "\\\\")
                .Replace("\"", "\\\"")
                .Replace("\r", "\\r")
                .Replace("\n", "\\n")
                .Replace("\t", "\\t");
        }

        private static string Snake(object value)
        {
            string text = value == null ? "unknown" : value.ToString();
            var builder = new StringBuilder(text.Length + 4);
            for (int i = 0; i < text.Length; i++)
            {
                char c = text[i];
                if (char.IsUpper(c) && i > 0)
                {
                    builder.Append('_');
                }

                builder.Append(char.ToLowerInvariant(c));
            }

            return builder.ToString();
        }

        public static string ComputeSha256(string value)
        {
            using (SHA256 sha = SHA256.Create())
            {
                byte[] hash = sha.ComputeHash(Encoding.UTF8.GetBytes(value ?? string.Empty));
                var builder = new StringBuilder(hash.Length * 2);
                for (int i = 0; i < hash.Length; i++)
                {
                    builder.Append(hash[i].ToString("X2", CultureInfo.InvariantCulture));
                }

                return builder.ToString();
            }
        }

        public static string SerializeConfigArtifact(BenchmarkRunConfig config)
        {
            if (config == null)
            {
                throw new ArgumentNullException("config");
            }

            return JsonUtility.ToJson(config, true) + Environment.NewLine;
        }
    }

    public static class BenchmarkRecordFactory
    {
        public static BenchmarkEnvironmentRecord CaptureEnvironment(BenchmarkRunConfig config, BenchmarkMetricCapability[] capabilities)
        {
            return new BenchmarkEnvironmentRecord
            {
                tier = config.tier,
                unityVersion = Application.unityVersion,
                operatingSystem = SystemInfo.operatingSystem,
                processorType = SystemInfo.processorType,
                processorCount = SystemInfo.processorCount,
                graphicsDeviceName = SystemInfo.graphicsDeviceName,
                graphicsDeviceType = SystemInfo.graphicsDeviceType.ToString(),
                graphicsDeviceVersion = SystemInfo.graphicsDeviceVersion,
                screenWidth = Screen.width,
                screenHeight = Screen.height,
                qualityLevel = QualitySettings.names[QualitySettings.GetQualityLevel()],
                vSyncCount = QualitySettings.vSyncCount,
                targetFrameRate = Application.targetFrameRate,
                scriptingBackend = Type.GetType("Mono.Runtime") != null ? "mono" : "il2cpp-or-unknown",
                buildType = Debug.isDebugBuild ? "development" : "release",
                metricCapabilities = capabilities
            };
        }

        public static BenchmarkIdentityRecord CreateIdentity(BenchmarkRunConfig config)
        {
            string configArtifact = FileBenchmarkArtifactWriter.SerializeConfigArtifact(config);
            return new BenchmarkIdentityRecord
            {
                runId = config.runId,
                candidateId = config.candidateId,
                buildId = config.buildId,
                sourceRevision = config.sourceRevision,
                dirty = config.dirty,
                configSha256 = FileBenchmarkArtifactWriter.ComputeSha256(configArtifact),
                createdUtc = DateTime.UtcNow.ToString("O", CultureInfo.InvariantCulture)
            };
        }
    }
}
