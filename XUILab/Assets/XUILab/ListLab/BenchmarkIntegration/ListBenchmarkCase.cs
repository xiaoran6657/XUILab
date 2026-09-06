using System;
using System.Globalization;
using UnityEngine;
using XUILab.Benchmarking;

namespace XUILab.ListLab
{
    [Serializable]
    public sealed class ListMetrics
    {
        public string schemaVersion = "xuilab.list.metrics/v1";
        public string runId, caseId, actionProfile;
        public int itemCount;
        public bool virtualized;
        public double coldBuildMs, firstInteractiveMs;
        public string correctness = "not_run", reason = "";
        public float maxPositionErrorPixels;
        public int createdAtMeasureStart, destroyedAtMeasureStart;
        public int finalCreated, finalDestroyed, finalLeased, finalCached, finalUniqueTotal;
        public int cleanupUniqueTotal = -1, rejectedReturns, sampleCount;
        public string uiRebuildMetric = "unavailable";
        public string uiRebuildReason = "No validated UI rebuild recorder in this Player; Bind counts are not mesh rebuild counts.";
    }
    public struct ListFrameMetrics
    {
        public int Index, UnityFrame;
        public float Offset;
        public int Visible, Active, Leased, Cached, Created, Destroyed, Bind, Unbind;
    }
    public sealed class ListBenchmarkCase : IBenchmarkCase
    {
        public string Id { get; private set; }
        public ListMetrics Metrics { get; private set; }
        public ListFrameMetrics[] Frames { get; private set; }
        public ListView View { get; private set; }
        private GameObject root;
        private ListItem[] data;
        private ListPosition saved;
        private double openedAt;
        private int preparedFrame;
        private bool prepared, cleaned;
        private string failedReason;
        private float expectedOffset;
        private int priorFirst, priorEnd;

