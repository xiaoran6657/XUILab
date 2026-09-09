using System;
using System.Collections;
using System.IO;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.TestTools;
using XUILab.Benchmarking;

namespace XUILab.ListLab.Tests
{
    public class ListRefreshBenchmarkTests
    {
        [Test] public void RefreshCaseIdsAreStrict()
        {
            Assert.IsTrue(BenchmarkRunConfig.IsListRefreshCaseId("listrefresh-virtual-1000-target-high"));
            foreach(string value in new[]{null,"listrefresh-virtual-100-target-high","listrefresh-virtual-1000-target-high\n",
                "listrefresh-normal-1000-window-other","listrefresh-normal-1000-TARGET-high","list-virtual-1000-scroll"})
                Assert.IsFalse(BenchmarkRunConfig.IsListRefreshCaseId(value));
        }
        [UnityTest] public IEnumerator AllProfilesUseFollowingFrameSamplesAndExactCounters()
        {
            foreach(string backend in new[]{"normal","virtual"})
            foreach(string policy in new[]{"window","target"})
            foreach(string profile in new[]{"idle","sparse","burst","high","batch"})
            {
                var config=new BenchmarkRunConfig{runId="refresh-integration-"+Guid.NewGuid().ToString("N"),
                    caseId=$"listrefresh-{backend}-1000-{policy}-{profile}",warmupFrames=300,measureFrames=120,sampleCapacity=120,
                    outputDirectory=Path.GetFullPath(Path.Combine(Application.dataPath,"../../Artifacts/list-refresh-test-runs")),
                    candidateId="refresh-integration-test",buildId="editor",sourceRevision="workspace",targetFrameRate=-1,enableProfilerRecorders=false};
                var factory=new ListRefreshBenchmarkFactory();
                using(var runner=new BenchmarkRunner(factory,writer:new ListRefreshBenchmarkWriter(factory)))
                {
                    runner.Start(config);
                    for(int i=0;i<550&&!runner.IsTerminal;i++){yield return null;runner.Tick(Time.unscaledDeltaTime*1000,Time.frameCount);}
                    Assert.IsTrue(runner.IsTerminal);Assert.IsTrue(runner.Result.IsProcessSuccess,runner.Result.FailureReason);
                    int expectedBind=factory.Current.Metrics.bindAtStart;
                    for(int i=0;i<120;i++)
                    {
                        var frame=factory.Current.Frames[i];
                        int updates=profile=="idle"?0:(profile=="sparse"||profile=="burst")?(i%60==0?(profile=="burst"?3:1):0):profile=="batch"?9:1;
                        int binds=updates==0?0:policy=="target"?updates:profile=="batch"?9:9*updates;
                        expectedBind+=binds;
                        Assert.AreEqual(updates,frame.Updates);Assert.AreEqual(expectedBind,frame.Bind);
                        Assert.AreEqual(frame.ActionFrame+1,runner.Result.Samples[i].UnityFrame);
                        Assert.AreEqual(frame.ActionFrame+1,frame.SettledFrame);
                        Assert.AreEqual(9,frame.Visible);Assert.AreEqual(0,frame.Pending);
                    }
                    Assert.AreEqual(0,factory.Current.Metrics.cleanupUnique);
                    Assert.IsTrue(File.Exists(Path.Combine(runner.RunDirectory,"refresh-samples.csv")));
                    TestContext.WriteLine(config.caseId+": 120 aligned samples, exact action/Bind counters, cleanup0");
                }
                yield return null;
            }
        }
        [UnityTest] public IEnumerator FocusLossInvalidatesRefreshRunner()
        {
            var config=new BenchmarkRunConfig{runId="refresh-focus-"+Guid.NewGuid().ToString("N"),caseId="listrefresh-virtual-1000-target-high",
                warmupFrames=1,measureFrames=4,sampleCapacity=4,targetFrameRate=-1,enableProfilerRecorders=false,
                candidateId="refresh-focus-fixture",buildId="editor",sourceRevision="workspace",
                outputDirectory=Path.GetFullPath(Path.Combine(Application.dataPath,"../../Artifacts/list-refresh-test-runs"))};
            var factory=new ListRefreshBenchmarkFactory();
            using(var runner=new BenchmarkRunner(factory,writer:new ListRefreshBenchmarkWriter(factory)))
            {
                runner.Start(config);runner.MarkFocusLost();
                for(int i=0;i<40&&!runner.IsTerminal;i++){yield return null;runner.Tick(Time.unscaledDeltaTime*1000,Time.frameCount);}
                Assert.IsTrue(runner.IsTerminal);Assert.AreEqual(BenchmarkMeasurementValidity.Invalid,runner.Result.MeasurementValidity);
                Assert.IsFalse(runner.Result.IsProcessSuccess);Assert.AreEqual(0,factory.Current.Metrics.cleanupUnique);
            }
        }
    }
}
