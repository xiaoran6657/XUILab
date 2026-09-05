using System;
using UnityEngine;

namespace XUILab.Benchmarking
{
    public sealed class BenchmarkRunner : IDisposable
    {
        private readonly IBenchmarkCaseFactory caseFactory;
        private readonly IBenchmarkMetricProbeSet metrics;
        private readonly IBenchmarkArtifactWriter writer;
        private readonly IBenchmarkFaultInjector faults;
        private readonly Func<bool> isDebugBuild;
        private BenchmarkRunConfig config;
        private IBenchmarkCase benchmarkCase;
        private BenchmarkSampleBuffer samples;
        private BenchmarkEventBuffer eventsBuffer;
        private BenchmarkEnvironmentRecord environment;
        private BenchmarkIdentityRecord identity;
        private BenchmarkSummaryStatistics statistics;
        private BenchmarkRunResult result;
        private int warmupFrame;
        private int readyWaitFrame;
        private double elapsedMeasureMs;
        private int originalTargetFrameRate;
        private int originalVSyncCount;
        private bool settingsCaptured;
        private bool cancellationRequested;
        private bool enteredMeasure;
        private bool cleanupExecuted;
        private bool exportStarted;
        private bool exportSucceeded;
        private bool cleanupSucceeded;
        private bool externalInvalid;
        private string externalInvalidReason = string.Empty;
        private BenchmarkFailureCode failureCode;
        private string failureReason = string.Empty;
        private BenchmarkCorrectnessStatus correctness = BenchmarkCorrectnessStatus.NotRun;
        private BenchmarkMeasurementValidity measurementValidity = BenchmarkMeasurementValidity.NotAssessed;
        private bool requiredMetricsAvailable = true;
        private string requiredMetricsFailureReason = string.Empty;

        public BenchmarkRunner(
            IBenchmarkCaseFactory caseFactory = null,
            IBenchmarkMetricProbeSet metrics = null,
            IBenchmarkArtifactWriter writer = null,
            IBenchmarkFaultInjector faults = null,
            Func<bool> isDebugBuild = null)
        {
            this.caseFactory = caseFactory ?? new BenchmarkCaseFactory();
            this.metrics = metrics ?? new UnityProfilerMetricProbeSet();
            this.writer = writer ?? new FileBenchmarkArtifactWriter();
            this.faults = faults ?? new ConfigurableBenchmarkFaultInjector();
            this.isDebugBuild = isDebugBuild ?? (() => Debug.isDebugBuild);
        }

        public BenchmarkRunState State { get; private set; }
        public bool IsTerminal
        {
            get
            {
                return State == BenchmarkRunState.Completed ||
                       State == BenchmarkRunState.Failed ||
                       State == BenchmarkRunState.Cancelled;
            }
        }

        public BenchmarkRunResult Result { get { return result; } }
        public string RunDirectory { get { return writer.RunDirectory; } }

        public void Start(BenchmarkRunConfig runConfig)
        {
            if (State != BenchmarkRunState.Idle)
            {
                throw new InvalidOperationException("Runner can only start from Idle.");
            }

            config = runConfig ?? throw new ArgumentNullException("runConfig");
            eventsBuffer = new BenchmarkEventBuffer(64);
            Transition(BenchmarkRunState.Prepare);

            try
            {
                string validationError = config.Validate();
                if (validationError != null)
                {
                    Fail(BenchmarkFailureCode.ConfigurationInvalid, validationError);
                    return;
                }

                originalTargetFrameRate = Application.targetFrameRate;
                originalVSyncCount = QualitySettings.vSyncCount;
                settingsCaptured = true;

                faults.Configure(config);
                if (config.faultPlan.mode != "none" && !isDebugBuild())
                {
                    Fail(BenchmarkFailureCode.ConfigurationInvalid, "Fault plans require a Development or Editor build.");
                    return;
                }

                Application.targetFrameRate = config.targetFrameRate;
                QualitySettings.vSyncCount = config.vSyncCount;

                samples = new BenchmarkSampleBuffer(config.sampleCapacity);
                benchmarkCase = caseFactory.Create(config);
                if (benchmarkCase == null)
                {
                    Fail(BenchmarkFailureCode.UnknownCase, "Case factory returned null.");
                    return;
                }

                metrics.Prepare(config);
                requiredMetricsAvailable = metrics.RequiredMetricsAvailable;
                requiredMetricsFailureReason = metrics.RequiredMetricsFailureReason;
                if (faults.ForceRequiredMetricUnavailable)
                {
                    requiredMetricsAvailable = false;
                    requiredMetricsFailureReason = faults.RequiredMetricFailureReason;
                    MarkRequiredCapabilitiesUnavailable(metrics.Capabilities, requiredMetricsFailureReason);
                }

                environment = BenchmarkRecordFactory.CaptureEnvironment(config, metrics.Capabilities);
                identity = BenchmarkRecordFactory.CreateIdentity(config);
                if (!requiredMetricsAvailable)
                {
                    measurementValidity = BenchmarkMeasurementValidity.Invalid;
                    externalInvalid = true;
                    externalInvalidReason = requiredMetricsFailureReason;
                    failureCode = BenchmarkFailureCode.RequiredMetricUnavailable;
                    failureReason = requiredMetricsFailureReason;
                }

                faults.BeforeCasePrepare();
                benchmarkCase.Prepare(config);
                Transition(BenchmarkRunState.Warmup);
            }
            catch (Exception exception)
            {
                Fail(BenchmarkFailureCode.PrepareFailed, exception.GetType().Name + ": " + exception.Message);
            }
        }

