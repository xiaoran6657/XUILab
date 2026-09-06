using System;
using System.Collections;
using System.IO;
using UnityEngine;
using UnityEngine.UI;

namespace XUILab.ListLab
{
    // Diagnostic-only capture. This component is never installed for a benchmark run.
    public sealed class ListMediaCapture : MonoBehaviour
    {
        private string directory;
        private bool quit;
        private int originalCapture, originalTarget, originalVsync;
        private bool settingsCaptured;
        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        private static void Install()
        {
            string[] args=Environment.GetCommandLineArgs();int index=Array.IndexOf(args,"--list-media-dir");
            if(index<0)return;
            if(Array.IndexOf(args,"--xuilab-run")>=0)throw new InvalidOperationException("Media and benchmark runs must be separate.");
            if(index+1>=args.Length)throw new ArgumentException("Media output path missing.");
            var demo=UnityEngine.Object.FindObjectOfType<ListLabDemo>();if(!demo)throw new InvalidOperationException("ListLab scene required.");
            var capture=demo.gameObject.AddComponent<ListMediaCapture>();capture.directory=Path.GetFullPath(args[index+1]);
            capture.quit=Array.IndexOf(args,"--list-media-quit")>=0;
        }
        private IEnumerator Start()
        {
            if(Directory.Exists(directory))throw new IOException("Refusing to overwrite a capture directory.");
            Directory.CreateDirectory(directory);
            originalCapture=Time.captureFramerate;originalTarget=Application.targetFrameRate;originalVsync=QualitySettings.vSyncCount;settingsCaptured=true;
            Time.captureFramerate=15;Application.targetFrameRate=15;QualitySettings.vSyncCount=0;
            yield return null;
            var demo=GetComponent<ListLabDemo>();Click("Backend");yield return null;
            for(int frame=0;frame<450;frame++)
            {
                if(frame==150)Click("Backend");
                if(frame==300){Click("2 templates");Click("Effects");}
                if(frame<300)demo.View.SetPixelOffset((frame%150)/149f*demo.View.MaxOffset);
                else if(frame<390)demo.View.SetPixelOffset((frame-300)/89f*3000);
                if(frame==390){Click("Save");Click("Top");}
                if(frame==405)Click("Restore");
                if(frame==435)Click("Reopen");
                foreach(var text in UnityEngine.Object.FindObjectsOfType<Text>())
                    if(text.name=="Text" && text.fontSize==22)
                        text.text=frame<150?"NORMAL  /  1000 ROWS RETAINED":frame<300?"VIRTUAL  /  BOUNDED VISIBLE WINDOW":"REUSE  /  TWO TEMPLATES + FADE + RESTORE";
                yield return new WaitForEndOfFrame();
                var texture=ScreenCapture.CaptureScreenshotAsTexture();
                File.WriteAllBytes(Path.Combine(directory,"frame-"+frame.ToString("D4")+".png"),texture.EncodeToPNG());
                Destroy(texture);
            }
            File.WriteAllText(Path.Combine(directory,"capture.json"),JsonUtility.ToJson(new CaptureRecord{frames=450,fps=15,width=Screen.width,height=Screen.height,unityVersion=Application.unityVersion},true));
            Restore();if(quit)Application.Quit(0);
        }
        private static void Click(string name)
        {foreach(var button in UnityEngine.Object.FindObjectsOfType<Button>())if(button.name==name){button.onClick.Invoke();return;}throw new InvalidOperationException("Missing demo control "+name);}
        private void Restore(){if(!settingsCaptured)return;Time.captureFramerate=originalCapture;Application.targetFrameRate=originalTarget;QualitySettings.vSyncCount=originalVsync;settingsCaptured=false;}
        private void OnDestroy(){Restore();}
        [Serializable]private sealed class CaptureRecord{public string schemaVersion="xuilab.list.media/v1";public string purpose="diagnostic only; not performance samples";public int frames,fps,width,height;public string unityVersion;}
    }
}
