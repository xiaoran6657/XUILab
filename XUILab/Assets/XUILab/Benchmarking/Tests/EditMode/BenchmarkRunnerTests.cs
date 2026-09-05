using System;
using NUnit.Framework;
using UnityEngine;

namespace XUILab.Benchmarking.Tests.EditMode
{
    public sealed class BenchmarkRunnerTests
    {
        [Test]
        public void SuccessPath_UsesFixedStatesAndCleansExactlyOnce()
        {
            var benchmarkCase = new FakeCase();
            var metrics = new FakeMetrics(true);
            var writer = new FakeWriter();
            var runner = new BenchmarkRunner(new FakeCaseFactory(benchmarkCase), metrics, writer);
            BenchmarkRunConfig config = Config("success", 1, 3);

            runner.Start(config);
            Assert.That(runner.State, Is.EqualTo(BenchmarkRunState.Warmup));
            runner.Tick(1, 1);
            Assert.That(runner.State, Is.EqualTo(BenchmarkRunState.Warmup));
            runner.Tick(1, 2);
            Assert.That(runner.State, Is.EqualTo(BenchmarkRunState.Measure));
            runner.Tick(10, 3);
            runner.Tick(11, 4);
            runner.Tick(12, 5);
            Assert.That(writer.InitialWrites, Is.EqualTo(0), "Measure must not write artifacts.");
            Assert.That(runner.State, Is.EqualTo(BenchmarkRunState.Validate));
            runner.Tick(1, 6);
            Assert.That(runner.State, Is.EqualTo(BenchmarkRunState.Export));
            runner.Tick(1, 7);

            Assert.That(runner.State, Is.EqualTo(BenchmarkRunState.Completed));
            Assert.That(runner.Result.Correctness, Is.EqualTo(BenchmarkCorrectnessStatus.Pass));
            Assert.That(runner.Result.MeasurementValidity, Is.EqualTo(BenchmarkMeasurementValidity.Valid));
            Assert.That(runner.Result.Statistics.SampleCount, Is.EqualTo(3));
            Assert.That(benchmarkCase.CleanupCount, Is.EqualTo(1));
            Assert.That(metrics.DisposeCount, Is.EqualTo(1));
            Assert.That(writer.InitialWrites, Is.EqualTo(1));
            Assert.That(writer.TerminalWrites, Is.EqualTo(1));

            runner.Dispose();
            runner.Dispose();
            Assert.That(benchmarkCase.CleanupCount, Is.EqualTo(1));
            Assert.That(metrics.DisposeCount, Is.EqualTo(1));
        }

        [Test]
        public void RequiredMetricUnavailable_CompletesButIsInvalid()
        {
            var runner = new BenchmarkRunner(
                new FakeCaseFactory(new FakeCase()),
                new FakeMetrics(false),
                new FakeWriter());
            BenchmarkRunConfig config = Config("missing-metric", 0, 1);

            DriveToTerminal(runner, config);

            Assert.That(runner.State, Is.EqualTo(BenchmarkRunState.Completed));
            Assert.That(runner.Result.Correctness, Is.EqualTo(BenchmarkCorrectnessStatus.Pass));
            Assert.That(runner.Result.MeasurementValidity, Is.EqualTo(BenchmarkMeasurementValidity.Invalid));
            Assert.That(runner.Result.FailureCode, Is.EqualTo(BenchmarkFailureCode.RequiredMetricUnavailable));
            Assert.That(runner.Result.ExitCode, Is.EqualTo(3));
        }