        public void Tick(double frameIntervalMs, int unityFrame)
        {
            if (IsTerminal || State == BenchmarkRunState.Idle)
            {
                return;
            }

            if (cancellationRequested)
            {
                CancelNow();
                return;
            }

            try
            {
                switch (State)
                {
                    case BenchmarkRunState.Warmup:
                        TickWarmup();
                        break;
                    case BenchmarkRunState.Measure:
                        TickMeasure(frameIntervalMs, unityFrame);
                        break;
                    case BenchmarkRunState.Validate:
                        Validate();
                        break;
                    case BenchmarkRunState.Export:
                        ExportAndComplete();
                        break;
                }
            }
            catch (BenchmarkInjectedFaultException exception)
            {
                Fail(BenchmarkFailureCode.CaseException, exception.Message);
            }
            catch (Exception exception)
            {
                Fail(BenchmarkFailureCode.UnexpectedException, exception.GetType().Name + ": " + exception.Message);
            }
        }

        public void RequestCancel()
        {
            cancellationRequested = true;
        }

        public void MarkFocusLost()
        {
            externalInvalid = true;
            externalInvalidReason = "Application focus was lost during the run.";
            if (eventsBuffer != null)
            {
                eventsBuffer.Add("focus_lost");
            }
        }

        public void MarkPaused()
        {
            externalInvalid = true;
            externalInvalidReason = "Application pause was observed during the run.";
            if (eventsBuffer != null)
            {
                eventsBuffer.Add("application_paused");
            }
        }

        public void Dispose()
        {
            if (!cleanupExecuted)
            {
                CleanupOnce();
            }
        }

        private void TickWarmup()
        {
            if (faults.ForceNotReady || !benchmarkCase.IsReady)
            {
                readyWaitFrame++;
                if (readyWaitFrame >= config.readyTimeoutFrames)
                {
                    Fail(BenchmarkFailureCode.ReadyTimeout, "Case did not become ready before readyTimeoutFrames.");
                }

                return;
            }

            if (warmupFrame < config.warmupFrames)
            {
                benchmarkCase.TickWarmup(warmupFrame);
                warmupFrame++;
                return;
            }

            benchmarkCase.BeginMeasure();
            metrics.BeginMeasure();
            enteredMeasure = true;
            eventsBuffer.Add("measure_started");
            Transition(BenchmarkRunState.Measure);
            ScheduleMeasureAction(samples.Count);
        }

        private void TickMeasure(double frameIntervalMs, int unityFrame)
        {
            if (double.IsNaN(frameIntervalMs) || double.IsInfinity(frameIntervalMs) || frameIntervalMs < 0)
            {
                throw new InvalidOperationException("Frame interval must be finite and non-negative.");
            }

            int sampleIndex = samples.Count;
            elapsedMeasureMs += frameIntervalMs;

            var sample = new BenchmarkFrameSample
            {
                SampleIndex = sampleIndex,
                UnityFrame = unityFrame,
                ElapsedMs = elapsedMeasureMs,
                FrameIntervalMs = frameIntervalMs
            };
            metrics.Capture(ref sample);
            if (!samples.TryAdd(sample))
            {
                Fail(BenchmarkFailureCode.SampleCapacityExceeded, "Preallocated sample buffer capacity was exceeded.");
                return;
            }

            if (samples.Count >= config.measureFrames)
            {
                FinishMeasure("measure_completed samples=" + samples.Count);
                return;
            }

            ScheduleMeasureAction(samples.Count);
        }

