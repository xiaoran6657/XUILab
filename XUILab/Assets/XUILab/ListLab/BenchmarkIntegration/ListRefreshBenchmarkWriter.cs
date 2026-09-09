using System.Globalization;
using System.IO;
using System.Text;
using UnityEngine;
using XUILab.Benchmarking;

namespace XUILab.ListLab
{
    public sealed class ListRefreshBenchmarkWriter : IBenchmarkArtifactWriter
    {
        private readonly FileBenchmarkArtifactWriter inner=new FileBenchmarkArtifactWriter();
        private readonly ListRefreshBenchmarkFactory factory;
        private readonly RefreshPlayerBinding binding;
        public string RunDirectory => inner.RunDirectory;
        public ListRefreshBenchmarkWriter(ListRefreshBenchmarkFactory factory,RefreshPlayerBinding binding=null)
        {this.factory=factory;this.binding=binding;}
        public void WriteInitial(BenchmarkRunResult result){inner.WriteInitial(result);}
        public void WriteTerminal(BenchmarkRunResult result)
        {
            var current=factory.Current;
            if(current!=null&&current.Metrics!=null)
            {
                File.WriteAllText(Path.Combine(inner.RunDirectory,"refresh-metrics.json"),JsonUtility.ToJson(current.Metrics,true),new UTF8Encoding(false));
                if(binding!=null)File.WriteAllText(Path.Combine(inner.RunDirectory,"refresh-binding.json"),binding.Document().ToString(),new UTF8Encoding(false));
                if(result.EnteredMeasure)
                {
                    var csv=new StringBuilder("sample_index,action_frame,settled_frame,updates,target_mask,state_mask,label_checksum,bind_count,unbind_count,created,destroyed,leased,cached,pending,visible,offset\n");
                    for(int i=0;i<current.Metrics.sampleCount;i++)
                    {
                        var f=current.Frames[i];
                        csv.Append(f.Index).Append(',').Append(f.ActionFrame).Append(',').Append(f.SettledFrame).Append(',').Append(f.Updates).Append(',')
                            .Append(f.TargetMask).Append(',').Append(f.StateMask).Append(',').Append(f.LabelChecksum).Append(',').Append(f.Bind).Append(',')
                            .Append(f.Unbind).Append(',').Append(f.Created).Append(',').Append(f.Destroyed).Append(',').Append(f.Leased).Append(',')
                            .Append(f.Cached).Append(',').Append(f.Pending).Append(',').Append(f.Visible).Append(',').Append(f.Offset.ToString("R",CultureInfo.InvariantCulture)).Append('\n');
                    }
                    File.WriteAllText(Path.Combine(inner.RunDirectory,"refresh-samples.csv"),csv.ToString(),new UTF8Encoding(false));
                }
            }
            inner.WriteTerminal(result);
        }
    }
}