        [Test]
        public void CancellationBeforeMeasure_IsCancelledAndHasNoSamples()
        {
            var benchmarkCase = new FakeCase();
            var writer = new FakeWriter();
            var runner = new BenchmarkRunner(new FakeCaseFactory(benchmarkCase), new FakeMetrics(true), writer);
            BenchmarkRunConfig config = Config("cancel", 3, 3);

            runner.Start(config);
            runner.RequestCancel();
            runner.Tick(1, 1);

            Assert.That(runner.State, Is.EqualTo(BenchmarkRunState.Cancelled));
            Assert.That(runner.Result.EnteredMeasure, Is.False);
            Assert.That(runner.Result.MeasurementValidity, Is.EqualTo(BenchmarkMeasurementValidity.NotAssessed));
            Assert.That(benchmarkCase.CleanupCount, Is.EqualTo(1));
            Assert.That(writer.LastInitialResult.EnteredMeasure, Is.False);
        }

        [Test]
        public void PrepareFailure_IsFailedNotAssessedAndCleansOnce()
        {
            var benchmarkCase = new FakeCase();
            var writer = new FakeWriter();
            var runner = new BenchmarkRunner(new FakeCaseFactory(benchmarkCase), new FakeMetrics(true), writer);
            BenchmarkRunConfig config = Config("prepare-failure", 0, 2);
            config.faultPlan.mode = "prepare_failure";

            runner.Start(config);

            Assert.That(runner.State, Is.EqualTo(BenchmarkRunState.Failed));
            Assert.That(runner.Result.FailureCode, Is.EqualTo(BenchmarkFailureCode.PrepareFailed));
            Assert.That(runner.Result.MeasurementValidity, Is.EqualTo(BenchmarkMeasurementValidity.NotAssessed));
            Assert.That(runner.Result.EnteredMeasure, Is.False);
            Assert.That(runner.Result.ExitCode, Is.EqualTo(1));
            Assert.That(benchmarkCase.CleanupCount, Is.EqualTo(1));
            Assert.That(writer.InitialWrites, Is.EqualTo(1));
            Assert.That(writer.TerminalWrites, Is.EqualTo(1));
        }

        [Test]
        public void ReadyTimeout_IsFailedBeforeMeasure()
        {
            var runner = new BenchmarkRunner(
                new FakeCaseFactory(new FakeCase()),
                new FakeMetrics(true),
                new FakeWriter());
            BenchmarkRunConfig config = Config("ready-timeout", 0, 2);
            config.readyTimeoutFrames = 2;
            config.faultPlan.mode = "ready_timeout";

            DriveToTerminal(runner, config);

            Assert.That(runner.State, Is.EqualTo(BenchmarkRunState.Failed));
            Assert.That(runner.Result.FailureCode, Is.EqualTo(BenchmarkFailureCode.ReadyTimeout));
            Assert.That(runner.Result.EnteredMeasure, Is.False);
            Assert.That(runner.Result.MeasurementValidity, Is.EqualTo(BenchmarkMeasurementValidity.NotAssessed));
        }

        [Test]
        public void RequiredMetricFault_CompletesInvalidAndUsesNonzeroExit()
        {
            var metrics = new FakeMetrics(true);
            var runner = new BenchmarkRunner(new FakeCaseFactory(new FakeCase()), metrics, new FakeWriter());
            BenchmarkRunConfig config = Config("required-fault", 0, 2);
            config.faultPlan.mode = "required_metric_unavailable";

            DriveToTerminal(runner, config);

            Assert.That(runner.State, Is.EqualTo(BenchmarkRunState.Completed));
            Assert.That(runner.Result.MeasurementValidity, Is.EqualTo(BenchmarkMeasurementValidity.Invalid));
            Assert.That(runner.Result.FailureCode, Is.EqualTo(BenchmarkFailureCode.RequiredMetricUnavailable));
            Assert.That(runner.Result.ExitCode, Is.EqualTo(3));
            Assert.That(metrics.Capabilities[0].status, Is.EqualTo("unavailable"));
        }

