using System;
using System.Collections;
using System.IO;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.TestTools;
using XUILab.Benchmarking;

namespace XUILab.ListLab.Tests
{
    public class ListBenchmarkTests
    {
        [UnityTest] public IEnumerator RealRunnerAlignsListActionsWithFollowingFrameAndExportsCleanup()
        {
            string output=Path.GetFullPath(Path.Combine(Application.dataPath,"../..","Artifacts/list-test-runs"));
            var config=new BenchmarkRunConfig{runId="list-alignment-"+Guid.NewGuid().ToString("N"),caseId="list-virtual-100-scroll",warmupFrames=300,measureFrames=24,sampleCapacity=24,
                outputDirectory=output,candidateId="list-integration-test",buildId="editor",sourceRevision="workspace",targetFrameRate=-1,enableProfilerRecorders=false};
            var factory=new ListBenchmarkFactory();
            using(var runner=new BenchmarkRunner(factory,writer:new ListBenchmarkWriter(factory)))
            {
                runner.Start(config);
                for(int i=0;i<500&&!runner.IsTerminal;i++){yield return null;runner.Tick(Time.unscaledDeltaTime*1000,Time.frameCount);}
                Assert.True(runner.IsTerminal);Assert.True(runner.Result.IsProcessSuccess,runner.Result.FailureReason);
                for(int i=0;i<config.measureFrames;i++)Assert.AreEqual(factory.Current.Frames[i].UnityFrame+1,runner.Result.Samples[i].UnityFrame);
                Assert.AreEqual(0,factory.Current.Metrics.cleanupUniqueTotal);
                Assert.True(File.Exists(Path.Combine(runner.RunDirectory,"list-metrics.json")));
                Assert.True(File.Exists(Path.Combine(runner.RunDirectory,"list-samples.csv")));
            }
            yield return null;
        }
        [UnityTest] public IEnumerator FullLifecycleBothBackendsSatisfiesIdentityAndPositionContract()
        {
            foreach(string backend in new[]{"normal","virtual"})
            {
                var config=new BenchmarkRunConfig{caseId="list-"+backend+"-100-lifecycle",measureFrames=1800};
                var subject=new ListBenchmarkCase();
                try
                {
                    subject.Prepare(config);yield return null;Assert.True(subject.IsReady);
                    for(int i=0;i<300;i++)subject.TickWarmup(i);
                    subject.BeginMeasure();
                    for(int i=0;i<1800;i++){subject.TickMeasure(i);Canvas.ForceUpdateCanvases();}
                    subject.EndMeasure();var validation=subject.Validate();Assert.True(validation.Passed,validation.Reason);
                    Assert.AreEqual(0,subject.Frames[1440].Leased);Assert.AreEqual(0,subject.Frames[1560].Leased);Assert.Greater(subject.Frames[1620].Leased,0);
                    Assert.LessOrEqual(subject.Metrics.maxPositionErrorPixels,.05f);
                }
                finally{subject.Cleanup();}
                yield return null;
            }
        }
    }
}
