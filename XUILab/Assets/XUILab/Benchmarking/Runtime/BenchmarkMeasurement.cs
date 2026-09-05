using System;
using Unity.Profiling;

namespace XUILab.Benchmarking
{
    public interface IBenchmarkMetricProbeSet : IDisposable
    {
        BenchmarkMetricCapability[] Capabilities { get; }
        bool RequiredMetricsAvailable { get; }
        string RequiredMetricsFailureReason { get; }
        void Prepare(BenchmarkRunConfig config);
        void BeginMeasure();
        void Capture(ref BenchmarkFrameSample sample);
        void Stop();
    }

    public sealed class BenchmarkSampleBuffer
    {
        private readonly BenchmarkFrameSample[] samples;

        public BenchmarkSampleBuffer(int capacity)
        {
            if (capacity <= 0)
            {
                throw new ArgumentOutOfRangeException("capacity");
            }

            samples = new BenchmarkFrameSample[capacity];
        }

        public int Count { get; private set; }
        public int Capacity { get { return samples.Length; } }

        public BenchmarkFrameSample this[int index]
        {
            get
            {
                if (index < 0 || index >= Count)
                {
                    throw new ArgumentOutOfRangeException("index");
                }

                return samples[index];
            }
        }

        public bool TryAdd(BenchmarkFrameSample sample)
        {
            if (Count >= samples.Length)
            {
                return false;
            }

            samples[Count] = sample;
            Count++;
            return true;
        }
    }

    public sealed class UnityProfilerMetricProbeSet : IBenchmarkMetricProbeSet
    {
        private const string FrameIntervalName = "Frame Interval";
        private const string MainThreadName = "Main Thread";
        private const string GcAllocatedName = "GC Allocated In Frame";
        private const string SystemMemoryName = "System Used Memory";

        private ProfilerRecorder mainThread;
        private ProfilerRecorder gcAllocated;
        private ProfilerRecorder systemMemory;
        private bool mainThreadAvailable;
        private bool gcAllocatedAvailable;
        private bool systemMemoryAvailable;
        private bool mainThreadObserved;
        private bool gcAllocatedObserved;
        private bool systemMemoryObserved;
        private bool measureStarted;
        private bool disposed;

        public BenchmarkMetricCapability[] Capabilities { get; private set; }
        public bool RequiredMetricsAvailable { get; private set; }
        public string RequiredMetricsFailureReason { get; private set; }

        public void Prepare(BenchmarkRunConfig config)
        {
            if (Capabilities != null)
            {
                throw new InvalidOperationException("Metric probes are already prepared.");
            }

            mainThread = StartRecorder(config.enableProfilerRecorders, ProfilerCategory.Internal, MainThreadName);
            gcAllocated = StartRecorder(config.enableProfilerRecorders, ProfilerCategory.Memory, GcAllocatedName);
            systemMemory = StartRecorder(config.enableProfilerRecorders, ProfilerCategory.Memory, SystemMemoryName);

            mainThreadAvailable = mainThread.Valid;
            gcAllocatedAvailable = gcAllocated.Valid;
            systemMemoryAvailable = systemMemory.Valid;

            Capabilities = new[]
            {
                CreateCapability(config, FrameIntervalName, "BuiltIn", "Milliseconds", true, string.Empty),
                CreateCapability(config, MainThreadName, "Internal", Unit(mainThread, mainThreadAvailable), mainThreadAvailable, "ProfilerRecorder counter unavailable."),
                CreateCapability(config, GcAllocatedName, "Memory", Unit(gcAllocated, gcAllocatedAvailable), gcAllocatedAvailable, "ProfilerRecorder counter unavailable."),
                CreateCapability(config, SystemMemoryName, "Memory", Unit(systemMemory, systemMemoryAvailable), systemMemoryAvailable, "ProfilerRecorder counter unavailable.")
            };

            RequiredMetricsAvailable = true;
            RequiredMetricsFailureReason = string.Empty;
            for (int i = 0; i < Capabilities.Length; i++)
            {
                BenchmarkMetricCapability capability = Capabilities[i];
                if (capability.required && capability.status != "available")
                {
                    RequiredMetricsAvailable = false;
                    RequiredMetricsFailureReason = "Required metric unavailable: " + capability.name;
                    break;
                }
            }

            string[] required = config.requiredMetrics ?? new string[0];
            for (int i = 0; i < required.Length; i++)
            {
                if (!ContainsCapability(required[i]))
                {
                    RequiredMetricsAvailable = false;
                    RequiredMetricsFailureReason = "Required metric is unknown: " + required[i];
                    break;
                }
            }
        }

