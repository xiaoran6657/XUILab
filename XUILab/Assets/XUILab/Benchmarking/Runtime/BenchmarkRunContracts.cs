using System;
using System.Globalization;
using System.IO;

namespace XUILab.Benchmarking
{
    public enum BenchmarkRunState
    {
        Idle,
        Prepare,
        Warmup,
        Measure,
        Validate,
        Export,
        Cleanup,
        Completed,
        Failed,
        Cancelled
    }

    public enum BenchmarkCorrectnessStatus
    {
        NotRun,
        Pass,
        Fail
    }

    public enum BenchmarkMeasurementValidity
    {
        NotAssessed,
        Valid,
        Invalid
    }

    public enum BenchmarkComparisonStatus
    {
        NotAssessed,
        Improved,
        Regressed,
        NoClearDifference,
        Inconclusive
    }

    public enum BenchmarkFailureCode
    {
        None,
        ConfigurationInvalid,
        UnknownCase,
        PrepareFailed,
        ReadyTimeout,
        RequiredMetricUnavailable,
        SampleCapacityExceeded,
        SampleShortage,
        CaseValidationFailed,
        CaseException,
        ExportFailed,
        Cancelled,
        UnexpectedException
    }

    [Serializable]
    public sealed class BenchmarkFaultPlan
    {
        public string mode = "none";
        public int triggerMeasureFrame;
        public int shortageSampleCount = 1;

        public string Validate(int measureFrames)
        {
            switch (mode)
            {
                case "none":
                case "prepare_failure":
                case "ready_timeout":
                case "required_metric_unavailable":
                case "sample_shortage":
                case "cancel":
                case "case_exception":
                case "export_failure":
                case "cleanup_failure":
                case "focus_loss":
                case "pause":
                    break;
                default:
                    return "faultPlan.mode is unsupported.";
            }

            if (triggerMeasureFrame < 0)
            {
                return "faultPlan.triggerMeasureFrame cannot be negative.";
            }

            if (mode == "sample_shortage" &&
                (shortageSampleCount < 0 || shortageSampleCount >= measureFrames))
            {
                return "sample_shortage requires shortageSampleCount in [0, measureFrames).";
            }

            bool usesMeasureTrigger = mode == "cancel" ||
                                      mode == "case_exception" ||
                                      mode == "focus_loss" ||
                                      mode == "pause";
            if (usesMeasureTrigger && triggerMeasureFrame >= measureFrames)
            {
                return "Measure-triggered faults require triggerMeasureFrame in [0, measureFrames).";
            }

            return null;
        }
    }

    [Serializable]
    public sealed class BenchmarkRunConfig
    {
        public string schemaVersion = "xuilab.benchmark.config/v1";
        public string protocolVersion = "xuilab.benchmark.protocol/v1";
        public string runId = string.Empty;
        public string seriesId = "m0-exploratory";
        public int runIndex;
        public int plannedRepeatCount = 5;
        public string tier = "unknown";
        public string caseId = "idle";
        public string caseVersion = "1";
        public int seed = 1337;
        public int warmupFrames = 300;
        public int measureFrames = 1800;
        public int sampleCapacity = 1800;
        public int readyTimeoutFrames = 300;
        public double frameBudgetMs = 16.6666667;
        public int targetFrameRate = 60;
        public int vSyncCount;
        public bool enableProfilerRecorders = true;
        public string[] requiredMetrics = { "Frame Interval" };
        public string[] optionalMetrics = { "Main Thread", "GC Allocated In Frame", "System Used Memory" };
        public int cpuIterationsPerFrame;
        public int allocationBytesPerFrame;
        public string outputDirectory = string.Empty;
        public string candidateId = "unknown";
        public string buildId = "unknown";
        public string sourceRevision = "unknown";
        public bool dirty = true;
        public bool quitWhenDone;
        public BenchmarkFaultPlan faultPlan = new BenchmarkFaultPlan();

