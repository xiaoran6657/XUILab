using System;
using System.IO;
using System.Security.Cryptography;
using NUnit.Framework;

namespace XUILab.Benchmarking.Tests.EditMode
{
    public sealed class BenchmarkStatisticsAndArtifactsTests
    {
        [Test]
        public void PercentilesAndBudgetRatio_UseLinearInterpolation()
        {
            var buffer = new BenchmarkSampleBuffer(4);
            buffer.TryAdd(Sample(1));
            buffer.TryAdd(Sample(2));
            buffer.TryAdd(Sample(3));
            buffer.TryAdd(Sample(4));

            BenchmarkSummaryStatistics stats = BenchmarkStatistics.Calculate(buffer, 2);

            Assert.That(stats.P50FrameIntervalMs, Is.EqualTo(2.5).Within(0.000001));
            Assert.That(stats.P95FrameIntervalMs, Is.EqualTo(3.85).Within(0.000001));
            Assert.That(stats.P99FrameIntervalMs, Is.EqualTo(3.97).Within(0.000001));
            Assert.That(stats.MaxFrameIntervalMs, Is.EqualTo(4));
            Assert.That(stats.OverBudgetRatio, Is.EqualTo(0.5));
        }

        [Test]
        public void ArtifactWriter_WritesSevenFilesAndNullForUnavailableMetrics()
        {
            string root = Path.Combine(Path.GetTempPath(), "XUILab-M0-03-" + Guid.NewGuid().ToString("N"));
            try
            {
                var config = new BenchmarkRunConfig
                {
                    runId = "artifact-contract",
                    outputDirectory = root,
                    measureFrames = 1,
                    sampleCapacity = 1,
                    warmupFrames = 0,
                    candidateId = "m0-04-test",
                    buildId = "editmode-test",
                    sourceRevision = "workspace-test"
                };
                var buffer = new BenchmarkSampleBuffer(1);
                buffer.TryAdd(Sample(10));
                var result = new BenchmarkRunResult
                {
                    Config = config,
                    Environment = new BenchmarkEnvironmentRecord { tier = "test", metricCapabilities = new BenchmarkMetricCapability[0] },
                    Identity = BenchmarkRecordFactory.CreateIdentity(config),
                    State = BenchmarkRunState.Completed,
                    Correctness = BenchmarkCorrectnessStatus.Pass,
                    MeasurementValidity = BenchmarkMeasurementValidity.Valid,
                    PerformanceComparison = BenchmarkComparisonStatus.NotAssessed,
                    EnteredMeasure = true,
                    ExportSucceeded = true,
                    CleanupSucceeded = true,
                    Samples = buffer,
                    Statistics = BenchmarkStatistics.Calculate(buffer, 16.6666667),
                    Events = new BenchmarkEventBuffer(4)
                };
                result.Events.Add("state=Completed");

                // The writer owns the final config artifact and must hash the exact bytes it writes,
                // even if a mutable Case changed the config after identity creation.
                config.caseVersion = "mutated-after-identity";

                var writer = new FileBenchmarkArtifactWriter();
                writer.WriteInitial(result);
                writer.WriteTerminal(result);

                string[] files = Directory.GetFiles(writer.RunDirectory);
                Assert.That(files, Has.Length.EqualTo(7));
                Assert.That(File.ReadAllLines(Path.Combine(writer.RunDirectory, "samples.csv")), Has.Length.EqualTo(2));
                string summary = File.ReadAllText(Path.Combine(writer.RunDirectory, "summary.json"));
                Assert.That(summary, Does.Contain("\"sampleCount\": 1"));
                Assert.That(summary, Does.Contain("\"meanMainThreadNanoseconds\": null"));
                Assert.That(summary, Does.Contain("\"performanceComparison\": \"not_assessed\""));
                string configPath = Path.Combine(writer.RunDirectory, "config.json");
                Assert.That(File.ReadAllText(configPath), Does.Contain("\"caseVersion\": \"mutated-after-identity\""));
                Assert.That(result.Identity.configSha256, Is.EqualTo(ComputeFileSha256(configPath)));
            }
            finally
            {
                if (Directory.Exists(root))
                {
                    Directory.Delete(root, true);
                }
            }
        }

        [Test]
        public void PrepareFailureArtifacts_WriteSixFilesWithoutSamples()
        {
            string root = Path.Combine(Path.GetTempPath(), "XUILab-M0-04-" + Guid.NewGuid().ToString("N"));
            try
            {
                var config = new BenchmarkRunConfig
                {
                    runId = "prepare-failure-artifacts",
                    caseId = "idle",
                    warmupFrames = 0,
                    measureFrames = 2,
                    sampleCapacity = 2,
                    outputDirectory = root,
                    targetFrameRate = -1,
                    candidateId = "m0-04-test",
                    buildId = "editmode-test",
                    sourceRevision = "workspace-test",
                    faultPlan = new BenchmarkFaultPlan { mode = "prepare_failure" }
                };
                var runner = new BenchmarkRunner(
                    new InlineCaseFactory(),
                    new InlineMetrics(),
                    new FileBenchmarkArtifactWriter());

                runner.Start(config);

                string runDirectory = Path.Combine(root, config.runId);
                Assert.That(runner.State, Is.EqualTo(BenchmarkRunState.Failed));
                Assert.That(Directory.GetFiles(runDirectory), Has.Length.EqualTo(6));
                Assert.That(File.Exists(Path.Combine(runDirectory, "samples.csv")), Is.False);
                string summary = File.ReadAllText(Path.Combine(runDirectory, "summary.json"));
                Assert.That(summary, Does.Contain("\"measurementValidity\": \"not_assessed\""));
                Assert.That(summary, Does.Contain("\"processSuccess\": false"));
                Assert.That(summary, Does.Contain("\"exitCode\": 1"));
            }
            finally
            {
                if (Directory.Exists(root))
                {
                    Directory.Delete(root, true);
                }
            }
        }

        [Test]
        public void SampleBuffer_DoesNotGrowPastCapacity()
        {
            var buffer = new BenchmarkSampleBuffer(1);
            Assert.That(buffer.TryAdd(Sample(1)), Is.True);
            Assert.That(buffer.TryAdd(Sample(2)), Is.False);
            Assert.That(buffer.Count, Is.EqualTo(1));
            Assert.That(buffer.Capacity, Is.EqualTo(1));
        }

        private static BenchmarkFrameSample Sample(double interval)
        {
            return new BenchmarkFrameSample { FrameIntervalMs = interval };
        }

        private static string ComputeFileSha256(string path)
        {
            using (SHA256 sha = SHA256.Create())
            using (FileStream stream = File.OpenRead(path))
            {
                return BitConverter.ToString(sha.ComputeHash(stream)).Replace("-", string.Empty);
            }
        }

        private sealed class InlineCaseFactory : IBenchmarkCaseFactory
        {
            public IBenchmarkCase Create(BenchmarkRunConfig config) { return new IdleBenchmarkCase(); }
        }

        private sealed class InlineMetrics : IBenchmarkMetricProbeSet
        {
            public BenchmarkMetricCapability[] Capabilities { get; private set; }
            public bool RequiredMetricsAvailable { get { return true; } }
            public string RequiredMetricsFailureReason { get { return string.Empty; } }
            public void Prepare(BenchmarkRunConfig config)
            {
                Capabilities = new[]
                {
                    new BenchmarkMetricCapability { name = "Frame Interval", required = true, status = "available" }
                };
            }
            public void BeginMeasure() { }
            public void Capture(ref BenchmarkFrameSample sample) { }
            public void Stop() { }
            public void Dispose() { }
        }
    }
}