        private void ScheduleMeasureAction(int actionIndex)
        {
            if (faults.ShouldCancel(actionIndex))
            {
                CancelNow();
                return;
            }

            if (faults.ShouldMarkFocusLost(actionIndex))
            {
                MarkFocusLost();
            }

            if (faults.ShouldMarkPaused(actionIndex))
            {
                MarkPaused();
            }

            if (faults.ShouldEndMeasure(actionIndex))
            {
                FinishMeasure("measure_forced_shortage samples=" + samples.Count);
                return;
            }

            faults.BeforeCaseMeasure(actionIndex);
            benchmarkCase.TickMeasure(actionIndex);
        }

        private void FinishMeasure(string eventText)
        {
            metrics.Stop();
            requiredMetricsAvailable = requiredMetricsAvailable && metrics.RequiredMetricsAvailable;
            if (!requiredMetricsAvailable && string.IsNullOrEmpty(requiredMetricsFailureReason))
            {
                requiredMetricsFailureReason = metrics.RequiredMetricsFailureReason;
            }

            benchmarkCase.EndMeasure();
            eventsBuffer.Add(eventText);
            Transition(BenchmarkRunState.Validate);
        }

        private void Validate()
        {
            statistics = BenchmarkStatistics.Calculate(samples, config.frameBudgetMs);
            BenchmarkCaseValidation caseValidation = benchmarkCase.Validate();
            correctness = caseValidation.Passed ? BenchmarkCorrectnessStatus.Pass : BenchmarkCorrectnessStatus.Fail;
            if (!caseValidation.Passed)
            {
                failureCode = BenchmarkFailureCode.CaseValidationFailed;
                failureReason = caseValidation.Reason;
            }

            if (samples.Count < config.measureFrames)
            {
                measurementValidity = BenchmarkMeasurementValidity.Invalid;
                failureCode = BenchmarkFailureCode.SampleShortage;
                failureReason = "Measured sample count is below measureFrames.";
            }
            else if (!requiredMetricsAvailable)
            {
                measurementValidity = BenchmarkMeasurementValidity.Invalid;
                failureCode = BenchmarkFailureCode.RequiredMetricUnavailable;
                failureReason = requiredMetricsFailureReason;
            }
            else if (externalInvalid)
            {
                measurementValidity = BenchmarkMeasurementValidity.Invalid;
                failureReason = externalInvalidReason;
            }
            else
            {
                measurementValidity = BenchmarkMeasurementValidity.Valid;
            }

            eventsBuffer.Add("validation correctness=" + correctness + " validity=" + measurementValidity);
            Transition(BenchmarkRunState.Export);
        }

        private void ExportAndComplete()
        {
            exportStarted = true;
            result = BuildResult(BenchmarkRunState.Export);
            bool initialWritten = false;
            try
            {
                faults.BeforeExport();
                writer.WriteInitial(result);
                initialWritten = true;
            }
            catch (Exception exception)
            {
                failureCode = BenchmarkFailureCode.ExportFailed;
                failureReason = exception.GetType().Name + ": " + exception.Message;
            }

            Transition(BenchmarkRunState.Cleanup);
            CleanupOnce();
            exportSucceeded = initialWritten;
            Transition(initialWritten && cleanupSucceeded ? BenchmarkRunState.Completed : BenchmarkRunState.Failed);
            result = BuildResult(State);

            if (initialWritten || !string.IsNullOrEmpty(writer.RunDirectory))
            {
                try
                {
                    writer.WriteTerminal(result);
                }
                catch (Exception exception)
                {
                    failureCode = BenchmarkFailureCode.ExportFailed;
                    failureReason = exception.GetType().Name + ": " + exception.Message;
                    exportSucceeded = false;
                    State = BenchmarkRunState.Failed;
                    result = BuildResult(State);
                }
            }
        }

        private void CancelNow()
        {
            failureCode = BenchmarkFailureCode.Cancelled;
            failureReason = "Run cancellation was requested.";
            measurementValidity = enteredMeasure
                ? BenchmarkMeasurementValidity.Invalid
                : BenchmarkMeasurementValidity.NotAssessed;
            eventsBuffer.Add("cancel_requested state=" + State);
            Transition(BenchmarkRunState.Cleanup);
            CleanupOnce();
            Transition(BenchmarkRunState.Cancelled);
            TryWriteFailureArtifacts();
        }