        public bool IsReady
        {
            get
            {
                if (!prepared || cleaned || Time.frameCount <= preparedFrame) return false;
                if (Metrics.firstInteractiveMs == 0) Metrics.firstInteractiveMs = ClockMs() - openedAt;
                return true;
            }
        }
        public void Prepare(BenchmarkRunConfig config)
        {
            if (!BenchmarkRunConfig.IsListCaseId(config.caseId) || config.caseVersion != "1") throw new ArgumentException("Unsupported list profile.");
            string[] parts = config.caseId.Split('-'); Id = config.caseId;
            Metrics = new ListMetrics { runId=config.runId,caseId=Id,virtualized=parts[1]=="virtual",
                itemCount=int.Parse(parts[2],CultureInfo.InvariantCulture),actionProfile=parts[3] };
            data=ListItem.Generate(Metrics.itemCount); Frames=new ListFrameMetrics[config.measureFrames];
            openedAt=ClockMs();
            View=ListLabFactory.Create(Metrics.virtualized,out root); View.SetItems(data,false);
            Canvas.ForceUpdateCanvases(); Metrics.coldBuildMs=ClockMs()-openedAt;
            preparedFrame=Time.frameCount;prepared=true;cleaned=false;
        }
        public void TickWarmup(int frameIndex) { View.SetPixelOffset(Triangle(frameIndex,600)*View.MaxOffset); }
        public void BeginMeasure()
        {
            View.SetPixelOffset(0); Canvas.ForceUpdateCanvases();
            Metrics.createdAtMeasureStart=View.Pool.Created; Metrics.destroyedAtMeasureStart=View.Pool.Destroyed;
            priorFirst=0;priorEnd=0;
        }
        public void TickMeasure(int frameIndex)
        {
            CheckPriorLayout();
            if (Metrics.actionProfile=="scroll") SetOffset(Triangle(frameIndex,600)*View.MaxOffset);
            else TickLifecycle(frameIndex);
            Capture(frameIndex);
        }
        public void EndMeasure() { CheckPriorLayout(); }
        private void TickLifecycle(int i)
        {
            if(i<300)SetOffset(0);
            else if(i<1200)SetOffset(Triangle(i-300,900)*View.MaxOffset);
            else if(i==1200)SetOffset(0);
            else if(i==1260)SetOffset(View.MaxOffset);
            else if(i==1320){SetOffset(View.MaxOffset*.4525f);saved=View.CapturePosition();}
            else if(i==1380){View.SetPixelOffset(0);View.RestorePosition(saved);expectedOffset=View.MaxOffset*.4525f;}
            else if(i==1440){View.SetItems(Array.Empty<ListItem>());expectedOffset=0;}
            else if(i==1500){View.SetItems(data,false);View.RestorePosition(saved);expectedOffset=View.MaxOffset*.4525f;}
            else if(i==1560)View.gameObject.SetActive(false);
            else if(i==1620)View.gameObject.SetActive(true);
        }
        private void SetOffset(float value) { expectedOffset=value;View.SetPixelOffset(value); }
        private void Capture(int index)
        {
            var pool=View.Pool; bool active=View.gameObject.activeInHierarchy;
            float offset=View.PixelOffset;
            int first=Mathf.Min(View.Count,Mathf.FloorToInt(offset/48));
            int end=Mathf.Min(View.Count,Mathf.CeilToInt((offset+384)/48));
            int visible=active?end-first:0;
            if(active)
            {
                for(int i=first;i<end;i++)
                {
                    if(!View.Cells.TryGetValue(i,out var cell)||!cell||!cell.gameObject.activeInHierarchy||cell.Index!=i||cell.ItemId!=data[i].Id||cell.Template!=0||!cell.IsBound)
                        failedReason="Visible item identity mismatch.";
                }
            }
            if(pool.UniqueTotal!=pool.Leased+pool.Cached || pool.UniqueTotal!=pool.Created-pool.Destroyed ||
                pool.Active!=pool.Leased || pool.Cached>16 ||
                (Metrics.virtualized&&(pool.Leased>13||pool.UniqueTotal>13))||(!Metrics.virtualized&&active&&pool.Leased!=View.Count)) failedReason="Ownership budget mismatch.";
            Metrics.maxPositionErrorPixels=Mathf.Max(Metrics.maxPositionErrorPixels,Mathf.Abs(offset-expectedOffset));
            Frames[index]=new ListFrameMetrics{Index=index,UnityFrame=Time.frameCount,Offset=offset,Visible=visible,
                Active=View.ActiveCount,Leased=pool.Leased,Cached=pool.Cached,Created=pool.Created,Destroyed=pool.Destroyed,
                Bind=pool.BindCount,Unbind=pool.UnbindCount};
            Metrics.sampleCount=index+1;priorFirst=active?first:0;priorEnd=active?end:0;
        }
        private void CheckPriorLayout()
        {
            if (!View) return;
            int observedVisible=0;
            for(int i=priorFirst;i<priorEnd;i++)
                if(View.Cells.TryGetValue(i,out var cell)&&cell)
                {
                    var rect=(RectTransform)cell.transform;
                    if(Mathf.Abs(rect.anchoredPosition.y+i*48)>.05f||Mathf.Abs(rect.rect.height-48)>.05f) failedReason="Rendered row layout mismatch.";
                    float top=-rect.anchoredPosition.y;
                    if(cell.gameObject.activeInHierarchy && top+rect.rect.height>View.PixelOffset && top<View.PixelOffset+View.Scroll.viewport.rect.height) observedVisible++;
                }
            if(Metrics.sampleCount>0)
            {
                int index=Metrics.sampleCount-1;
                if(observedVisible!=Frames[index].Visible) failedReason="Rendered visible intersection mismatch.";
                Frames[index].Visible=observedVisible;
            }
        }
        public BenchmarkCaseValidation Validate()
        {
            if(!View.ValidateState(out var reason))failedReason=reason;
            if(Metrics.maxPositionErrorPixels>.05f)failedReason="Position restore error exceeds tolerance.";
            if(Metrics.actionProfile=="scroll"&&(View.Pool.Created!=Metrics.createdAtMeasureStart||View.Pool.Destroyed!=Metrics.destroyedAtMeasureStart))
                failedReason="Steady scroll created or destroyed cells after warmup.";
            if(View.Pool.RejectedReturns!=0)failedReason="Unexpected rejected return.";
            CaptureFinal(); Metrics.correctness=failedReason==null?"pass":"fail";Metrics.reason=failedReason??"";
            return failedReason==null?BenchmarkCaseValidation.Pass():BenchmarkCaseValidation.Fail(failedReason);
        }
        private void CaptureFinal()
        {
            Metrics.finalCreated=View.Pool.Created;Metrics.finalDestroyed=View.Pool.Destroyed;Metrics.finalLeased=View.Pool.Leased;
            Metrics.finalCached=View.Pool.Cached;Metrics.finalUniqueTotal=View.Pool.UniqueTotal;Metrics.rejectedReturns=View.Pool.RejectedReturns;
        }
        public void Cleanup()
        {
            if(cleaned)return;cleaned=true;
            if(View)
            {
                CaptureFinal();root.SetActive(false);View.Pool.Dispose();Metrics.cleanupUniqueTotal=View.Pool.UniqueTotal;
                UnityEngine.Object.Destroy(root);
            }
            else if(Metrics!=null)Metrics.cleanupUniqueTotal=0;
        }
        public static float Triangle(int frame,int period)
        { int phase=frame%period;int half=period/2;return phase<=half?phase/(float)half:(period-1-phase)/(float)(period-1-half); }
        private static double ClockMs()=>System.Diagnostics.Stopwatch.GetTimestamp()*1000.0/System.Diagnostics.Stopwatch.Frequency;
    }
    public sealed class ListBenchmarkFactory : IBenchmarkCaseFactory
    {
        public ListBenchmarkCase Current { get; private set; }
        public IBenchmarkCase Create(BenchmarkRunConfig config) { Current=new ListBenchmarkCase();return Current; }
    }
}
