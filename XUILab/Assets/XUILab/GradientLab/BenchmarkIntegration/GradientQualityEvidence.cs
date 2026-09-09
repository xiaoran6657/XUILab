using System;
using System.Globalization;
using System.Text;
using Newtonsoft.Json.Linq;
using UnityEngine;

namespace XUILab.GradientLab
{
    public sealed class GradientQualityEvidence
    {
        public JObject Document;
        public string ScanCsv,Status;
        public double MaximumError,QuantizationMaximum;
        public static GradientQualityEvidence Create(GradientPlayerBinding binding,Color start,Color end,GradientCurve curve,float initialBias)
        {
            string state=(string)binding.Parameters["state"];bool original=state=="image"||state=="disabled",dynamic=state=="few"||state=="all";
            int segments=original||curve==GradientCurve.Linear?1:((int?)binding.Parameters["segments"]??32);
            bool adaptive=(string)binding.Parameters["effectMode"]=="adaptive";
            var adaptivePositions=new float[65];var adaptiveErrors=new double[64];double[] worstPositions=null;
            float from=(float?)binding.Parameters["transitionFrom"]??.25f,to=(float?)binding.Parameters["transitionTo"]??.75f;
            var scan=new StringBuilder("scan_index,bias,node_index,t,r,g,b,a,quant_r,quant_g,quant_b,quant_a\n");
            double worst=-1,quantMax=0;float worstBias=initialBias;Color[] worstNodes=null;
            int scanCount=dynamic?600:1;
            for(int scanIndex=0;scanIndex<scanCount;scanIndex++)
            {
                bool reverse=(scanIndex/300)%2!=0;float bias=dynamic?Mathf.LerpUnclamped(reverse?to:from,reverse?from:to,(scanIndex%300)/299f):initialBias;
                if(adaptive)segments=GradientSegmentSelector.Select(start,end,bias,curve,(int)binding.Parameters["minSegments"],(int)binding.Parameters["maxSegments"],(float)binding.Parameters["tolerance"],adaptivePositions,adaptiveErrors).Segments;
                var positions=new double[segments+1];for(int n=0;n<=segments;n++)positions[n]=adaptive?adaptivePositions[n]:n/(double)segments;
                var nodes=new Color[segments+1];
                for(int n=0;n<=segments;n++)
                {
                    nodes[n]=original?Color.white:GradientFunction.Evaluate((float)positions[n],start,end,bias,curve);
                    Color32 quant=GradientFunction.Quantize(nodes[n]);
                    scan.Append(scanIndex).Append(',').Append(bias.ToString("R",CultureInfo.InvariantCulture)).Append(',').Append(n).Append(',').Append(positions[n].ToString("R",CultureInfo.InvariantCulture));
                    for(int c=0;c<4;c++){scan.Append(',').Append(nodes[n][c].ToString("R",CultureInfo.InvariantCulture));quantMax=Math.Max(quantMax,Math.Abs(nodes[n][c]-((Color)quant)[c]));}
                    scan.Append(',').Append(quant.r).Append(',').Append(quant.g).Append(',').Append(quant.b).Append(',').Append(quant.a).Append('\n');
                }
                double max=0;
                int cell=0;
                for(int i=0;i<=4096;i++)
                {
                    double t=i/4096.0;while(cell<segments-1 && t>positions[cell+1])cell++;double u=(t-positions[cell])/(positions[cell+1]-positions[cell]);
                    double w=original?0:curve==GradientCurve.Linear?t:Weight(t,bias);
                    for(int c=0;c<4;c++){double expected=original?1:start[c]+(end[c]-start[c])*w;double actual=nodes[cell][c]+(nodes[cell+1][c]-nodes[cell][c])*u;max=Math.Max(max,Math.Abs(expected-actual));}
                }
                if(max>worst){worst=max;worstBias=bias;worstNodes=nodes;worstPositions=positions;}
            }
            var samples=new JArray();
            int worstCell=0;
            for(int i=0;i<=4096;i++)
            {
                double t=i/4096.0;while(worstCell<worstNodes.Length-2 && t>worstPositions[worstCell+1])worstCell++;
                int cell=worstCell;double u=(t-worstPositions[cell])/(worstPositions[cell+1]-worstPositions[cell]),w=original?0:curve==GradientCurve.Linear?t:Weight(t,worstBias);
                var expected=new JArray();var actual=new JArray();
                for(int c=0;c<4;c++){expected.Add(original?1:start[c]+(end[c]-start[c])*w);actual.Add(worstNodes[cell][c]+(worstNodes[cell+1][c]-worstNodes[cell][c])*u);}
                samples.Add(new JObject {["t"]=t,["expectedRgba"]=expected,["actualRgba"]=actual});
            }
            var plan=binding.Plan;var q=(JObject)plan["quality"];
            var document=new JObject {["schemaVersion"]="xuilab.gradient.quality/v1",["runId"]=binding.Run["runId"].DeepClone(),["contractId"]=plan["contractId"].DeepClone(),["contractSha256"]=plan["contractSha256"].DeepClone(),
                ["evidenceKind"]=plan["evidenceKind"].DeepClone(),["referenceId"]=q["referenceId"].DeepClone(),["metricId"]=q["metricId"].DeepClone(),["threshold"]=q["threshold"].DeepClone(),["aggregation"]=q["aggregation"].DeepClone(),
                ["colorSpace"]="encoded-rgb",["alphaMode"]="straight-rgba-equal-weight",["samples"]=samples};
            return new GradientQualityEvidence {Document=document,ScanCsv=scan.ToString(),MaximumError=worst,QuantizationMaximum=quantMax,Status=worst<=(double)q["threshold"]?"pass":"quality_limited"};
        }
        private static double Weight(double t,double bias){double a=(1-bias)/bias;return t/(a+(1-a)*t);}
    }
}
