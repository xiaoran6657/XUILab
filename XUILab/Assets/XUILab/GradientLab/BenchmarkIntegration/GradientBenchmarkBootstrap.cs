using System;
using UnityEngine;
using XUILab.Benchmarking;

namespace XUILab.GradientLab
{
    [DefaultExecutionOrder(-100)] public sealed class GradientBenchmarkBootstrap : MonoBehaviour
    {
        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)] private static void Install()
        {
            if(UnityEngine.SceneManagement.SceneManager.GetActiveScene().name!="GradientLab")return;
            var demo=UnityEngine.Object.FindObjectOfType<GradientLabDemo>();if(demo&&!demo.GetComponent<GradientBenchmarkBootstrap>())demo.gameObject.AddComponent<GradientBenchmarkBootstrap>();
        }
        private BenchmarkRunner runner;
        private bool requested,quitIssued;
        private int width,height;
        private void Awake()
        {
            requested=Array.IndexOf(Environment.GetCommandLineArgs(),"--xuilab-run")>=0;
            if(requested){var demo=GetComponent<GradientLabDemo>();if(demo){demo.MeasurementMode=true;demo.enabled=false;}}
        }
        private void Start()
        {
            if(!requested)return;
            try
            {
                var binding=GradientPlayerBinding.Load(Environment.GetCommandLineArgs());binding.CaptureStartFocus(Application.isFocused);width=Screen.width;height=Screen.height;
                var factory=new GradientBenchmarkFactory(binding);runner=StartBoundRunner(binding,factory,new GradientBenchmarkWriter(factory,binding));
            }
            catch(Exception e){Debug.LogError(e);Application.Quit(2);}
        }
        public static BenchmarkRunner StartBoundRunner(GradientPlayerBinding binding,IBenchmarkCaseFactory factory,IBenchmarkArtifactWriter writer)
        {
            var instance=new BenchmarkRunner(factory,writer:writer);instance.Start(binding.Config);
            if(!binding.StartFocus)instance.MarkFocusLost();
            return instance;
        }
        private void Update()
        {
            if(runner==null)return;
            if(!runner.IsTerminal){if(Screen.width!=width||Screen.height!=height)runner.MarkPaused();runner.Tick(Time.unscaledDeltaTime*1000.0,Time.frameCount);}
            else if(!quitIssued&&runner.Result.Config.quitWhenDone){quitIssued=true;Application.Quit(runner.Result.ExitCode);}
        }
        private void OnApplicationFocus(bool focus){if(!focus&&runner!=null&&!runner.IsTerminal)runner.MarkFocusLost();}
        private void OnApplicationPause(bool paused){if(paused&&runner!=null&&!runner.IsTerminal)runner.MarkPaused();}
        private void OnDestroy(){runner?.Dispose();}
    }
}
