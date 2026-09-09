using System;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using Newtonsoft.Json.Linq;
using UnityEngine;
using XUILab.Benchmarking;

namespace XUILab.ListLab
{
    public sealed class RefreshPlayerBinding
    {
        public JObject Plan, Run, Parameters, Preflight;
        public string PlanSha256,BuildManifestSha256;
        public bool StartFocus {get;private set;}
        public void CaptureStartFocus(bool focused){StartFocus=focused;}
        public BenchmarkRunConfig Config;
        public static string Hash(byte[] bytes)
        {using(var sha=SHA256.Create())return BitConverter.ToString(sha.ComputeHash(bytes)).Replace("-","").ToLowerInvariant();}
        public static string Arg(string[] args,string key)
        {int i=Array.IndexOf(args,key);if(i<0||i+1>=args.Length)throw new ArgumentException("Missing "+key);return args[i+1];}
        public static RefreshPlayerBinding Load(string[] args)
        {
            var bytes=File.ReadAllBytes(Arg(args,"--refresh-plan"));string hash=Hash(bytes);
            if(hash!=Arg(args,"--refresh-plan-sha256"))throw new InvalidDataException("Plan hash mismatch.");
            var plan=JObject.Parse(System.Text.Encoding.UTF8.GetString(bytes));
            if((string)plan["schemaVersion"]!="xuilab.list-refresh.plan/v1"||(string)plan["status"]!="frozen"||(string)plan["evidenceKind"]!="windows-development-player")throw new InvalidDataException("Frozen Player plan required.");
            string runId=Arg(args,"--xuilab-run-id");var matches=((JArray)plan["runs"]).OfType<JObject>().Where(x=>(string)x["runId"]==runId).ToArray();
            if(matches.Length!=1)throw new InvalidDataException("Run must occur exactly once.");
            var run=matches[0];var p=(JObject)run["parameters"];
            string manifestPath=Path.GetFullPath(Arg(args,"--refresh-build-manifest"));var manifestBytes=File.ReadAllBytes(manifestPath);string manifestHash=Hash(manifestBytes);
            if(manifestHash!=Arg(args,"--refresh-build-manifest-sha256")||manifestHash!=(string)p["buildManifestSha256"]||((JArray)plan["runs"]).Any(x=>(string)x["parameters"]["buildManifestSha256"]!=manifestHash))throw new InvalidDataException("Build manifest hash mismatch.");
            var manifest=JObject.Parse(System.Text.Encoding.UTF8.GetString(manifestBytes));
            if((string)manifest["schemaVersion"]!="xuilab.list-refresh.build/v1")throw new InvalidDataException("Build manifest schema mismatch.");
            foreach(string key in new[]{"candidateId","buildId","sourceRevision","dirty"})if(!JToken.DeepEquals(manifest[key],plan[key]))throw new InvalidDataException("Build manifest identity mismatch: "+key);
            string buildRoot=Path.GetDirectoryName(manifestPath),prefix=buildRoot.TrimEnd(Path.DirectorySeparatorChar)+Path.DirectorySeparatorChar;
            var files=manifest["files"] as JObject;if(files==null||files.Count==0)throw new InvalidDataException("Build file hashes missing.");
            foreach(var file in files.Properties())
            {
                string full=Path.GetFullPath(Path.Combine(buildRoot,file.Name));
                if(Path.IsPathRooted(file.Name)||file.Name.Split('/','\\').Any(x=>x=="..")||!full.StartsWith(prefix,StringComparison.OrdinalIgnoreCase))throw new InvalidDataException("Build file escapes root.");
                if(Hash(File.ReadAllBytes(full))!=(string)file.Value)throw new InvalidDataException("Build file hash mismatch: "+file.Name);
            }
            string playerName=(string)manifest["player"];
            if(playerName==null||files[playerName]==null)throw new InvalidDataException("Player is not hashed.");
            if(!Application.isEditor)
            {
                using(var process=System.Diagnostics.Process.GetCurrentProcess())
                    if(!string.Equals(Path.GetFullPath(process.MainModule.FileName),Path.GetFullPath(Path.Combine(buildRoot,playerName)),StringComparison.OrdinalIgnoreCase))throw new InvalidDataException("Running executable does not match manifest.");
            }
            var gateBytes=File.ReadAllBytes(Arg(args,"--refresh-preflight"));
            if(Hash(gateBytes)!=(string)p["preflightSha256"])throw new InvalidDataException("Preflight hash mismatch.");
            var gate=JObject.Parse(System.Text.Encoding.UTF8.GetString(gateBytes));
            if((string)gate["status"]!="pass"||(string)gate["candidateId"]!=(string)plan["candidateId"])throw new InvalidDataException("Preflight gate not accepted for candidate.");
            if((string)plan["contractId"]!="list-refresh/v1" || !BenchmarkRunConfig.IsListRefreshCaseId((string)run["caseId"]))
                throw new InvalidDataException("Refresh contract/case mismatch.");
            int index=(int)run["runIndex"],repeats=(int)run["plannedRepeatCount"];
            if(index<1||index>repeats)throw new InvalidDataException("Run index must be 1-based.");
            var config=new BenchmarkRunConfig {runId=runId,seriesId=(string)plan["planId"],runIndex=index,plannedRepeatCount=repeats,
                caseId=(string)run["caseId"],candidateId=(string)plan["candidateId"],buildId=(string)plan["buildId"],sourceRevision=(string)plan["sourceRevision"],dirty=(bool)plan["dirty"],
                tier=Application.isEditor?"editor-playmode":"windows-development-player",warmupFrames=(int)run["warmupFrames"],measureFrames=(int)run["measureFrames"],sampleCapacity=(int)run["sampleCapacity"],
                frameBudgetMs=(double)run["frameBudgetMs"],targetFrameRate=(int)p["targetFrameRate"],vSyncCount=(int)p["vSyncCount"],outputDirectory=Arg(args,"--xuilab-output-root"),quitWhenDone=true};
            var error=config.Validate();if(error!=null)throw new InvalidDataException(error);
            return new RefreshPlayerBinding {Plan=plan,Run=run,Parameters=p,Preflight=gate,PlanSha256=hash,BuildManifestSha256=manifestHash,Config=config};
        }
        public JObject Document()
        {
            return new JObject { ["schemaVersion"]="xuilab.list-refresh.binding/v1",["planSha256"]=PlanSha256,["planId"]=Plan["planId"].DeepClone(),
                ["contractId"]=Plan["contractId"].DeepClone(),["contractSha256"]=Plan["contractSha256"].DeepClone(),["run"]=Run.DeepClone(),["preflight"]=Preflight.DeepClone(),
                ["colorSpace"]=QualitySettings.activeColorSpace.ToString(),["batchMode"]=Application.isBatchMode,["startFocus"]=StartFocus,["observedFocusAtExport"]=Application.isFocused,["buildManifestSha256"]=BuildManifestSha256,
                ["pipeline"]=QualitySettings.renderPipeline?QualitySettings.renderPipeline.name:"none"};
        }
    }
}
