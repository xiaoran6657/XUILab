using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.SceneManagement;
using UnityEngine.TestTools;
using UnityEngine.UI;
using Object = UnityEngine.Object;

namespace XUILab.Benchmarking.Tests.PlayMode
{
    public sealed class BenchmarkSmokeSceneTests
    {
        [UnityTest]
        public IEnumerator SmokeScene_HasMinimalTopologyAndLiveRunnerHost()
        {
            AsyncOperation load = SceneManager.LoadSceneAsync(
                BenchmarkSmokeSceneContract.ScenePath,
                LoadSceneMode.Single);

            Assert.That(load, Is.Not.Null);
            yield return load;
            yield return null;

            Assert.That(SceneManager.GetActiveScene().path, Is.EqualTo(BenchmarkSmokeSceneContract.ScenePath));

            BenchmarkRunnerHost[] hosts = Object.FindObjectsOfType<BenchmarkRunnerHost>(true);
            Canvas[] canvases = Object.FindObjectsOfType<Canvas>(true);
            CanvasScaler[] scalers = Object.FindObjectsOfType<CanvasScaler>(true);
            GraphicRaycaster[] raycasters = Object.FindObjectsOfType<GraphicRaycaster>(true);
            Image[] images = Object.FindObjectsOfType<Image>(true);
            Camera[] cameras = Object.FindObjectsOfType<Camera>(true);
            EventSystem[] eventSystems = Object.FindObjectsOfType<EventSystem>(true);

            Assert.That(hosts, Has.Length.EqualTo(1));
            Assert.That(hosts[0].name, Is.EqualTo(BenchmarkSmokeSceneContract.RunnerObjectName));
            Assert.That(hosts[0].IsReady, Is.True);
            Assert.That(hosts[0].ObservedFrameCount, Is.GreaterThan(0));
            Assert.That(canvases, Has.Length.EqualTo(1));
            Assert.That(canvases[0].name, Is.EqualTo(BenchmarkSmokeSceneContract.CanvasObjectName));
            Assert.That(scalers, Has.Length.EqualTo(1));
            Assert.That(raycasters, Has.Length.EqualTo(1));
            Assert.That(images, Has.Length.EqualTo(1));
            Assert.That(images[0].name, Is.EqualTo(BenchmarkSmokeSceneContract.ImageObjectName));
            Assert.That(cameras, Has.Length.EqualTo(1));
            Assert.That(eventSystems, Is.Empty, "The non-interactive smoke scene must not create an EventSystem.");
        }

        [UnityTest]
        public IEnumerator RunnerHost_CompletesEditorRunAndWritesSevenArtifacts()
        {
            AsyncOperation load = SceneManager.LoadSceneAsync(
                BenchmarkSmokeSceneContract.ScenePath,
                LoadSceneMode.Single);
            Assert.That(load, Is.Not.Null);
            yield return load;
            yield return null;

            BenchmarkRunnerHost host = Object.FindObjectOfType<BenchmarkRunnerHost>(true);
            Assert.That(host, Is.Not.Null);

            string outputRoot = Path.Combine(
                Application.temporaryCachePath,
                "XUILab-M0-03-" + Guid.NewGuid().ToString("N"));
            var config = new BenchmarkRunConfig
            {
                runId = "editor-normal",
                tier = "editor-playmode-test",
                caseId = "idle",
                warmupFrames = 2,
                measureFrames = 5,
                sampleCapacity = 5,
                outputDirectory = outputRoot,
                targetFrameRate = -1,
                vSyncCount = 0,
                candidateId = "m0-03-test",
                buildId = "editor-test",
                sourceRevision = "workspace",
                dirty = true
            };

            try
            {
                host.StartRun(config);
                for (int i = 0; i < 240 && (host.LastResult == null || host.IsRunActive); i++)
                {
                    yield return null;
                }

                Assert.That(host.LastResult, Is.Not.Null);
                Assert.That(host.LastResult.State, Is.EqualTo(BenchmarkRunState.Completed));
                Assert.That(host.LastResult.Correctness, Is.EqualTo(BenchmarkCorrectnessStatus.Pass));
                Assert.That(host.LastResult.MeasurementValidity, Is.EqualTo(BenchmarkMeasurementValidity.Valid));
                Assert.That(host.LastResult.Statistics.SampleCount, Is.EqualTo(5));

                string runDirectory = Path.Combine(outputRoot, config.runId);
                Assert.That(Directory.Exists(runDirectory), Is.True);
                Assert.That(Directory.GetFiles(runDirectory), Has.Length.EqualTo(7));
                Assert.That(File.ReadAllLines(Path.Combine(runDirectory, "samples.csv")), Has.Length.EqualTo(6));
            }
            finally
            {
                if (Directory.Exists(outputRoot))
                {
                    Directory.Delete(outputRoot, true);
                }
            }
        }

