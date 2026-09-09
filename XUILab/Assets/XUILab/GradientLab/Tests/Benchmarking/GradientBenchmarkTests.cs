using System;
using System.Collections;
using System.IO;
using System.Linq;
using Newtonsoft.Json.Linq;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.TestTools;
using XUILab.Benchmarking;

namespace XUILab.GradientLab.Tests
{
    public sealed class GradientBenchmarkTests
    {
        private BenchmarkRunner runner;
        [TearDown] public void Cleanup(){runner?.Dispose();runner=null;}
        private static GradientPlayerBinding Binding(string layout,string state,int measure)
        {
            int count=layout=="clip"?1000:100,visible=layout=="clip"?19:100,changed=state=="few"?(visible+9)/10:state=="all"?visible:0;
            string id="gradient-"+layout+"-"+count+"-"+state+"-horizontal-25";
            var p=new JObject {["count"]=count,["state"]=state,["layout"]=layout,["screenWidth"]=Screen.width,["screenHeight"]=Screen.height,["colorSpace"]="Linear",["qualityLevel"]=QualitySettings.names[QualitySettings.GetQualityLevel()],
                ["startRgba"]=new JArray(.04,.75,.95,1),["endRgba"]=new JArray(.95,.15,.4,.6),["bias"]=.25,["direction"]="Horizontal",["curve"]=state=="linear"?"Linear":"Nonlinear",
                ["visibleCount"]=visible,["changedIndices"]=new JArray(Enumerable.Range(0,changed)),["targetIndices"]=new JArray(Enumerable.Range(0,state=="same"?count:changed)),
                ["expectedVertices"]=state=="image"||state=="disabled"||state=="linear"?4:66,["expectedTriangles"]=state=="image"||state=="disabled"||state=="linear"?2:64,
                ["geometry"]=new JObject {["columns"]=14,["rows"]=8}};
            var config=new BenchmarkRunConfig {runId="gradient-test-"+Guid.NewGuid().ToString("N"),seriesId="fixture-gradient",caseId=id,candidateId="test",buildId="editor-test",sourceRevision="test",tier="editor-playmode",warmupFrames=4,measureFrames=measure,sampleCapacity=measure,enableProfilerRecorders=false,targetFrameRate=-1,
                outputDirectory=Path.GetFullPath(Path.Combine(Application.dataPath,"../../Artifacts/gradient-runner-tests"))};
            var plan=new JObject {["planId"]="fixture-gradient",["contractId"]="gradient-schlick-v1",["contractSha256"]=new string('0',64),["evidenceKind"]="fixture",
                ["quality"]=new JObject {["referenceId"]="schlick-dense4097-v1",["metricId"]="rgba-max-absolute-error",["threshold"]=.01,["aggregation"]="max-absolute-rgba"},
                ["artifacts"]=new JArray("config.json","environment.json","identity.json","samples.csv","summary.json","report.md","events.log","gradient-metrics.json","gradient-samples.csv","gradient-binding.json","gradient-mesh.json","quality.json","quality-scan.csv")};
            return new GradientPlayerBinding {Config=config,Parameters=p,Plan=plan,Run=new JObject {["runId"]=config.runId,["parameters"]=p},Preflight=new JObject {["status"]="fixture"},PlanSha256=new string('0',64)};
        }
        private IEnumerator Check(string layout,string state,int frames,bool startFocus=true,int segments=32,bool continuous=false)
        {
            var binding=Binding(layout,state,frames);
            binding.Parameters["segments"]=segments;
            if(continuous){binding.Config.caseId="gradient-subdivision-grid-dynamic-s"+segments;binding.Config.warmupFrames=300;binding.Parameters["continueWarmup"]=true;binding.Parameters["transitionFrom"]=.05;binding.Parameters["transitionTo"]=.95;binding.Parameters["bias"]=.05;binding.Parameters["expectedVertices"]=2*(segments+1);binding.Parameters["expectedTriangles"]=2*segments;}
            var factory=new GradientBenchmarkFactory(binding);var writer=new GradientBenchmarkWriter(factory,binding);
            binding.CaptureStartFocus(startFocus);runner=GradientBenchmarkBootstrap.StartBoundRunner(binding,factory,writer);
            for(int i=0;!runner.IsTerminal&&i<frames+binding.Config.warmupFrames+100;i++){yield return null;runner.Tick(Time.unscaledDeltaTime*1000,Time.frameCount);}
            Assert.True(runner.IsTerminal);Assert.AreEqual(BenchmarkRunState.Completed,runner.State,runner.Result?.FailureReason);
            Assert.AreEqual(BenchmarkCorrectnessStatus.Pass,runner.Result.Correctness,runner.Result.FailureReason);Assert.True(runner.Result.ExportSucceeded);Assert.True(runner.Result.CleanupSucceeded);
            var observed=JObject.Parse(File.ReadAllText(Path.Combine(writer.RunDirectory,"gradient-binding.json")));Assert.AreEqual(startFocus,(bool)observed["startFocus"]);Assert.AreEqual(JTokenType.Boolean,observed["observedFocusAtExport"].Type);
            if(!startFocus){Assert.AreEqual(BenchmarkMeasurementValidity.Invalid,runner.Result.MeasurementValidity);StringAssert.Contains("focus_lost",File.ReadAllText(Path.Combine(writer.RunDirectory,"events.log")));}
            Assert.AreEqual(frames,factory.Current.Metrics.sampleCount);Assert.AreEqual(0,factory.Current.Metrics.cleanupActiveObjects);
            for(int i=0;i<frames;i++){var f=factory.Current.Frames[i];Assert.AreEqual(f.ActionFrame+1,f.SettledFrame);Assert.AreEqual(runner.Result.Samples[i].UnityFrame,f.SettledFrame);}
            var identity=JObject.Parse(File.ReadAllText(Path.Combine(writer.RunDirectory,"identity.json")));
            foreach(var property in ((JObject)identity["artifactSha256"]).Properties())Assert.AreEqual((string)property.Value,GradientPlayerBinding.Hash(File.ReadAllBytes(Path.Combine(writer.RunDirectory,property.Name))));
            Assert.AreEqual(12,((JObject)identity["artifactSha256"]).Count);
            if(state=="same"||state=="static")Assert.AreEqual(0,factory.Current.Metrics.totalDirty);
            if(frames>300){Assert.AreEqual(0,factory.Current.Frames[300].Dirty);Assert.AreEqual(factory.Current.Metrics.changedCount,factory.Current.Frames[301].Dirty);}
            if(continuous)
            {
                Assert.That(factory.Current.Frames[0].Bias,Is.EqualTo(.95f).Within(1e-6));Assert.AreEqual(0,factory.Current.Frames[0].Dirty);
                Assert.That(factory.Current.Frames[300].Bias,Is.EqualTo(.05f).Within(1e-6));
                foreach(var f in factory.Current.Frames){Assert.AreEqual(100*segments,f.Segments);Assert.AreEqual(100*2*(segments+1),f.Vertices);}
            }
            runner.Dispose();runner=null;yield return null;
        }
        [Test] public void AdaptiveCaseNamesAreExactAndDoNotBroadenUnknownIds()
        {
            foreach(string scenario in new[]{"large-static-05","large-static-50","large-static-95","grid-static-05","grid-static-50","grid-static-95","large-dynamic","grid-dynamic"})
            foreach(string variant in new[]{"fixed32","adaptive64"})Assert.True(BenchmarkRunConfig.IsGradientCaseId("gradient-adaptive-"+scenario+"-"+variant));
            foreach(string id in new[]{"gradient-adaptive-grid-dynamic-adaptive65","gradient-adaptive-grid-static-25-adaptive64","gradient-adaptive-clip-dynamic-adaptive64","gradient-adaptive-grid-dynamic-fixed8","gradient-adaptive-grid-dynamic-adaptive64suffix"})Assert.False(BenchmarkRunConfig.IsGradientCaseId(id));
        }
        [UnityTest] public IEnumerator AdaptiveRunnerObservesVariableTopologyAndSelectionCost()
        {
            foreach(string state in new[]{"static","all"})
            {
                int frames=state=="all"?302:8;var binding=Binding("grid",state,frames);
                binding.Config.caseId="gradient-adaptive-grid-"+(state=="all"?"dynamic":"static-05")+"-adaptive64";
                binding.Config.warmupFrames=300;var p=binding.Parameters;
                p["effectMode"]="adaptive";p["segments"]=32;p["minSegments"]=1;p["maxSegments"]=64;p["tolerance"]=.01;
                p["continueWarmup"]=true;p["transitionFrom"]=.05;p["transitionTo"]=.95;p["bias"]=.05;p["expectedVertices"]=-1;p["expectedTriangles"]=-1;
                binding.Plan["experimentId"]="gradient-adaptive-v1";((JArray)binding.Plan["artifacts"]).Add("selection-samples.csv");
                var factory=new GradientBenchmarkFactory(binding);var writer=new GradientBenchmarkWriter(factory,binding);binding.CaptureStartFocus(true);
                runner=GradientBenchmarkBootstrap.StartBoundRunner(binding,factory,writer);
                for(int i=0;!runner.IsTerminal&&i<frames+400;i++){yield return null;runner.Tick(Time.unscaledDeltaTime*1000,Time.frameCount);}
                Assert.True(runner.IsTerminal);Assert.AreEqual(BenchmarkCorrectnessStatus.Pass,runner.Result.Correctness,runner.Result.FailureReason);
                Assert.True(runner.Result.ExportSucceeded);Assert.True(runner.Result.CleanupSucceeded);
                var m=factory.Current.Metrics;Assert.AreEqual(100,m.coldSelectionCalls);Assert.AreEqual(0,m.coldSelectionCacheHits);Assert.Greater(m.coldSelectionTicks,0);
                Assert.AreEqual(0,m.selectionCacheHits);Assert.AreEqual(0,m.qualityLimitedObservations);Assert.That(m.maxSelectedSegments,Is.InRange(1,64));
                Assert.AreEqual(state=="all"?30000:0,m.selectionCalls);Assert.AreEqual(m.totalRebuild,m.selectionCalls);
                if(state=="all"){Assert.Greater(m.selectionTicks,0);Assert.Greater(m.maxSelectedSegments,m.minSelectedSegments);}else Assert.AreEqual(0,m.selectionTicks);
                foreach(var f in factory.Current.Frames)
                {
                    Assert.AreEqual(f.ActionFrame+1,f.SettledFrame);Assert.AreEqual(2*(f.Segments+f.Visible),f.Vertices);Assert.AreEqual(2*f.Segments,f.Triangles);
                    Assert.AreEqual(f.Rebuild,f.SelectionCalls);Assert.AreEqual(0,f.SelectionCacheHits);
                }
                var identity=JObject.Parse(File.ReadAllText(Path.Combine(writer.RunDirectory,"identity.json")));
                Assert.AreEqual(13,((JObject)identity["artifactSha256"]).Count);
                foreach(var property in ((JObject)identity["artifactSha256"]).Properties())Assert.AreEqual((string)property.Value,GradientPlayerBinding.Hash(File.ReadAllBytes(Path.Combine(writer.RunDirectory,property.Name))));
                Assert.AreEqual(frames+1,File.ReadAllLines(Path.Combine(writer.RunDirectory,"selection-samples.csv")).Length);
                Assert.AreEqual("pass",factory.Current.Quality.Status);Assert.LessOrEqual(factory.Current.Quality.MaximumError,.01);
                runner.Dispose();runner=null;yield return null;
            }
        }
        [UnityTest] public IEnumerator FixedSubdivisionContinuesWarmupAndSamplesAllCounts(){foreach(int segments in new[]{8,16,32,64})yield return Check("grid","all",302,true,segments,true);}
        [UnityTest] public IEnumerator StartupFocusLossCannotBeErasedByExportObservation(){yield return Check("grid","static",8,false);}
        [UnityTest] public IEnumerator StaticAndRepeatedSettersDoNotDirty(){yield return Check("grid","static",8);yield return Check("grid","same",8);}
        [UnityTest] public IEnumerator DynamicAndSplitSettleWholeFrames(){yield return Check("grid","all",302);yield return Check("split","few",302);}
        [UnityTest] public IEnumerator ClippedTargetsUseActualVisibleSet(){yield return Check("clip","few",302);}
        [UnityTest] public IEnumerator ImageDisabledAndLinearPreserveOriginalTopology(){foreach(string state in new[]{"image","disabled","linear"})yield return Check("grid",state,8);}
    }
}