        [Test]
        public void SampleShortage_ExportsMeasuredPrefixAsInvalid()
        {
            var writer = new FakeWriter();
            var runner = new BenchmarkRunner(
                new FakeCaseFactory(new FakeCase()),
                new FakeMetrics(true),
                writer);
            BenchmarkRunConfig config = Config("sample-shortage", 0, 4);
            config.faultPlan.mode = "sample_shortage";
            config.faultPlan.shortageSampleCount = 2;

            DriveToTerminal(runner, config);

            Assert.That(runner.State, Is.EqualTo(BenchmarkRunState.Completed));
            Assert.That(runner.Result.FailureCode, Is.EqualTo(BenchmarkFailureCode.SampleShortage));
            Assert.That(runner.Result.MeasurementValidity, Is.EqualTo(BenchmarkMeasurementValidity.Invalid));
            Assert.That(runner.Result.Statistics.SampleCount, Is.EqualTo(2));
            Assert.That(writer.LastInitialResult.EnteredMeasure, Is.True);
        }

        [Test]
        public void ConfiguredCancellation_PreservesMeasuredPrefixAndCancels()
        {
            var runner = new BenchmarkRunner(
                new FakeCaseFactory(new FakeCase()),
                new FakeMetrics(true),
                new FakeWriter());
            BenchmarkRunConfig config = Config("configured-cancel", 0, 4);
            config.faultPlan.mode = "cancel";
            config.faultPlan.triggerMeasureFrame = 1;

            DriveToTerminal(runner, config);

            Assert.That(runner.State, Is.EqualTo(BenchmarkRunState.Cancelled));
            Assert.That(runner.Result.MeasurementValidity, Is.EqualTo(BenchmarkMeasurementValidity.Invalid));
            Assert.That(runner.Result.Statistics.SampleCount, Is.EqualTo(1));
            Assert.That(runner.Result.ExitCode, Is.EqualTo(2));
        }

        [Test]
        public void CaseException_FailsAndPreservesMeasuredPrefix()
        {
            var runner = new BenchmarkRunner(
                new FakeCaseFactory(new FakeCase()),
                new FakeMetrics(true),
                new FakeWriter());
            BenchmarkRunConfig config = Config("case-exception", 0, 4);
            config.faultPlan.mode = "case_exception";
            config.faultPlan.triggerMeasureFrame = 1;

            DriveToTerminal(runner, config);

            Assert.That(runner.State, Is.EqualTo(BenchmarkRunState.Failed));
            Assert.That(runner.Result.FailureCode, Is.EqualTo(BenchmarkFailureCode.CaseException));
            Assert.That(runner.Result.MeasurementValidity, Is.EqualTo(BenchmarkMeasurementValidity.Invalid));
            Assert.That(runner.Result.Statistics.SampleCount, Is.EqualTo(1));
        }

        [Test]
        public void ExportFailure_IsFailedAndDoesNotCallWriter()
        {
            var writer = new FakeWriter();
            var runner = new BenchmarkRunner(
                new FakeCaseFactory(new FakeCase()),
                new FakeMetrics(true),
                writer);
            BenchmarkRunConfig config = Config("export-failure", 0, 2);
            config.faultPlan.mode = "export_failure";

            DriveToTerminal(runner, config);

            Assert.That(runner.State, Is.EqualTo(BenchmarkRunState.Failed));
            Assert.That(runner.Result.FailureCode, Is.EqualTo(BenchmarkFailureCode.ExportFailed));
            Assert.That(runner.Result.ExitCode, Is.EqualTo(1));
            Assert.That(writer.InitialWrites, Is.EqualTo(0));
            Assert.That(writer.TerminalWrites, Is.EqualTo(0));
        }

