using System;
using UnityEngine;
using XUILab.Benchmarking;

namespace XUILab.ListLab
{
    [Serializable] public sealed class ListRefreshMetrics
    {
        public string schemaVersion="xuilab.list-refresh.metrics/v1";
        public string runId,caseId,backend,policy,profile;
        public string correctness="not_run",reason="";
        public string uiRebuild="unavailable";
        public string uiRebuildReason="No validated Player UI marker; independent PlayMode dirty/mesh diagnostics are separate.";
        public int itemCount=1000,visibleCount=9,initialMask,bindAtStart,unbindAtStart,createdAtStart,destroyedAtStart;
        public int sampleCount,finalBind,finalUnbind,finalCreated,finalDestroyed,finalLeased,finalCached,cleanupUnique=-1;
        public double coldBuildMs;
    }
    public struct ListRefreshFrame
    {
        public int Index,ActionFrame,SettledFrame,Updates,TargetMask,StateMask,Bind,Unbind,Created,Destroyed,Leased,Cached,Pending,Visible;
        public uint LabelChecksum;
        public float Offset;
    }
    public sealed class ListRefreshBenchmarkCase : IBenchmarkCase
    {
        public string Id {get;private set;}
        public ListView View {get;private set;}
        public ListRefreshMetrics Metrics {get;private set;}
        public ListRefreshFrame[] Frames {get;private set;}
        private GameObject root;
        private ListItem[] data;
        private readonly ListItem[,] variants=new ListItem[9,2];
        private readonly int[] states=new int[9];
        private readonly ListItemUpdate[] batch=new ListItemUpdate[9];
        private int preparedFrame;
        private bool cleaned;
        private string failure;
        public bool IsReady => View && !cleaned && Time.frameCount>preparedFrame;
        public void Prepare(BenchmarkRunConfig config)
        {
            if(!BenchmarkRunConfig.IsListRefreshCaseId(config.caseId)||config.caseVersion!="1")throw new ArgumentException("Unsupported refresh case.");
            Id=config.caseId;var parts=Id.Split('-');
            Metrics=new ListRefreshMetrics{runId=config.runId,caseId=Id,backend=parts[1],policy=parts[3],profile=parts[4]};
            Frames=new ListRefreshFrame[config.measureFrames];data=ListItem.Generate(1000,true);
            for(int slot=0;slot<9;slot++)
            {
                var item=data[slot+10];string prefix=item.Label.Substring(0,item.Label.Length-1);
                variants[slot,0]=new ListItem(item.Id,item.Template,prefix+"0");
                variants[slot,1]=new ListItem(item.Id,item.Template,prefix+"1");
                data[slot+10]=variants[slot,0];
            }
            double start=ClockMs();
            View=ListLabFactory.Create(parts[1]=="virtual",out root);
            View.RefreshPolicy=parts[3]=="target"?ListRefreshPolicy.TargetOnly:ListRefreshPolicy.VisibleWindow;
            View.SetItems(data,false);View.SetPixelOffset(492);Canvas.ForceUpdateCanvases();
            Metrics.coldBuildMs=ClockMs()-start;preparedFrame=Time.frameCount;
        }
        public void TickWarmup(int frameIndex) { Apply(frameIndex,out _); }
        public void BeginMeasure()
        {
            Metrics.initialMask=StateMask();Metrics.bindAtStart=View.Pool.BindCount;Metrics.unbindAtStart=View.Pool.UnbindCount;
            Metrics.createdAtStart=View.Pool.Created;Metrics.destroyedAtStart=View.Pool.Destroyed;
        }
        private int Apply(int frame,out int targets)
        {
            targets=0;
            if(Metrics.profile=="idle" || ((Metrics.profile=="sparse"||Metrics.profile=="burst")&&frame%60!=0))return 0;
            int count=Metrics.profile=="burst"?3:Metrics.profile=="batch"?9:1;
            for(int n=0;n<count;n++)
            {
                int slot=(frame+n)%9;states[slot]=1-states[slot];data[slot+10]=variants[slot,states[slot]];
                targets|=1<<slot;
                if(Metrics.profile=="batch")batch[n]=new ListItemUpdate(slot+10,data[slot+10]);
                else View.UpdateItem(slot+10,data[slot+10]);
            }
            if(Metrics.profile=="batch")View.UpdateItems(batch);
            return count;
        }
        public void TickMeasure(int frameIndex)
        {
            CheckSettled();
            int updates=Apply(frameIndex,out int targets);
            uint checksum=ChecksumAndCheck();
            var pool=View.Pool;
            if(pool.Created!=Metrics.createdAtStart||pool.Destroyed!=Metrics.destroyedAtStart||View.PendingRefreshCount!=0)failure="Static refresh unexpectedly changed ownership or left pending data.";
            Frames[frameIndex]=new ListRefreshFrame{Index=frameIndex,ActionFrame=Time.frameCount,SettledFrame=-1,
                Updates=updates,TargetMask=targets,StateMask=StateMask(),LabelChecksum=checksum,Bind=pool.BindCount,Unbind=pool.UnbindCount,
                Created=pool.Created,Destroyed=pool.Destroyed,Leased=pool.Leased,Cached=pool.Cached,Pending=View.PendingRefreshCount,
                Offset=View.PixelOffset,Visible=0};
            Metrics.sampleCount=frameIndex+1;
        }
        private int StateMask()
        {
            int mask=0;for(int i=0;i<9;i++)mask|=states[i]<<i;return mask;
        }
        private uint ChecksumAndCheck()
        {
            uint hash=2166136261;
            for(int index=10;index<=18;index++)
            {
                if(!View.Cells.TryGetValue(index,out var cell)||!cell||!cell.IsBound||cell.Index!=index||cell.ItemId!=data[index].Id||
                   cell.Template!=data[index].Template||cell.Label.text!=data[index].Label||!cell.gameObject.activeInHierarchy)
                {failure="Visible content/identity mismatch.";continue;}
                string label=cell.Label.text;
                for(int j=0;j<label.Length;j++)unchecked{hash=(hash^label[j])*16777619;}
            }
            return hash;
        }
        private void CheckSettled()
        {
            if(Metrics.sampleCount==0)return;
            int index=Metrics.sampleCount-1;var frame=Frames[index];int visible=0;
            for(int i=10;i<=18;i++)
            {
                if(!View.Cells.TryGetValue(i,out var cell)||!cell){failure="Settled cell missing.";continue;}
                var rect=(RectTransform)cell.transform;
                if(Mathf.Abs(-rect.anchoredPosition.y-i*48)>.05f||Mathf.Abs(rect.rect.height-48)>.05f)failure="Settled geometry mismatch.";
                float top=-rect.anchoredPosition.y;
                if(top+rect.rect.height>View.PixelOffset&&top<View.PixelOffset+View.Scroll.viewport.rect.height)visible++;
            }
            if(visible!=9||Mathf.Abs(View.PixelOffset-492)>.05f)failure="Visible window changed.";
            frame.SettledFrame=Time.frameCount;frame.Visible=visible;Frames[index]=frame;
        }
        public void EndMeasure(){CheckSettled();}
        public BenchmarkCaseValidation Validate()
        {
            if(!View.ValidateState(out var reason))failure=reason;
            int expected=Metrics.backend=="virtual"?13:1000;
            if(View.Pool.Leased!=expected||View.Pool.Active!=expected||View.Pool.RejectedReturns!=0)failure="Pool/window mismatch.";
            CaptureFinal();Metrics.correctness=failure==null?"pass":"fail";Metrics.reason=failure??"";
            return failure==null?BenchmarkCaseValidation.Pass():BenchmarkCaseValidation.Fail(failure);
        }
        private void CaptureFinal()
        {
            var p=View.Pool;Metrics.finalBind=p.BindCount;Metrics.finalUnbind=p.UnbindCount;Metrics.finalCreated=p.Created;
            Metrics.finalDestroyed=p.Destroyed;Metrics.finalLeased=p.Leased;Metrics.finalCached=p.Cached;
        }
        public void Cleanup()
        {
            if(cleaned)return;cleaned=true;
            if(View)
            {
                CaptureFinal();root.SetActive(false);View.Pool.Dispose();Metrics.cleanupUnique=View.Pool.UniqueTotal;
                UnityEngine.Object.Destroy(root);
            }
            else if(Metrics!=null)Metrics.cleanupUnique=0;
        }
        private static double ClockMs()=>System.Diagnostics.Stopwatch.GetTimestamp()*1000.0/System.Diagnostics.Stopwatch.Frequency;
    }
    public sealed class ListRefreshBenchmarkFactory : IBenchmarkCaseFactory
    {
        public ListRefreshBenchmarkCase Current {get;private set;}
        public IBenchmarkCase Create(BenchmarkRunConfig config){Current=new ListRefreshBenchmarkCase();return Current;}
    }
}