        public void BeginMeasure()
        {
            ResetIfValid(ref mainThread, mainThreadAvailable);
            ResetIfValid(ref gcAllocated, gcAllocatedAvailable);
            ResetIfValid(ref systemMemory, systemMemoryAvailable);
            measureStarted = true;
        }

        public void Capture(ref BenchmarkFrameSample sample)
        {
            sample.MainThreadAvailable = HasSample(ref mainThread, mainThreadAvailable) && mainThread.LastValue > 0;
            if (sample.MainThreadAvailable)
            {
                sample.MainThreadNanoseconds = mainThread.LastValue;
                mainThreadObserved = true;
            }

            sample.GcAllocatedAvailable = HasSample(ref gcAllocated, gcAllocatedAvailable);
            if (sample.GcAllocatedAvailable)
            {
                sample.GcAllocatedBytes = gcAllocated.LastValue;
                gcAllocatedObserved = true;
            }

            sample.SystemUsedMemoryAvailable = HasSample(ref systemMemory, systemMemoryAvailable) && systemMemory.LastValue > 0;
            if (sample.SystemUsedMemoryAvailable)
            {
                sample.SystemUsedMemoryBytes = systemMemory.LastValue;
                systemMemoryObserved = true;
            }
        }

        public void Stop()
        {
            StopIfValid(ref mainThread, mainThreadAvailable);
            StopIfValid(ref gcAllocated, gcAllocatedAvailable);
            StopIfValid(ref systemMemory, systemMemoryAvailable);
            if (measureStarted)
            {
                UpdateObservedCapabilities();
            }
        }

        public void Dispose()
        {
            if (disposed)
            {
                return;
            }

            Stop();
            DisposeIfValid(ref mainThread, mainThreadAvailable);
            DisposeIfValid(ref gcAllocated, gcAllocatedAvailable);
            DisposeIfValid(ref systemMemory, systemMemoryAvailable);
            disposed = true;
        }

        private static ProfilerRecorder StartRecorder(bool enabled, ProfilerCategory category, string name)
        {
            if (!enabled)
            {
                return default(ProfilerRecorder);
            }

            try
            {
                return ProfilerRecorder.StartNew(category, name, 1);
            }
            catch
            {
                return default(ProfilerRecorder);
            }
        }

        private static string Unit(ProfilerRecorder recorder, bool available)
        {
            return available ? recorder.UnitType.ToString() : "unknown";
        }

        private static bool HasSample(ref ProfilerRecorder recorder, bool available)
        {
            return available && recorder.Count > 0;
        }

        private void UpdateObservedCapabilities()
        {
            UpdateObservedCapability(Capabilities[1], mainThreadObserved);
            UpdateObservedCapability(Capabilities[2], gcAllocatedObserved);
            UpdateObservedCapability(Capabilities[3], systemMemoryObserved);

            RequiredMetricsAvailable = true;
            RequiredMetricsFailureReason = string.Empty;
            for (int i = 0; i < Capabilities.Length; i++)
            {
                BenchmarkMetricCapability capability = Capabilities[i];
                if (capability.required && capability.status != "available")
                {
                    RequiredMetricsAvailable = false;
                    RequiredMetricsFailureReason = "Required metric unavailable: " + capability.name;
                    return;
                }
            }
        }

        private static void UpdateObservedCapability(BenchmarkMetricCapability capability, bool observed)
        {
            if (capability.status == "available" && !observed)
            {
                capability.status = "unavailable";
                capability.reason = "ProfilerRecorder produced no usable samples.";
            }
        }

        private static void ResetIfValid(ref ProfilerRecorder recorder, bool available)
        {
            if (available)
            {
                recorder.Reset();
            }
        }

        private static void StopIfValid(ref ProfilerRecorder recorder, bool available)
        {
            if (available && recorder.IsRunning)
            {
                recorder.Stop();
            }
        }

        private static void DisposeIfValid(ref ProfilerRecorder recorder, bool available)
        {
            if (available)
            {
                recorder.Dispose();
            }
        }