        [Test]
        public void TerminalExportFailure_CannotRemainProcessSuccess()
        {
            var writer = new FakeWriter { ThrowOnTerminal = true };
            var runner = new BenchmarkRunner(
                new FakeCaseFactory(new FakeCase()),
                new FakeMetrics(true),
                writer);
            BenchmarkRunConfig config = Config("terminal-export-failure", 0, 2);

            DriveToTerminal(runner, config);

            Assert.That(runner.State, Is.EqualTo(BenchmarkRunState.Failed));
            Assert.That(runner.Result.FailureCode, Is.EqualTo(BenchmarkFailureCode.ExportFailed));
            Assert.That(runner.Result.ExportSucceeded, Is.False);
            Assert.That(runner.Result.IsProcessSuccess, Is.False);
            Assert.That(runner.Result.ExitCode, Is.EqualTo(1));
            Assert.That(writer.InitialWrites, Is.EqualTo(1));
            Assert.That(writer.TerminalWrites, Is.EqualTo(1));
        }

        [Test]
        public void CleanupFailure_StillDisposesMetricsAndExportsFailureResult()
        {
            var benchmarkCase = new FakeCase();
            var metrics = new FakeMetrics(true);
            var writer = new FakeWriter();
            var runner = new BenchmarkRunner(new FakeCaseFactory(benchmarkCase), metrics, writer);
            BenchmarkRunConfig config = Config("cleanup-failure", 0, 2);
            config.faultPlan.mode = "cleanup_failure";

            DriveToTerminal(runner, config);

            Assert.That(runner.State, Is.EqualTo(BenchmarkRunState.Failed));
            Assert.That(runner.Result.CleanupSucceeded, Is.False);
            Assert.That(benchmarkCase.CleanupCount, Is.EqualTo(1));
            Assert.That(metrics.DisposeCount, Is.EqualTo(1));
            Assert.That(writer.InitialWrites, Is.EqualTo(1));
            Assert.That(writer.TerminalWrites, Is.EqualTo(1));
        }

        [TestCase("focus_loss")]
        [TestCase("pause")]
        public void FocusOrPauseFault_CompletesButIsInvalid(string faultMode)
        {
            var runner = new BenchmarkRunner(
                new FakeCaseFactory(new FakeCase()),
                new FakeMetrics(true),
                new FakeWriter());
            BenchmarkRunConfig config = Config("external-invalid-" + faultMode.Replace('_', '-'), 0, 2);
            config.faultPlan.mode = faultMode;

            DriveToTerminal(runner, config);

            Assert.That(runner.State, Is.EqualTo(BenchmarkRunState.Completed));
            Assert.That(runner.Result.MeasurementValidity, Is.EqualTo(BenchmarkMeasurementValidity.Invalid));
            Assert.That(runner.Result.ExitCode, Is.EqualTo(3));
        }

        [Test]
        public void UnsafeRunId_FailsBeforeCaseCreation()
        {
            var runner = new BenchmarkRunner(
                new FakeCaseFactory(new FakeCase()),
                new FakeMetrics(true),
                new FakeWriter());
            BenchmarkRunConfig config = Config("../escape", 0, 1);

            runner.Start(config);

            Assert.That(runner.State, Is.EqualTo(BenchmarkRunState.Failed));
            Assert.That(runner.Result.FailureCode, Is.EqualTo(BenchmarkFailureCode.ConfigurationInvalid));
        }

        [Test]
        public void UnsupportedProtocol_FailsConfiguration()
        {
            var runner = new BenchmarkRunner(
                new FakeCaseFactory(new FakeCase()),
                new FakeMetrics(true),
                new FakeWriter());
            BenchmarkRunConfig config = Config("unsupported-protocol", 0, 1);
            config.protocolVersion = "xuilab.benchmark.protocol/future";

            runner.Start(config);

            Assert.That(runner.State, Is.EqualTo(BenchmarkRunState.Failed));
            Assert.That(runner.Result.FailureCode, Is.EqualTo(BenchmarkFailureCode.ConfigurationInvalid));
        }