        [UnityTest]
        public IEnumerator RunnerSamplesTheFrameAfterEachAlternatingMeasureAction()
        {
            const int measureFrames = 12;
            var benchmarkCase = new AlternatingWorkCase(35.0);
            var runner = new BenchmarkRunner(
                new SingleCaseFactory(benchmarkCase),
                new FrameIntervalOnlyMetrics(),
                new MemoryWriter());
            var config = new BenchmarkRunConfig
            {
                runId = "playmode-action-sample-alignment",
                tier = "editor-playmode-test",
                caseId = "idle",
                warmupFrames = 0,
                measureFrames = measureFrames,
                sampleCapacity = measureFrames,
                outputDirectory = Application.temporaryCachePath,
                targetFrameRate = -1,
                vSyncCount = 0,
                candidateId = "m0-04-r4-test",
                buildId = "editor-test",
                sourceRevision = "workspace",
                dirty = true
            };

            runner.Start(config);
            for (int i = 0; i < 240 && !runner.IsTerminal; i++)
            {
                runner.Tick(Time.unscaledDeltaTime * 1000.0, Time.frameCount);
                yield return null;
            }

            Assert.That(runner.IsTerminal, Is.True);
            Assert.That(runner.Result.State, Is.EqualTo(BenchmarkRunState.Completed));
            Assert.That(benchmarkCase.ActionIndices, Is.EqualTo(Enumerable.Range(0, measureFrames)));

            var heavy = new List<double>();
            var light = new List<double>();
            for (int i = 0; i < runner.Result.Samples.Count; i++)
            {
                BenchmarkFrameSample sample = runner.Result.Samples[i];
                Assert.That(sample.SampleIndex, Is.EqualTo(i));
                Assert.That(sample.UnityFrame, Is.EqualTo(benchmarkCase.ActionUnityFrames[i] + 1),
                    "Each sample must be captured on the frame immediately after its same-index action.");
                (i % 2 == 0 ? heavy : light).Add(sample.FrameIntervalMs);
            }

            Assert.That(Median(heavy), Is.GreaterThan(Median(light) + 8.0),
                "Even samples must contain the 35 ms work scheduled by the same even action index.");
        }

        private static double Median(List<double> values)
        {
            values.Sort();
            int middle = values.Count / 2;
            return values.Count % 2 == 0
                ? (values[middle - 1] + values[middle]) * 0.5
                : values[middle];
        }

        private sealed class SingleCaseFactory : IBenchmarkCaseFactory
        {
            private readonly IBenchmarkCase benchmarkCase;
            public SingleCaseFactory(IBenchmarkCase benchmarkCase) { this.benchmarkCase = benchmarkCase; }
            public IBenchmarkCase Create(BenchmarkRunConfig config) { return benchmarkCase; }
        }

        private sealed class AlternatingWorkCase : IBenchmarkCase
        {
            private readonly double heavyMilliseconds;
            public AlternatingWorkCase(double heavyMilliseconds) { this.heavyMilliseconds = heavyMilliseconds; }
            public string Id { get { return "alternating-work"; } }
            public bool IsReady { get; private set; }
            public List<int> ActionIndices { get; } = new List<int>();
            public List<int> ActionUnityFrames { get; } = new List<int>();
            public void Prepare(BenchmarkRunConfig config) { IsReady = true; }
            public void TickWarmup(int frameIndex) { }
            public void BeginMeasure() { }
            public void TickMeasure(int frameIndex)
            {
                ActionIndices.Add(frameIndex);
                ActionUnityFrames.Add(Time.frameCount);
                if (frameIndex % 2 != 0)
                {
                    return;
                }

                long started = System.Diagnostics.Stopwatch.GetTimestamp();
                double frequency = System.Diagnostics.Stopwatch.Frequency;
                while (((System.Diagnostics.Stopwatch.GetTimestamp() - started) * 1000.0 / frequency) < heavyMilliseconds)
                {
                }
            }
            public void EndMeasure() { }
            public BenchmarkCaseValidation Validate()
            {
                return ActionIndices.Count > 0
                    ? BenchmarkCaseValidation.Pass()
                    : BenchmarkCaseValidation.Fail("No measure actions ran.");
            }
            public void Cleanup() { }
        }

        private sealed class FrameIntervalOnlyMetrics : IBenchmarkMetricProbeSet
        {
            public BenchmarkMetricCapability[] Capabilities { get; private set; }
            public bool RequiredMetricsAvailable { get { return true; } }
            public string RequiredMetricsFailureReason { get { return string.Empty; } }
            public void Prepare(BenchmarkRunConfig config)
            {
                Capabilities = new[]
                {
                    new BenchmarkMetricCapability
                    {
                        name = "Frame Interval",
                        category = "Time",
                        unit = "ms",
                        required = true,
                        status = "available",
                        reason = string.Empty
                    }
                };
            }
            public void BeginMeasure() { }
            public void Capture(ref BenchmarkFrameSample sample) { }
            public void Stop() { }
            public void Dispose() { }
        }

        private sealed class MemoryWriter : IBenchmarkArtifactWriter
        {
            public string RunDirectory { get { return "memory"; } }
            public void WriteInitial(BenchmarkRunResult result) { }
            public void WriteTerminal(BenchmarkRunResult result) { }
        }
    }
}