        private void Fail(BenchmarkFailureCode code, string reason)
        {
            failureCode = code;
            failureReason = reason ?? "Benchmark run failed.";
            measurementValidity = enteredMeasure
                ? BenchmarkMeasurementValidity.Invalid
                : BenchmarkMeasurementValidity.NotAssessed;
            if (eventsBuffer != null)
            {
                eventsBuffer.Add("failure code=" + code + " reason=" + failureReason);
            }

            try
            {
                metrics.Stop();
            }
            catch
            {
                // Preserve the primary failure.
            }

            if (State != BenchmarkRunState.Cleanup)
            {
                Transition(BenchmarkRunState.Cleanup);
            }

            CleanupOnce();
            Transition(BenchmarkRunState.Failed);
            TryWriteFailureArtifacts();
        }

        private void TryWriteFailureArtifacts()
        {
            if (config == null || config.Validate() != null || exportStarted)
            {
                result = BuildResult(State);
                return;
            }

            if (environment == null)
            {
                environment = BenchmarkRecordFactory.CaptureEnvironment(config, metrics.Capabilities ?? new BenchmarkMetricCapability[0]);
            }

            if (identity == null)
            {
                identity = BenchmarkRecordFactory.CreateIdentity(config);
            }

            if (statistics == null)
            {
                statistics = samples != null && samples.Count > 0
                    ? BenchmarkStatistics.Calculate(samples, config.frameBudgetMs)
                    : new BenchmarkSummaryStatistics();
            }

            result = BuildResult(State);
            try
            {
                writer.WriteInitial(result);
                exportSucceeded = true;
                result = BuildResult(State);
                writer.WriteTerminal(result);
            }
            catch
            {
                exportSucceeded = false;
                result = BuildResult(State);
            }
        }

        private void CleanupOnce()
        {
            if (cleanupExecuted)
            {
                return;
            }

            cleanupExecuted = true;
            cleanupSucceeded = true;

            try
            {
                faults.BeforeCleanup();
            }
            catch (Exception exception)
            {
                RecordCleanupFailure("fault hook", exception);
            }

            try
            {
                metrics.Stop();
            }
            catch (Exception exception)
            {
                RecordCleanupFailure("metric stop", exception);
            }

            try
            {
                if (benchmarkCase != null)
                {
                    benchmarkCase.Cleanup();
                }
            }
            catch (Exception exception)
            {
                RecordCleanupFailure("case cleanup", exception);
            }

            try
            {
                metrics.Dispose();
            }
            catch (Exception exception)
            {
                RecordCleanupFailure("metric dispose", exception);
            }

            try
            {
                if (settingsCaptured)
                {
                    Application.targetFrameRate = originalTargetFrameRate;
                    QualitySettings.vSyncCount = originalVSyncCount;
                }
            }
            catch (Exception exception)
            {
                RecordCleanupFailure("setting restore", exception);
            }

            if (eventsBuffer != null)
            {
                eventsBuffer.Add("cleanup completed=" + cleanupSucceeded);
            }
        }

        private void RecordCleanupFailure(string operation, Exception exception)
        {
            cleanupSucceeded = false;
            if (eventsBuffer != null)
            {
                eventsBuffer.Add("cleanup_failure operation=" + operation + " type=" + exception.GetType().Name);
            }

            if (failureCode == BenchmarkFailureCode.None)
            {
                failureCode = BenchmarkFailureCode.UnexpectedException;
                failureReason = "Cleanup failed during " + operation + ": " + exception.GetType().Name + ": " + exception.Message;
            }
        }

        private static void MarkRequiredCapabilitiesUnavailable(
            BenchmarkMetricCapability[] capabilities,
            string reason)
        {
            if (capabilities == null)
            {
                return;
            }

            for (int i = 0; i < capabilities.Length; i++)
            {
                if (capabilities[i].required)
                {
                    capabilities[i].status = "unavailable";
                    capabilities[i].reason = reason;
                }
            }
        }

        private BenchmarkRunResult BuildResult(BenchmarkRunState finalState)
        {
            return new BenchmarkRunResult
            {
                Config = config,
                Environment = environment,
                Identity = identity,
                State = finalState,
                FailureCode = failureCode,
                FailureReason = failureReason,
                Correctness = correctness,
                MeasurementValidity = measurementValidity,
                PerformanceComparison = BenchmarkComparisonStatus.NotAssessed,
                EnteredMeasure = enteredMeasure,
                ExportSucceeded = exportSucceeded,
                CleanupSucceeded = cleanupSucceeded,
                Samples = samples,
                Statistics = statistics,
                Events = eventsBuffer
            };
        }

        private void Transition(BenchmarkRunState next)
        {
            State = next;
            if (eventsBuffer != null)
            {
                eventsBuffer.Add("state=" + next);
            }
        }
    }
}