        [TestCaseSource(nameof(InvalidRequiredMetrics))]
        public void ProtocolV1_RejectsMissingOrChangedRequiredMetrics(string[] requiredMetrics)
        {
            var runner = new BenchmarkRunner(
                new FakeCaseFactory(new FakeCase()),
                new FakeMetrics(true),
                new FakeWriter());
            BenchmarkRunConfig config = Config("invalid-required-metrics", 0, 1);
            config.requiredMetrics = requiredMetrics;

            runner.Start(config);

            Assert.That(runner.State, Is.EqualTo(BenchmarkRunState.Failed));
            Assert.That(runner.Result.FailureCode, Is.EqualTo(BenchmarkFailureCode.ConfigurationInvalid));
            Assert.That(runner.Result.FailureReason, Does.Contain("Frame Interval"));
        }

        [Test]
        public void PlaceholderIdentity_FailsConfiguration()
        {
            var runner = new BenchmarkRunner(
                new FakeCaseFactory(new FakeCase()),
                new FakeMetrics(true),
                new FakeWriter());
            BenchmarkRunConfig config = Config("placeholder-identity", 0, 1);
            config.candidateId = "unknown";

            runner.Start(config);

            Assert.That(runner.State, Is.EqualTo(BenchmarkRunState.Failed));
            Assert.That(runner.Result.FailureCode, Is.EqualTo(BenchmarkFailureCode.ConfigurationInvalid));
        }

        [TestCase("cancel")]
        [TestCase("case_exception")]
        [TestCase("focus_loss")]
        [TestCase("pause")]
        public void MeasureTriggeredFaultAtOrBeyondMeasureFrames_FailsConfiguration(string faultMode)
        {
            var runner = new BenchmarkRunner(
                new FakeCaseFactory(new FakeCase()),
                new FakeMetrics(true),
                new FakeWriter());
            BenchmarkRunConfig config = Config("late-" + faultMode.Replace('_', '-'), 0, 2);
            config.faultPlan.mode = faultMode;
            config.faultPlan.triggerMeasureFrame = config.measureFrames;

            runner.Start(config);

            Assert.That(runner.State, Is.EqualTo(BenchmarkRunState.Failed));
            Assert.That(runner.Result.FailureCode, Is.EqualTo(BenchmarkFailureCode.ConfigurationInvalid));
            Assert.That(runner.Result.FailureReason, Does.Contain("triggerMeasureFrame"));
        }

        [Test]
        public void ReleaseFaultPlan_IsRejectedWithoutChangingPreexistingSettings()
        {
            int savedTargetFrameRate = Application.targetFrameRate;
            int savedVSyncCount = QualitySettings.vSyncCount;
            try
            {
                Application.targetFrameRate = 37;
                QualitySettings.vSyncCount = 2;
                var writer = new FakeWriter();
                var runner = new BenchmarkRunner(
                    new FakeCaseFactory(new FakeCase()),
                    new FakeMetrics(true),
                    writer,
                    null,
                    () => false);
                BenchmarkRunConfig config = Config("release-fault-rejected", 0, 2);
                config.targetFrameRate = 120;
                config.vSyncCount = 0;
                config.faultPlan.mode = "prepare_failure";

                runner.Start(config);

                Assert.That(runner.State, Is.EqualTo(BenchmarkRunState.Failed));
                Assert.That(runner.Result.FailureCode, Is.EqualTo(BenchmarkFailureCode.ConfigurationInvalid));
                Assert.That(Application.targetFrameRate, Is.EqualTo(37));
                Assert.That(QualitySettings.vSyncCount, Is.EqualTo(2));
                Assert.That(writer.LastTerminalResult.Environment.targetFrameRate, Is.EqualTo(37));
                Assert.That(writer.LastTerminalResult.Environment.vSyncCount, Is.EqualTo(2));
            }
            finally
            {
                Application.targetFrameRate = savedTargetFrameRate;
                QualitySettings.vSyncCount = savedVSyncCount;
            }
        }

