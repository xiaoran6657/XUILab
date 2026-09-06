using System;
using UnityEngine;
using XUILab.Benchmarking;

namespace XUILab.ListLab
{
    [DefaultExecutionOrder(-100)]
    public sealed class ListBenchmarkBootstrap : MonoBehaviour
    {
        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        private static void Install()
        {
            if(UnityEngine.SceneManagement.SceneManager.GetActiveScene().name!="ListLab")return;
            var demo=UnityEngine.Object.FindObjectOfType<ListLabDemo>();
            if(demo&&!demo.GetComponent<ListBenchmarkBootstrap>())demo.gameObject.AddComponent<ListBenchmarkBootstrap>();
        }
        private BenchmarkRunner runner;
        private bool requested,quitIssued;
        private int width,height;
        public BenchmarkRunResult Result=>runner?.Result;
        private void Awake()
        {
            requested=Array.IndexOf(Environment.GetCommandLineArgs(),"--xuilab-run")>=0;
            if(requested){var demo=GetComponent<ListLabDemo>();if(demo){demo.MeasurementMode=true;demo.enabled=false;}}
        }
        private void Start()
        {
            if(!requested)return;
            if(!BenchmarkCommandLine.TryCreateRunConfig(Environment.GetCommandLineArgs(),out var config,out var error))
            {Debug.LogError(error);Application.Quit(2);return;}
            width=Screen.width;height=Screen.height;var factory=new ListBenchmarkFactory();
            runner=new BenchmarkRunner(factory,writer:new ListBenchmarkWriter(factory));runner.Start(config);
        }
        private void Update()
        {
            if(runner==null)return;
            if(!runner.IsTerminal)
            {
                if(Screen.width!=width||Screen.height!=height)runner.MarkPaused();
                runner.Tick(Time.unscaledDeltaTime*1000.0,Time.frameCount);
            }
            else if(!quitIssued&&runner.Result.Config.quitWhenDone){quitIssued=true;Application.Quit(runner.Result.ExitCode);}
        }
        private void OnApplicationFocus(bool focus){if(!focus&&runner!=null&&!runner.IsTerminal)runner.MarkFocusLost();}
        private void OnApplicationPause(bool paused){if(paused&&runner!=null&&!runner.IsTerminal)runner.MarkPaused();}
        private void OnDestroy(){runner?.Dispose();}
    }
}