        private BenchmarkMetricCapability CreateCapability(
            BenchmarkRunConfig config,
            string name,
            string category,
            string unit,
            bool available,
            string unavailableReason)
        {
            bool required = Contains(config.requiredMetrics, name);
            return new BenchmarkMetricCapability
            {
                name = name,
                category = category,
                unit = unit,
                required = required,
                status = available ? "available" : "unavailable",
                reason = available ? string.Empty : unavailableReason
            };
        }

        private bool ContainsCapability(string name)
        {
            if (Capabilities == null)
            {
                return false;
            }

            for (int i = 0; i < Capabilities.Length; i++)
            {
                if (string.Equals(Capabilities[i].name, name, StringComparison.Ordinal))
                {
                    return true;
                }
            }

            return false;
        }

        private static bool Contains(string[] values, string value)
        {
            if (values == null)
            {
                return false;
            }

            for (int i = 0; i < values.Length; i++)
            {
                if (string.Equals(values[i], value, StringComparison.Ordinal))
                {
                    return true;
                }
            }

            return false;
        }
    }

    public static class BenchmarkStatistics
    {
        public static BenchmarkSummaryStatistics Calculate(BenchmarkSampleBuffer buffer, double frameBudgetMs)
        {
            if (buffer == null)
            {
                throw new ArgumentNullException("buffer");
            }

            if (buffer.Count == 0)
            {
                return new BenchmarkSummaryStatistics();
            }

            double[] intervals = new double[buffer.Count];
            int overBudget = 0;
            long mainThreadTotal = 0;
            int mainThreadCount = 0;
            long gcAllocatedTotal = 0;
            bool hasGc = false;
            bool hasSystemMemory = false;
            long lastSystemMemory = 0;

            for (int i = 0; i < buffer.Count; i++)
            {
                BenchmarkFrameSample sample = buffer[i];
                double interval = sample.FrameIntervalMs;
                if (double.IsNaN(interval) || double.IsInfinity(interval) || interval < 0)
                {
                    throw new InvalidOperationException("Frame interval sample must be finite and non-negative.");
                }

                intervals[i] = interval;
                if (interval > frameBudgetMs)
                {
                    overBudget++;
                }

                if (sample.MainThreadAvailable)
                {
                    mainThreadTotal += sample.MainThreadNanoseconds;
                    mainThreadCount++;
                }

                if (sample.GcAllocatedAvailable)
                {
                    gcAllocatedTotal += sample.GcAllocatedBytes;
                    hasGc = true;
                }

                if (sample.SystemUsedMemoryAvailable)
                {
                    lastSystemMemory = sample.SystemUsedMemoryBytes;
                    hasSystemMemory = true;
                }
            }

            Array.Sort(intervals);
            return new BenchmarkSummaryStatistics
            {
                SampleCount = buffer.Count,
                P50FrameIntervalMs = PercentileSorted(intervals, 0.50),
                P95FrameIntervalMs = PercentileSorted(intervals, 0.95),
                P99FrameIntervalMs = PercentileSorted(intervals, 0.99),
                MaxFrameIntervalMs = intervals[intervals.Length - 1],
                OverBudgetRatio = (double)overBudget / buffer.Count,
                HasMainThreadSamples = mainThreadCount > 0,
                MeanMainThreadNanoseconds = mainThreadCount > 0 ? (double)mainThreadTotal / mainThreadCount : 0,
                HasGcAllocatedSamples = hasGc,
                TotalGcAllocatedBytes = gcAllocatedTotal,
                HasSystemMemorySamples = hasSystemMemory,
                LastSystemUsedMemoryBytes = lastSystemMemory
            };
        }

        public static double Percentile(double[] values, double percentile)
        {
            if (values == null || values.Length == 0)
            {
                throw new ArgumentException("Percentile requires at least one value.", "values");
            }

            double[] copy = (double[])values.Clone();
            Array.Sort(copy);
            return PercentileSorted(copy, percentile);
        }

        private static double PercentileSorted(double[] sorted, double percentile)
        {
            if (percentile < 0 || percentile > 1 || double.IsNaN(percentile))
            {
                throw new ArgumentOutOfRangeException("percentile");
            }

            if (sorted.Length == 1)
            {
                return sorted[0];
            }

            double index = (sorted.Length - 1) * percentile;
            int lower = (int)Math.Floor(index);
            int upper = (int)Math.Ceiling(index);
            if (lower == upper)
            {
                return sorted[lower];
            }

            double weight = index - lower;
            return sorted[lower] + ((sorted[upper] - sorted[lower]) * weight);
        }
    }
}