        private static BenchmarkRunConfig Config(string runId, int warmupFrames, int measureFrames)
        {
            return new BenchmarkRunConfig
            {
                runId = runId,
                caseId = "idle",
                warmupFrames = warmupFrames,
                measureFrames = measureFrames,
                sampleCapacity = measureFrames,
                outputDirectory = ".",
                targetFrameRate = -1,
                requiredMetrics = new[] { "Frame Interval" },
                candidateId = "m0-04-test",
                buildId = "editmode-test",
                sourceRevision = "workspace-test"
            };
        }

        private static readonly object[] InvalidRequiredMetrics =
        {
            null,
            new string[0],
            new[] { "Main Thread" },
            new[] { "Frame Interval", "Main Thread" }
        };

        private static void DriveToTerminal(BenchmarkRunner runner, BenchmarkRunConfig config)
        {
            runner.Start(config);
            for (int i = 0; i < 32 && !runner.IsTerminal; i++)
            {
                runner.Tick(10, i);
            }

            Assert.That(runner.IsTerminal, Is.True);
        }

        private sealed class FakeCaseFactory : IBenchmarkCaseFactory
        {
            private readonly IBenchmarkCase benchmarkCase;
            public FakeCaseFactory(IBenchmarkCase benchmarkCase) { this.benchmarkCase = benchmarkCase; }
            public IBenchmarkCase Create(BenchmarkRunConfig config) { return benchmarkCase; }
        }

        private sealed class FakeCase : IBenchmarkCase
        {
            public string Id { get { return "fake"; } }
            public bool IsReady { get; private set; }
            public int CleanupCount { get; private set; }
            private int measuredFrames;
            public void Prepare(BenchmarkRunConfig config) { IsReady = true; }
            public void TickWarmup(int frameIndex) { }
            public void BeginMeasure() { }
            public void TickMeasure(int frameIndex) { measuredFrames++; }
            public void EndMeasure() { }
            public BenchmarkCaseValidation Validate() { return measuredFrames > 0 ? BenchmarkCaseValidation.Pass() : BenchmarkCaseValidation.Fail("no frames"); }
            public void Cleanup() { CleanupCount++; }
        }

        private sealed class FakeMetrics : IBenchmarkMetricProbeSet
        {
            private readonly bool requiredAvailable;
            public FakeMetrics(bool requiredAvailable) { this.requiredAvailable = requiredAvailable; }
            public BenchmarkMetricCapability[] Capabilities { get; private set; }
            public bool RequiredMetricsAvailable { get { return requiredAvailable; } }
            public string RequiredMetricsFailureReason { get { return requiredAvailable ? string.Empty : "Required metric unavailable: fake"; } }
            public int DisposeCount { get; private set; }
            public void Prepare(BenchmarkRunConfig config)
            {
                Capabilities = new[] { new BenchmarkMetricCapability { name = "Frame Interval", required = true, status = requiredAvailable ? "available" : "unavailable" } };
            }
            public void BeginMeasure() { }
            public void Capture(ref BenchmarkFrameSample sample) { }
            public void Stop() { }
            public void Dispose() { DisposeCount++; }
        }

        private sealed class FakeWriter : IBenchmarkArtifactWriter
        {
            private string runDirectory = string.Empty;
            public string RunDirectory { get { return runDirectory; } }
            public int InitialWrites { get; private set; }
            public int TerminalWrites { get; private set; }
            public bool ThrowOnTerminal { get; set; }
            public BenchmarkRunResult LastInitialResult { get; private set; }
            public BenchmarkRunResult LastTerminalResult { get; private set; }
            public void WriteInitial(BenchmarkRunResult result) { InitialWrites++; LastInitialResult = result; runDirectory = "fake"; }
            public void WriteTerminal(BenchmarkRunResult result)
            {
                TerminalWrites++;
                if (ThrowOnTerminal)
                {
                    throw new InvalidOperationException("Injected terminal writer failure.");
                }

                LastTerminalResult = result;
            }
        }
    }
}