        public string Validate()
        {
            if (schemaVersion != "xuilab.benchmark.config/v1")
            {
                return "Unsupported config schemaVersion.";
            }

            if (protocolVersion != "xuilab.benchmark.protocol/v1")
            {
                return "Unsupported protocolVersion.";
            }

            if (requiredMetrics == null ||
                requiredMetrics.Length != 1 ||
                !string.Equals(requiredMetrics[0], "Frame Interval", StringComparison.Ordinal))
            {
                return "Protocol v1 requires exactly one required metric: Frame Interval.";
            }

            if (!IsSafeRunId(runId))
            {
                return "runId must be one safe path segment.";
            }

            if (caseId != "idle" && caseId != "known-load" && !IsListCaseId(caseId) && !IsGradientCaseId(caseId) && !IsListRefreshCaseId(caseId))
            {
                return "caseId must be a supported benchmark profile.";
            }

            if (warmupFrames < 0 || measureFrames <= 0 || sampleCapacity < measureFrames)
            {
                return "Frame counts must be non-negative and sampleCapacity must cover measureFrames.";
            }

            if (plannedRepeatCount <= 0 || runIndex < 0)
            {
                return "plannedRepeatCount must be positive and runIndex cannot be negative.";
            }

            if (string.IsNullOrWhiteSpace(seriesId))
            {
                return "seriesId is required.";
            }

            if (readyTimeoutFrames <= 0 || frameBudgetMs <= 0 || double.IsNaN(frameBudgetMs) || double.IsInfinity(frameBudgetMs))
            {
                return "Timeout and frame budget must be finite positive values.";
            }

            if (cpuIterationsPerFrame < 0 || allocationBytesPerFrame < 0)
            {
                return "Known-load settings cannot be negative.";
            }

            if (string.IsNullOrWhiteSpace(outputDirectory))
            {
                return "outputDirectory is required.";
            }

            if (IsUnknownIdentity(candidateId) || IsUnknownIdentity(buildId) || IsUnknownIdentity(sourceRevision))
            {
                return "candidateId, buildId, and sourceRevision must be explicit.";
            }

            if (faultPlan == null)
            {
                return "faultPlan is required.";
            }

            string faultError = faultPlan.Validate(measureFrames);
            if (faultError != null)
            {
                return faultError;
            }

            return null;
        }

        private static bool IsUnknownIdentity(string value)
        {
            return string.IsNullOrWhiteSpace(value) || string.Equals(value, "unknown", StringComparison.OrdinalIgnoreCase);
        }

        public static bool IsListCaseId(string value)
        {
            return value != null && System.Text.RegularExpressions.Regex.IsMatch(value,
                @"\Alist-(normal|virtual)-(100|300|1000|10000)-(scroll|lifecycle)\z",
                System.Text.RegularExpressions.RegexOptions.CultureInvariant);
        }

        public static bool IsListRefreshCaseId(string value)
        {
            return value != null && System.Text.RegularExpressions.Regex.IsMatch(value,
                @"\Alistrefresh-(normal|virtual)-1000-(window|target)-(idle|sparse|burst|high|batch)\z",
                System.Text.RegularExpressions.RegexOptions.CultureInvariant);
        }

        public static bool IsGradientCaseId(string value)
        {
            return value != null && System.Text.RegularExpressions.Regex.IsMatch(value,
                @"\A(?:gradient-(grid|split|clip|large)-(1|100|500|1000|2000|5000)-(image|disabled|linear|static|same|few|all)-(horizontal|vertical)-(05|25|95)|gradient-subdivision-(large|grid)-(static-(05|50|95)|dynamic)-s(8|16|32|64)|gradient-adaptive-(large|grid)-(static-(05|50|95)|dynamic)-(fixed32|adaptive64))\z",
                System.Text.RegularExpressions.RegexOptions.CultureInvariant);
        }

        public static bool IsSafeRunId(string value)
        {
            if (string.IsNullOrWhiteSpace(value) || value == "." || value == "..")
            {
                return false;
            }

            if (value.IndexOfAny(Path.GetInvalidFileNameChars()) >= 0 || value.Contains("/") || value.Contains("\\"))
            {
                return false;
            }

            return string.Equals(Path.GetFileName(value), value, StringComparison.Ordinal);
        }
    }

    public struct BenchmarkFrameSample
    {
        public int SampleIndex;
        public int UnityFrame;
        public double ElapsedMs;
        public double FrameIntervalMs;
        public bool MainThreadAvailable;
        public long MainThreadNanoseconds;
        public bool GcAllocatedAvailable;
        public long GcAllocatedBytes;
        public bool SystemUsedMemoryAvailable;
        public long SystemUsedMemoryBytes;
    }

    [Serializable]
    public sealed class BenchmarkMetricCapability
    {
        public string name;
        public string category;
        public string unit;
        public bool required;
        public string status;
        public string reason;
    }

    public struct BenchmarkCaseValidation
    {
        public bool Passed;
        public string Reason;

        public static BenchmarkCaseValidation Pass()
        {
            return new BenchmarkCaseValidation { Passed = true, Reason = string.Empty };
        }

        public static BenchmarkCaseValidation Fail(string reason)
        {
            return new BenchmarkCaseValidation { Passed = false, Reason = reason ?? "Case validation failed." };
        }
    }

    public sealed class BenchmarkSummaryStatistics
    {
        public int SampleCount;
        public double P50FrameIntervalMs;
        public double P95FrameIntervalMs;
        public double P99FrameIntervalMs;
        public double MaxFrameIntervalMs;
        public double OverBudgetRatio;
        public bool HasMainThreadSamples;
        public double MeanMainThreadNanoseconds;
        public bool HasGcAllocatedSamples;
        public long TotalGcAllocatedBytes;
        public bool HasSystemMemorySamples;
        public long LastSystemUsedMemoryBytes;
    }

    public static class BenchmarkInvariant
    {
        public static string Number(double value)
        {
            return value.ToString("0.########", CultureInfo.InvariantCulture);
        }
    }
}
