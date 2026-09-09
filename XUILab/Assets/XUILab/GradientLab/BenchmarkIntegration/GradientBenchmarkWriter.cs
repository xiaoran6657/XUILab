using System;
using System.Globalization;
using System.IO;
using System.Text;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using UnityEngine;
using XUILab.Benchmarking;

namespace XUILab.GradientLab
{
    public sealed class GradientBenchmarkWriter : IBenchmarkArtifactWriter
    {
        private readonly FileBenchmarkArtifactWriter inner=new FileBenchmarkArtifactWriter();
        private readonly GradientBenchmarkFactory factory;
        private readonly GradientPlayerBinding binding;
        private JObject observedBinding;
        public string RunDirectory=>inner.RunDirectory;
        public GradientBenchmarkWriter(GradientBenchmarkFactory factory,GradientPlayerBinding binding){this.factory=factory;this.binding=binding;}
        public void WriteInitial(BenchmarkRunResult result){observedBinding=binding.Document();inner.WriteInitial(result);}
        public void WriteTerminal(BenchmarkRunResult result)
        {
            inner.WriteTerminal(result);
            var current=factory.Current;
            var metrics=current?.Metrics!=null?JObject.Parse(JsonUtility.ToJson(current.Metrics)):new JObject {["correctness"]="not_run"};
            if(current?.Quality!=null){metrics["qualityMaxError"]=current.Quality.MaximumError;metrics["quantizationMaxError"]=current.Quality.QuantizationMaximum;}
            Write("gradient-metrics.json",metrics.ToString(Formatting.Indented));
            Write("gradient-binding.json",(observedBinding??binding.Document()).ToString(Formatting.Indented));
            var text=new StringBuilder("sample_index,action_frame,settled_frame,bias,visible,culled,dirty_delta,rebuild_delta,vertices,triangles,segments,changed_count\n");
            if(current?.Metrics!=null)for(int i=0;i<current.Metrics.sampleCount;i++)
            {
                var f=current.Frames[i];text.Append(f.Index).Append(',').Append(f.ActionFrame).Append(',').Append(f.SettledFrame).Append(',').Append(f.Bias.ToString("R",CultureInfo.InvariantCulture)).Append(',')
                    .Append(f.Visible).Append(',').Append(f.Culled).Append(',').Append(f.Dirty).Append(',').Append(f.Rebuild).Append(',').Append(f.Vertices).Append(',').Append(f.Triangles).Append(',').Append(f.Segments).Append(',').Append(f.Changed).Append('\n');
            }
            Write("gradient-samples.csv",text.ToString());
            if((string)binding.Plan["experimentId"]=="gradient-adaptive-v1")
            {
                var selections=new StringBuilder("sample_index,selection_calls,cache_hits,selection_ticks,min_segments,max_segments,quality_limited,estimated_error\n");
                if(current?.Metrics!=null)for(int i=0;i<current.Metrics.sampleCount;i++)
                {
                    var f=current.Frames[i];selections.Append(f.Index).Append(',').Append(f.SelectionCalls).Append(',').Append(f.SelectionCacheHits).Append(',').Append(f.SelectionTicks).Append(',').Append(f.MinSegments).Append(',').Append(f.MaxSegments).Append(',').Append(f.QualityLimited).Append(',').Append(f.EstimatedError.ToString("R",CultureInfo.InvariantCulture)).Append('\n');
                }
                Write("selection-samples.csv",selections.ToString());
            }
            Write("gradient-mesh.json",(current?.MeshEvidence??new JObject {["status"]="not_run"}).ToString(Formatting.Indented));
            Write("quality.json",(current?.Quality?.Document??new JObject {["status"]="not_run"}).ToString(Formatting.Indented));
            Write("quality-scan.csv",current?.Quality?.ScanCsv??"scan_index,bias,node_index,t,r,g,b,a,quant_r,quant_g,quant_b,quant_a\n");
            var summary=JObject.Parse(File.ReadAllText(Path.Combine(RunDirectory,"summary.json")));Bind(summary);summary["qualityStatus"]=current?.Quality?.Status??"not_assessed";
            File.WriteAllText(Path.Combine(RunDirectory,"summary.json"),summary.ToString(Formatting.Indented),new UTF8Encoding(false));
            var identity=JObject.Parse(File.ReadAllText(Path.Combine(RunDirectory,"identity.json")));Bind(identity);identity["planSha256"]=binding.PlanSha256;identity["buildManifestSha256"]=binding.BuildManifestSha256;
            var hashes=new JObject();
            foreach(var token in (JArray)binding.Plan["artifacts"])
            {
                string name=(string)token;if(name=="identity.json")continue;
                if(Path.GetFileName(name)!=name)throw new IOException("Artifact name must be a single segment.");
                var path=Path.Combine(RunDirectory,name);if(File.Exists(path))hashes[name]=GradientPlayerBinding.Hash(File.ReadAllBytes(path));
            }
            identity["artifactSha256"]=hashes;File.WriteAllText(Path.Combine(RunDirectory,"identity.json"),identity.ToString(Formatting.Indented),new UTF8Encoding(false));
        }
        private void Bind(JObject value)
        {foreach(string key in new[]{"planId","contractId","contractSha256","evidenceKind"})value[key]=binding.Plan[key].DeepClone();}
        private void Write(string name,string content)
        {using(var stream=new FileStream(Path.Combine(RunDirectory,name),FileMode.CreateNew,FileAccess.Write,FileShare.None))using(var writer=new StreamWriter(stream,new UTF8Encoding(false)))writer.Write(content);}
    }
}
