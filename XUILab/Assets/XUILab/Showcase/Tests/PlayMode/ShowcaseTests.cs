using System.Collections;
using System.Linq;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.TestTools;
using UnityEngine.UI;
using XUILab.Benchmarking;
using XUILab.GradientLab;
namespace XUILab.Showcase.Tests
{
    public sealed class ShowcaseTests
    {
        private GameObject root;
        [UnityTearDown] public IEnumerator Cleanup(){if(root)Object.Destroy(root);yield return null;yield return null;}
        [Test] public void SamplingAndEditorNeverInstallNavigation()
        {
            foreach(var scene in new[]{"ListLab","GradientLab","BenchmarkSmoke"})
            {
                Assert.True(ShowcaseNavigation.AllowsNavigation(new string[0],false,scene));
                Assert.False(ShowcaseNavigation.AllowsNavigation(new string[0],true,scene));
                foreach(var flag in new[]{"--xuilab-run","--list-media-dir","--gradient-media-dir"})Assert.False(ShowcaseNavigation.AllowsNavigation(new[]{flag},false,scene));
            }
            Assert.False(ShowcaseNavigation.AllowsNavigation(new string[0],false,"SampleScene"));
        }
        [UnityTest] public IEnumerator DiagnosticTerminalsAndInterruptionRestoreSettings()
        {
            int target=Application.targetFrameRate,vsync=QualitySettings.vSyncCount;
            root=new GameObject("showcase-test");var nav=root.AddComponent<ShowcaseNavigation>();
            foreach(var mode in new[]{"normal","fail","invalid"})
            {
                nav.StartDiagnostic(mode);
                for(int i=0;i<300&&nav.DiagnosticRunning;i++)yield return null;
                Assert.False(nav.DiagnosticRunning);
                Assert.AreEqual(mode=="normal",nav.DiagnosticResult.IsProcessSuccess);
                if(mode=="fail")Assert.AreEqual(BenchmarkFailureCode.ConfigurationInvalid,nav.DiagnosticResult.FailureCode);
                if(mode=="invalid")Assert.AreEqual(BenchmarkMeasurementValidity.Invalid,nav.DiagnosticResult.MeasurementValidity);
                Assert.AreEqual(target,Application.targetFrameRate);Assert.AreEqual(vsync,QualitySettings.vSyncCount);
            }
            nav.StartDiagnostic("normal");yield return null;nav.StopDiagnostic();
            Assert.AreEqual(target,Application.targetFrameRate);Assert.AreEqual(vsync,QualitySettings.vSyncCount);
        }
        [UnityTest] public IEnumerator GradientButtonsChangeMeshAndStopTransition()
        {
            root=new GameObject("gradient-test",typeof(GradientLabDemo));var demo=root.GetComponent<GradientLabDemo>();yield return null;yield return null;
            Click("Fixed / Adaptive");yield return null;Canvas.ForceUpdateCanvases();
            Assert.True(demo.Effects.All(e=>e.SubdivisionMode==GradientSubdivisionMode.Adaptive));
            Assert.True(demo.Effects.Any(e=>e.LastMode==GradientMeshMode.AdaptiveSegments));
            Assert.True(demo.Effects.Any(e=>e.LastMode==GradientMeshMode.VertexFallback));
            Click("Segments");Assert.True(demo.Effects.All(e=>e.FixedSegments==64));
            Click("Bias");Assert.True(demo.Effects.All(e=>Mathf.Approximately(e.Bias,.5f)));
            Click("Transition");yield return new WaitForSecondsRealtime(.1f);
            float progressed=demo.Effects[0].Bias;Assert.Greater(progressed,.05f);
            Click("Stop");yield return new WaitForSecondsRealtime(.1f);Assert.AreEqual(progressed,demo.Effects[0].Bias);
        }
        private static void Click(string name){Object.FindObjectsOfType<Button>().Single(b=>b.name==name).onClick.Invoke();}
    }
}
