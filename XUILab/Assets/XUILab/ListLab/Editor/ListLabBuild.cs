using System;
using System.IO;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEngine;

namespace XUILab.ListLab.Editor
{
    public static class ListLabBuild
    {
        private static bool requested;
        [MenuItem("XUILab/List Lab/Build Development Player")]
        public static void Build()
        {
            if(requested) { Debug.Log("List build already requested in this domain; duplicate request ignored."); return; }
            requested=true;
            try { BuildNow(); }
            catch { requested=false; throw; }
        }
        private static void BuildNow()
        {
            if(EditorApplication.isPlayingOrWillChangePlaymode || EditorApplication.isCompiling)
                throw new InvalidOperationException("Editor must be idle.");
            for(int i=0;i<UnityEngine.SceneManagement.SceneManager.sceneCount;i++)
                if(UnityEngine.SceneManagement.SceneManager.GetSceneAt(i).isDirty)
                    throw new InvalidOperationException("Save dirty scenes before building.");
            if(Application.unityVersion!="2022.3.45f1c1" || PlayerSettings.GetScriptingBackend(BuildTargetGroup.Standalone)!=ScriptingImplementation.Mono2x)
                throw new InvalidOperationException("Requires fixed Unity 2022.3.45f1c1 and Mono.");
            string id="list-dev-"+DateTime.UtcNow.ToString("yyyyMMddTHHmmssZ");
            string directory=Path.GetFullPath(Path.Combine(Application.dataPath,"../../Artifacts",id));
            string output=Path.Combine(directory,"build","XUILab-List.exe");
            Directory.CreateDirectory(Path.GetDirectoryName(output));
            var report=BuildPipeline.BuildPlayer(new BuildPlayerOptions {
                scenes=new[]{ListLabSceneBuilder.ScenePath}, locationPathName=output,
                target=BuildTarget.StandaloneWindows64, options=BuildOptions.Development });
            var summary=report.summary;
            File.WriteAllText(Path.Combine(directory,"build-summary.json"),JsonUtility.ToJson(new Record {
                buildId=id,result=summary.result.ToString(),outputPath=output,unityVersion=Application.unityVersion,
                totalErrors=(int)summary.totalErrors,totalWarnings=(int)summary.totalWarnings,
                totalTimeSeconds=summary.totalTime.TotalSeconds,totalSizeBytes=(long)summary.totalSize },true));
            if(summary.result!=BuildResult.Succeeded)throw new InvalidOperationException("List Player build failed: "+summary.result);
            Debug.Log("List Player build succeeded: "+output);
        }
        [Serializable] private sealed class Record
        {
            public string schemaVersion="xuilab.build.summary/v1",buildId,result,outputPath,unityVersion;
            public string backend="Mono2x";
            public int totalErrors,totalWarnings;
            public long totalSizeBytes;
            public double totalTimeSeconds;
        }
    }
}
