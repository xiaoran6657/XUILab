using System;

namespace XUILab.Benchmarking
{
    public interface IBenchmarkFaultInjector
    {
        void Configure(BenchmarkRunConfig config);
        bool ForceNotReady { get; }
        bool ForceRequiredMetricUnavailable { get; }
        string RequiredMetricFailureReason { get; }
        void BeforeCasePrepare();
        bool ShouldCancel(int measuredSamples);
        bool ShouldEndMeasure(int measuredSamples);
        void BeforeCaseMeasure(int sampleIndex);
        bool ShouldMarkFocusLost(int measuredSamples);
        bool ShouldMarkPaused(int measuredSamples);
        void BeforeExport();
        void BeforeCleanup();
    }

    public sealed class ConfigurableBenchmarkFaultInjector : IBenchmarkFaultInjector
    {
        private BenchmarkFaultPlan plan;
        private bool focusInjected;
        private bool pauseInjected;

        public bool ForceNotReady { get { return plan != null && plan.mode == "ready_timeout"; } }
        public bool ForceRequiredMetricUnavailable { get { return plan != null && plan.mode == "required_metric_unavailable"; } }
        public string RequiredMetricFailureReason { get { return "Required metric unavailable by explicit fault plan."; } }

        public void Configure(BenchmarkRunConfig config)
        {
            plan = config == null ? null : config.faultPlan;
            focusInjected = false;
            pauseInjected = false;
        }

        public void BeforeCasePrepare()
        {
            ThrowIf("prepare_failure", "Injected Prepare failure.");
        }

        public bool ShouldCancel(int measuredSamples)
        {
            return IsTriggered("cancel", measuredSamples);
        }

        public bool ShouldEndMeasure(int measuredSamples)
        {
            return plan != null && plan.mode == "sample_shortage" && measuredSamples >= plan.shortageSampleCount;
        }

        public void BeforeCaseMeasure(int sampleIndex)
        {
            if (IsTriggered("case_exception", sampleIndex))
            {
                throw new BenchmarkInjectedFaultException("Injected Case exception.");
            }
        }

        public bool ShouldMarkFocusLost(int measuredSamples)
        {
            if (!focusInjected && IsTriggered("focus_loss", measuredSamples))
            {
                focusInjected = true;
                return true;
            }

            return false;
        }

        public bool ShouldMarkPaused(int measuredSamples)
        {
            if (!pauseInjected && IsTriggered("pause", measuredSamples))
            {
                pauseInjected = true;
                return true;
            }

            return false;
        }

        public void BeforeExport()
        {
            ThrowIf("export_failure", "Injected Export failure.");
        }

        public void BeforeCleanup()
        {
            ThrowIf("cleanup_failure", "Injected Cleanup failure.");
        }

        private bool IsTriggered(string mode, int measuredSamples)
        {
            return plan != null && plan.mode == mode && measuredSamples >= plan.triggerMeasureFrame;
        }

        private void ThrowIf(string mode, string message)
        {
            if (plan != null && plan.mode == mode)
            {
                throw new BenchmarkInjectedFaultException(message);
            }
        }
    }

    public sealed class BenchmarkInjectedFaultException : Exception
    {
        public BenchmarkInjectedFaultException(string message) : base(message) { }
    }
}
