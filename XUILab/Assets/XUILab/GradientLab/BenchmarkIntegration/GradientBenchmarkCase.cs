using System;
using System.Globalization;
using System.Linq;
using Newtonsoft.Json.Linq;
using UnityEngine;
using UnityEngine.UI;
using XUILab.Benchmarking;

namespace XUILab.GradientLab
{
    [Serializable] public sealed class GradientRunMetrics
    {
        public string schemaVersion="xuilab.gradient.metrics/v1",runId,caseId,layout,state,direction;
        public int count,visibleCount,changedCount,sampleCount,expectedVertices,expectedTriangles;
        public int totalDirty,totalRebuild,cleanupActiveObjects=-1;
        public string correctness="not_run",reason="",drawCalls="unavailable",batches="unavailable",uiMarker="unavailable",gpu="unavailable";
        public string componentCountMeaning="GradientEffect work only; not total Canvas rebuild or GPU time";
        public float initialBias;
        public double coldPrepareMs;
        public string subdivisionMode="fixed",selectionAlgorithm="not_used";
        public long selectionFrequency,selectionTicks,coldSelectionTicks;
        public int selectionCalls,selectionCacheHits,coldSelectionCalls,coldSelectionCacheHits;
        public int minSelectedSegments=int.MaxValue,maxSelectedSegments,qualityLimitedObservations;
        public double maximumEstimatedError;
        public string selectionTimingMeaning="Stopwatch elapsed ticks include cache lookup and instrumentation; not whole-frame CPU time";
    }
    public struct GradientFrameMetrics
    {
        public int Index,ActionFrame,SettledFrame,Visible,Culled,Dirty,Rebuild,Vertices,Triangles,Segments,Changed;
        public float Bias;
        public int SelectionCalls,SelectionCacheHits,MinSegments,MaxSegments,QualityLimited;
        public long SelectionTicks;
        public double EstimatedError;
    }
    public sealed class GradientBenchmarkCase : IBenchmarkCase
    {
        private readonly GradientPlayerBinding binding;
        public string Id { get; private set; }
        public GradientRunMetrics Metrics { get; private set; }
        public GradientFrameMetrics[] Frames { get; private set; }
        public GradientQualityEvidence Quality { get; private set; }
        public JObject MeshEvidence { get; private set; }
        private GameObject root;
        private Image[] images;
        private CanvasRenderer[] renderers;
        private GradientEffect[] effects;
        private GradientTransitionController[] controllers;
        private int[] targets;
        private int preparedFrame,pending=-1,priorDirty,priorRebuild;
        private bool cleaned;
        private string failure;
        private Color start,end;
        private GradientDirection direction;
        private GradientCurve curve;
        private float initialBias,transitionFrom,transitionTo;
        private int actionOffset;
        private bool continueWarmup,adaptive;
        private int priorSelection,priorCache;
        private long priorSelectionTicks;
        public GradientBenchmarkCase(GradientPlayerBinding binding){this.binding=binding;}
        public bool IsReady=>root&&!cleaned&&Time.frameCount>preparedFrame+1;
        public void Prepare(BenchmarkRunConfig config)
        {
            var cold=System.Diagnostics.Stopwatch.StartNew();
            var p=binding.Parameters;Id=config.caseId;adaptive=(string)p["effectMode"]=="adaptive";
            if(adaptive && ((int)p["expectedVertices"]!=-1 || (int)p["expectedTriangles"]!=-1))throw new ArgumentException("Adaptive topology must be observed.");
            transitionFrom=(float?)p["transitionFrom"]??.25f;transitionTo=(float?)p["transitionTo"]??.75f;
            continueWarmup=(bool?)p["continueWarmup"]??false;actionOffset=continueWarmup?config.warmupFrames:0;
            int count=(int)p["count"];string state=(string)p["state"],layout=(string)p["layout"];
            if(!BenchmarkRunConfig.IsGradientCaseId(Id)||count<1||count>5000)throw new ArgumentException("Invalid gradient case.");
            if(Screen.width!=(int)p["screenWidth"]||Screen.height!=(int)p["screenHeight"]||QualitySettings.activeColorSpace.ToString()!=(string)p["colorSpace"])throw new InvalidOperationException("Screen/colorSpace mismatch.");
            if(!Application.isEditor && (SystemInfo.graphicsDeviceType.ToString()!=(string)p["graphicsApi"]||!Debug.isDebugBuild||Type.GetType("Mono.Runtime")==null))throw new InvalidOperationException("Player environment mismatch.");
            if(QualitySettings.names[QualitySettings.GetQualityLevel()]!=(string)p["qualityLevel"])throw new InvalidOperationException("Quality level mismatch.");
            start=ColorFrom((JArray)p["startRgba"]);end=ColorFrom((JArray)p["endRgba"]);initialBias=(float)p["bias"];
            direction=(GradientDirection)Enum.Parse(typeof(GradientDirection),(string)p["direction"]);curve=(GradientCurve)Enum.Parse(typeof(GradientCurve),(string)p["curve"]);
            targets=((JArray)p["targetIndices"]).Select(x=>(int)x).ToArray();
            int visible=(int)p["visibleCount"];if(targets.Distinct().Count()!=targets.Length||targets.Any(x=>x<0||x>=count))throw new ArgumentException("Invalid target indices.");
            Metrics=new GradientRunMetrics {runId=config.runId,caseId=Id,layout=layout,state=state,direction=direction.ToString(),count=count,visibleCount=visible,
                changedCount=((JArray)p["changedIndices"]).Count,initialBias=initialBias,expectedVertices=(int)p["expectedVertices"],expectedTriangles=(int)p["expectedTriangles"]};
            Metrics.subdivisionMode=adaptive?"adaptive":"fixed";Metrics.selectionAlgorithm=adaptive?GradientSegmentSelector.AlgorithmVersion:"not_used";
            Metrics.selectionFrequency=System.Diagnostics.Stopwatch.Frequency;
            Frames=new GradientFrameMetrics[config.measureFrames];images=new Image[count];renderers=new CanvasRenderer[count];effects=new GradientEffect[count];controllers=new GradientTransitionController[count];
            root=new GameObject("GradientBenchmarkCanvas",typeof(Canvas),typeof(CanvasScaler));root.GetComponent<Canvas>().renderMode=RenderMode.ScreenSpaceOverlay;
            var scaler=root.GetComponent<CanvasScaler>();scaler.uiScaleMode=CanvasScaler.ScaleMode.ConstantPixelSize;scaler.scaleFactor=1;
            Transform normalParent=root.transform,dynamicParent=normalParent;
            if(layout=="clip")
            {
                var viewport=GradientLabFactory.Rect("Viewport",normalParent,Vector2.zero,new Vector2(900,450));viewport.gameObject.AddComponent<RectMask2D>();normalParent=viewport;
            }
            if(layout=="split")
            {
                var split=GradientLabFactory.Rect("DynamicCanvas",normalParent,Vector2.zero,new Vector2(900,480));var canvas=split.gameObject.AddComponent<Canvas>();canvas.overrideSorting=false;dynamicParent=split;
            }
            int cols=(int)p["geometry"]["columns"],rows=(int)p["geometry"]["rows"];
            float cellWidth=900f/cols,cellHeight=480f/rows;
            for(int i=0;i<count;i++)
            {
                Vector2 position,size;
                if(layout=="clip"){position=new Vector2(0,225-12-i*24);size=new Vector2(880,24);}
                else if(layout=="large"){position=Vector2.zero;size=new Vector2(900,450);}
                else {position=new Vector2(-450+(i%cols+.5f)*cellWidth,240-(i/cols+.5f)*cellHeight);size=new Vector2(cellWidth*.9f,cellHeight*.9f);}
                var parent=layout=="split"&&i<Metrics.changedCount?dynamicParent:normalParent;
                var rect=GradientLabFactory.Rect("Cell"+i,parent,position,size);var image=rect.gameObject.AddComponent<Image>();image.raycastTarget=false;images[i]=image;renderers[i]=image.canvasRenderer;
                if(state=="image")continue;
                var effect=rect.gameObject.AddComponent<GradientEffect>();effect.StartColor=start;effect.EndColor=end;effect.Bias=initialBias;effect.Direction=direction;effect.Curve=curve;effect.FixedSegments=(int?)p["segments"]??GradientEffect.BaselineSegments;effects[i]=effect;
                if(adaptive){effect.ConfigureAdaptive((int)p["minSegments"],(int)p["maxSegments"],(float)p["tolerance"]);effect.SubdivisionMode=GradientSubdivisionMode.Adaptive;}
                if(state=="disabled")effect.enabled=false;
                if(state=="few"||state=="all"){var controller=rect.gameObject.AddComponent<GradientTransitionController>();controller.Automatic=false;controllers[i]=controller;}
            }
            Canvas.ForceUpdateCanvases();preparedFrame=Time.frameCount;cold.Stop();Metrics.coldPrepareMs=cold.Elapsed.TotalMilliseconds;
            Counts(out int coldDirty,out int coldRebuild,out int coldCalls,out int coldCache,out long coldTicks);
            Metrics.coldSelectionCalls=coldCalls;Metrics.coldSelectionCacheHits=coldCache;Metrics.coldSelectionTicks=coldTicks;
        }
        public void TickWarmup(int frameIndex){ApplyAction(frameIndex);}
        public void BeginMeasure()
        {
            if(!continueWarmup)
            {
                foreach(var controller in controllers)if(controller)controller.Cancel();
                foreach(var effect in effects)if(effect)effect.Bias=initialBias;
                Canvas.ForceUpdateCanvases();
            }
            Counts(out priorDirty,out priorRebuild,out priorSelection,out priorCache,out priorSelectionTicks);pending=-1;
        }
        public void TickMeasure(int frameIndex)
        {
            Settle();Counts(out priorDirty,out priorRebuild,out priorSelection,out priorCache,out priorSelectionTicks);
            ApplyAction(frameIndex+actionOffset);
            Frames[frameIndex]=new GradientFrameMetrics {Index=frameIndex,ActionFrame=Time.frameCount,Bias=Metrics.changedCount>0?effects[targets[0]].Bias:initialBias,Changed=Metrics.changedCount};pending=frameIndex;
        }
        private void ApplyAction(int frame)
        {
            if(Metrics.state=="same")
            {
                for(int i=0;i<targets.Length;i++){var e=effects[targets[i]];e.StartColor=start;e.EndColor=end;e.Direction=direction;e.Curve=curve;e.Bias=initialBias;}
                return;
            }
            if(Metrics.changedCount==0)return;
            int phase=frame%300;bool reverse=(frame/300)%2!=0;float progress=phase/299f;
            for(int i=0;i<targets.Length;i++)
            {
                var c=controllers[targets[i]];
                if(phase==0)c.StartTransition(reverse?transitionTo:transitionFrom,reverse?transitionFrom:transitionTo,1);
                c.SetProgress(progress);
            }
        }
        private void Counts(out int dirty,out int rebuild,out int selection,out int cache,out long ticks)
        {
            dirty=0;rebuild=0;selection=0;cache=0;ticks=0;
            for(int i=0;i<effects.Length;i++)if(effects[i])
            {dirty+=effects[i].DirtyCount;rebuild+=effects[i].RebuildCount;selection+=effects[i].SelectionCount;cache+=effects[i].SelectionCacheHits;ticks+=effects[i].SelectionTicks;}
        }
        private void Settle()
        {
            if(pending<0)return;
            var f=Frames[pending];f.SettledFrame=Time.frameCount;
            Counts(out int dirty,out int rebuild,out int selection,out int cache,out long ticks);f.Dirty=dirty-priorDirty;f.Rebuild=rebuild-priorRebuild;
            f.SelectionCalls=selection-priorSelection;f.SelectionCacheHits=cache-priorCache;f.SelectionTicks=ticks-priorSelectionTicks;f.MinSegments=int.MaxValue;
            for(int i=0;i<renderers.Length;i++)
            {
                bool visible=!renderers[i].cull;
                if(visible){f.Visible++;if(effects[i]&&effects[i].enabled){f.Vertices+=effects[i].LastVertexCount;f.Triangles+=effects[i].LastTriangleCount;f.Segments+=effects[i].SelectedSegments;}else{f.Vertices+=4;f.Triangles+=2;}}
                else f.Culled++;
                if(visible && effects[i] && effects[i].enabled)
                {
                    var e=effects[i];f.MinSegments=Math.Min(f.MinSegments,e.SelectedSegments);f.MaxSegments=Math.Max(f.MaxSegments,e.SelectedSegments);
                    if(adaptive)
                    {
                        if(e.LastMode!=GradientMeshMode.AdaptiveSegments || !e.HasGradientEstimate || !e.OutputQualityAssessed || e.SelectedSegments<(int)binding.Parameters["minSegments"] || e.SelectedSegments>(int)binding.Parameters["maxSegments"] || e.Bias!=f.Bias)failure="Adaptive observation mismatch.";
                        f.EstimatedError=Math.Max(f.EstimatedError,e.EstimatedGradientError);if(e.GradientQualityLimited)f.QualityLimited++;
                    }
                }
                if(visible!=(i<Metrics.visibleCount))failure="Visible/cull index set drift.";
            }
            if(f.SettledFrame!=f.ActionFrame+1)failure="Action did not settle on the following Unity frame.";
            int expected=Metrics.changedCount>0&&pending%300!=0?Metrics.changedCount:0;
            if(f.Dirty!=expected||f.Rebuild!=expected)failure="Unexpected component dirty/rebuild delta.";
            if(adaptive)
            {
                if(f.Vertices!=2*(f.Segments+f.Visible) || f.Triangles!=2*f.Segments)failure="Adaptive shared topology count mismatch.";
                if(f.SelectionCalls!=expected || f.SelectionCacheHits!=0 || f.SelectionTicks<0)failure="Unexpected adaptive selection/cache delta.";
            }
            else if(f.Vertices!=Metrics.visibleCount*Metrics.expectedVertices||f.Triangles!=Metrics.visibleCount*Metrics.expectedTriangles)failure="Visible topology count mismatch.";
            if(!adaptive && (f.SelectionCalls!=0 || f.SelectionCacheHits!=0 || f.SelectionTicks!=0))failure="Fixed path unexpectedly selected adaptive nodes.";
            if(f.MinSegments==int.MaxValue)f.MinSegments=0;
            Metrics.minSelectedSegments=Math.Min(Metrics.minSelectedSegments,f.MinSegments);Metrics.maxSelectedSegments=Math.Max(Metrics.maxSelectedSegments,f.MaxSegments);
            Metrics.selectionCalls+=f.SelectionCalls;Metrics.selectionCacheHits+=f.SelectionCacheHits;Metrics.selectionTicks+=f.SelectionTicks;
            Metrics.qualityLimitedObservations+=f.QualityLimited;Metrics.maximumEstimatedError=Math.Max(Metrics.maximumEstimatedError,f.EstimatedError);
            Frames[pending]=f;Metrics.sampleCount=pending+1;Metrics.totalDirty+=f.Dirty;Metrics.totalRebuild+=f.Rebuild;pending=-1;
        }
        public void EndMeasure(){Settle();}
        public BenchmarkCaseValidation Validate()
        {
            if(Metrics.sampleCount!=Frames.Length)failure="Gradient trace sample shortage.";
            for(int i=0;i<images.Length;i++)
            {
                if(renderers[i].cull)continue;
                var mesh=renderers[i].GetMesh();
                int expectedVertices=adaptive?2*(effects[i].SelectedSegments+1):Metrics.expectedVertices;
                int expectedTriangles=adaptive?2*effects[i].SelectedSegments:Metrics.expectedTriangles;
                if(!mesh||mesh.vertexCount!=expectedVertices||mesh.GetIndexCount(0)!=(uint)(expectedTriangles*3))failure="Actual submitted mesh mismatch.";
                if(effects[i]&&effects[i].enabled)
                {
                    var mode=curve==GradientCurve.Linear?GradientMeshMode.LinearVertices:adaptive?GradientMeshMode.AdaptiveSegments:GradientMeshMode.FixedSegments;
                    if(effects[i].LastMode!=mode)failure="Unexpected fallback mode.";
                }
            }
            MeshEvidence=CaptureMesh();
            Quality=GradientQualityEvidence.Create(binding,start,end,curve,initialBias);
            Metrics.correctness=failure==null?"pass":"fail";Metrics.reason=failure??"";
            return failure==null?BenchmarkCaseValidation.Pass():BenchmarkCaseValidation.Fail(failure);
        }
        private JObject CaptureMesh()
        {
            int index=Metrics.changedCount>0?targets[0]:0;var mesh=renderers[index].GetMesh();var vertices=new JArray();var positions=mesh.vertices;var colors=mesh.colors32;
            for(int i=0;i<positions.Length;i++)vertices.Add(new JObject {["position"]=new JArray(positions[i].x,positions[i].y,positions[i].z),["rgba"]=new JArray(colors[i].r,colors[i].g,colors[i].b,colors[i].a)});
            return new JObject {["elementIndex"]=index,["bias"]=effects[index]?effects[index].Bias:initialBias,["mode"]=effects[index]&&effects[index].enabled?effects[index].LastMode.ToString():"OriginalImage",["vertices"]=vertices,["indices"]=new JArray(mesh.triangles)};
        }
        public void Cleanup()
        {
            if(cleaned)return;cleaned=true;
            if(root){root.SetActive(false);Metrics.cleanupActiveObjects=root.activeInHierarchy?1:0;UnityEngine.Object.Destroy(root);}
            else if(Metrics!=null)Metrics.cleanupActiveObjects=0;
        }
        private static Color ColorFrom(JArray a)=>new Color((float)a[0],(float)a[1],(float)a[2],(float)a[3]);
    }
    public sealed class GradientBenchmarkFactory : IBenchmarkCaseFactory
    {
        private readonly GradientPlayerBinding binding;
        public GradientBenchmarkCase Current {get;private set;}
        public GradientBenchmarkFactory(GradientPlayerBinding binding){this.binding=binding;}
        public IBenchmarkCase Create(BenchmarkRunConfig config){Current=new GradientBenchmarkCase(binding);return Current;}
    }
}
