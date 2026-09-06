using System.Globalization;
using System.IO;
using System.Text;
using UnityEngine;
using XUILab.Benchmarking;

namespace XUILab.ListLab
{
    public sealed class ListBenchmarkWriter : IBenchmarkArtifactWriter
    {
        private readonly FileBenchmarkArtifactWriter inner=new FileBenchmarkArtifactWriter();
        private readonly ListBenchmarkFactory factory;
        public string RunDirectory=>inner.RunDirectory;
        public ListBenchmarkWriter(ListBenchmarkFactory factory){this.factory=factory;}
        public void WriteInitial(BenchmarkRunResult result){inner.WriteInitial(result);}
        public void WriteTerminal(BenchmarkRunResult result)
        {
            var current=factory.Current;
            if(current!=null && current.Metrics!=null)
            {
                File.WriteAllText(Path.Combine(RunDirectory,"list-metrics.json"),JsonUtility.ToJson(current.Metrics,true),new UTF8Encoding(false));
                if(result.EnteredMeasure)
                {
                    var text=new StringBuilder("sample_index,unity_frame,offset,visible,active,leased,cached,created,destroyed,bind_count,unbind_count\n");
                    for(int i=0;i<current.Metrics.sampleCount;i++)
                    {
                        var f=current.Frames[i];text.Append(f.Index).Append(',').Append(f.UnityFrame).Append(',').Append(f.Offset.ToString("R",CultureInfo.InvariantCulture)).Append(',')
                            .Append(f.Visible).Append(',').Append(f.Active).Append(',').Append(f.Leased).Append(',').Append(f.Cached).Append(',').Append(f.Created).Append(',')
                            .Append(f.Destroyed).Append(',').Append(f.Bind).Append(',').Append(f.Unbind).Append('\n');
                    }
                    File.WriteAllText(Path.Combine(RunDirectory,"list-samples.csv"),text.ToString(),new UTF8Encoding(false));
                }
            }
            inner.WriteTerminal(result);
        }
    }
}
