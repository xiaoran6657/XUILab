using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.Events;
using UnityEngine.TestTools;
using UnityEngine.UI;
using Object = UnityEngine.Object;

namespace XUILab.ListLab.Tests
{
    public class RefreshTraceTests
    {
        [Serializable] public class CellState
        {
            public int key, instance, index, template, binds, unbinds;
            public long id;
            public string label;
            public float top, height;
            public bool visible;
        }
        [Serializable] public class GraphicState
        {
            public int cell, index, installedIndex, vertexDirty, layoutDirty, meshCalls, vertices;
            public int[] vertexDirtyIndices, layoutDirtyIndices, meshIndices;
            public string kind;
        }
        [Serializable] public class Snapshot
        {
            public string phase;
            public int frame, binds, unbinds, created, destroyed, leased, cached, unique, canvasEvents;
            public float offset, velocity;
            public bool stateValid;
            public string stateReason;
            public CellState[] cells;
            public GraphicState[] graphics;
        }
        [Serializable] public class Trace
        {
            public string name, backend, mutation, replacementLabel, reentryLabel;
            public string layoutRebuild = "unavailable";
            public string canvasRebuild = "unavailable";
            public string cpu = "unavailable";
            public string newCellInitialDirty = "not_applicable";
            public int target, targetBinds, totalBinds, scannedCells, dataMutationOperations;
            public int[] visibleBefore, reboundIndices;
            public long anchorBefore, anchorAfter;
            public float movingStart, movingBeforeMutation;
            public bool targetVisible, targetRetained, reentryStale;
            public List<Snapshot> snapshots = new List<Snapshot>();
        }
        [Serializable] public class Report
        {
            public string schema = "xuilab.list.refresh-trace/v1";
            public string candidate = "list-refresh-trace-r1";
            public string utc, unity;
            public string measurement = "Editor diagnostic only; probes and snapshots are not performance-neutral";
            public string boundaries = "Immediate pool deltas isolate dispatch; following frame includes natural scroll/render. Canvas event is not a rebuild count. Mesh calls are no-op observer invocations.";
            public List<Trace> traces = new List<Trace>();
        }
        private sealed class Observer : IDisposable
        {
            public Graphic graphic;
            public RefreshMeshProbe probe;
            private ListCell boundCell;
            private readonly List<int> vertexIndices=new List<int>(), layoutIndices=new List<int>();
            public int cell, index, vertexDirty, layoutDirty;
            public string kind;
            private UnityAction vertex, layout;
            public Observer(Graphic g, ListCell c)
            {
                graphic = g; boundCell=c; cell = c.GetInstanceID(); index = c.Index; kind = g.GetType().Name;
                probe = g.gameObject.AddComponent<RefreshMeshProbe>();
                vertex = () => { vertexDirty++; vertexIndices.Add(boundCell?boundCell.Index:-1); };
                layout = () => { layoutDirty++; layoutIndices.Add(boundCell?boundCell.Index:-1); };
                g.RegisterDirtyVerticesCallback(vertex);
                g.RegisterDirtyLayoutCallback(layout);
            }
            public void Reset() { vertexDirty = layoutDirty = 0; vertexIndices.Clear(); layoutIndices.Clear(); if (probe) probe.ResetObservation(); }
            public GraphicState Read() => new GraphicState { cell=cell,index=boundCell?boundCell.Index:-1,installedIndex=index,kind=kind,vertexDirty=vertexDirty,
                layoutDirty=layoutDirty,meshCalls=probe?probe.Calls:0,vertices=probe?probe.LastVertices:-1,vertexDirtyIndices=vertexIndices.ToArray(),layoutDirtyIndices=layoutIndices.ToArray(),meshIndices=probe?probe.Indices.ToArray():new int[0] };
            public void Dispose()
            {
                if (graphic) { graphic.UnregisterDirtyVerticesCallback(vertex); graphic.UnregisterDirtyLayoutCallback(layout); }
                graphic = null; probe = null; boundCell=null; vertexIndices.Clear(); layoutIndices.Clear();
            }
        }
        private GameObject root;
        private readonly List<Observer> observers = new List<Observer>();
        private readonly HashSet<int> observedGraphics = new HashSet<int>();
        private int canvasEvents;
        private bool subscribed;
        private void CanvasEvent() { canvasEvents++; }
        private void Install(ListView view)
        {
            foreach (var pair in view.Cells)
                foreach (var g in pair.Value.GetComponentsInChildren<Graphic>())
                    if (observedGraphics.Add(g.GetInstanceID())) observers.Add(new Observer(g, pair.Value));
        }
        private Snapshot Capture(ListView view, string phase)
        {
            bool valid = view.ValidateState(out var reason);
            Assert.IsTrue(valid, reason);
            return new Snapshot
            {
                phase=phase,frame=Time.frameCount,offset=view.PixelOffset,velocity=view.Scroll.velocity.y,
                binds=view.Pool.BindCount,unbinds=view.Pool.UnbindCount,created=view.Pool.Created,
                destroyed=view.Pool.Destroyed,leased=view.Pool.Leased,cached=view.Pool.Cached,
                unique=view.Pool.UniqueTotal,canvasEvents=canvasEvents,stateValid=valid,stateReason=reason,
                cells=view.Cells.OrderBy(p=>p.Key).Select(p=>new CellState
                {
                    key=p.Key,instance=p.Value.GetInstanceID(),index=p.Value.Index,template=p.Value.Template,id=p.Value.ItemId,
                    label=p.Value.Label.text,binds=p.Value.BindCount,unbinds=p.Value.UnbindCount,
                    top=-((RectTransform)p.Value.transform).anchoredPosition.y,height=((RectTransform)p.Value.transform).rect.height,
                    visible=Visible(view,p.Key)
                }).ToArray(),
                graphics=observers.Where(o=>o.graphic).Select(o=>o.Read()).ToArray()
            };
        }
        private static bool Visible(ListView v,int i) => (i+1)*48 > v.PixelOffset && i*48 < v.PixelOffset+v.Scroll.viewport.rect.height;
        private void Unsubscribe()
        {
            if(subscribed) Canvas.willRenderCanvases-=CanvasEvent;
            subscribed=false;
            foreach(var o in observers) o.Dispose();
            observers.Clear(); observedGraphics.Clear();
        }
        [UnityTearDown] public IEnumerator Cleanup()
        {
            Unsubscribe();
            if(root) Object.Destroy(root);
            root=null;
            yield return null;
        }
        [UnityTest] public IEnumerator BaselineWindowRefreshTrace()
        {
            var report=new Report { utc=DateTime.UtcNow.ToString("O"), unity=Application.unityVersion };
            var cases=new[]{"middle","first_partial","last_partial","off_prefetch","off_far","moving","template","insert","delete"};
            foreach(bool virtualized in new[]{false,true})
            foreach(string name in cases)
            {
                var view=ListLabFactory.Create(virtualized,out root);
                var data=ListItem.Generate(1000,true);
                view.SetItems(data,false);
                view.SetPixelOffset(492);
                yield return null;
                Install(view);
                Canvas.ForceUpdateCanvases();
                yield return null;
                Canvas.ForceUpdateCanvases();
                var trace=new Trace {name=name,backend=virtualized?"virtual":"normal",dataMutationOperations=1};
                if(name=="moving")
                {
                    trace.movingStart=view.PixelOffset;
                    view.Scroll.velocity=new Vector2(0,120);
                    for(int f=0;f<8 && Mathf.Abs(view.PixelOffset-trace.movingStart)<.01f;f++) yield return null;
                    trace.movingBeforeMutation=view.PixelOffset;
                    Assert.Greater(Mathf.Abs(trace.movingBeforeMutation-trace.movingStart),.01f,"Natural ScrollRect must actually move.");
                }
                Install(view);
                Canvas.ForceUpdateCanvases();
                foreach(var o in observers) o.Reset();
                canvasEvents=0; Canvas.willRenderCanvases+=CanvasEvent; subscribed=true;
                var before=Capture(view,"before");
                trace.snapshots.Add(before);
                trace.visibleBefore=before.cells.Where(c=>c.visible).Select(c=>c.key).ToArray();
                int first=trace.visibleBefore.First(),last=trace.visibleBefore.Last();
                trace.target=name=="first_partial"?first:name=="last_partial"?last:name=="off_prefetch"?first-1:name=="off_far"?700:(first+last)/2;
                trace.scannedCells=before.cells.Length;
                trace.targetVisible=trace.visibleBefore.Contains(trace.target);
                trace.targetRetained=view.Cells.ContainsKey(trace.target);
                trace.anchorBefore=view.CapturePosition().ItemId;
                bool reset=name=="template" || name=="insert" || name=="delete";
                if(reset)
                {
                    trace.mutation="public SetItems reset";
                    trace.newCellInitialDirty="unavailable before observer registration";
                    var changed=data.ToList();
                    if(name=="template") changed[trace.target]=new ListItem(data[trace.target].Id,1-data[trace.target].Template,data[trace.target].Label);
                    if(name=="insert") changed.Insert(5,new ListItem(10001,0,data[5].Label));
                    if(name=="delete") changed.RemoveAt(5);
                    data=changed.ToArray();
                    view.SetItems(data);
                }
                else
                {
                    trace.mutation="reflection-only internal data replacement, then original RefreshItem";
                    var field=typeof(ListView).GetField("items",BindingFlags.Instance|BindingFlags.NonPublic);
                    Assert.NotNull(field); Assert.AreEqual(typeof(ListItem[]),field.FieldType);
                    var stored=(ListItem[])field.GetValue(view);
                    Assert.AreEqual(1000,stored.Length); Assert.AreNotSame(data,stored);
                    var item=stored[trace.target];
                    trace.replacementLabel=item.Label.Substring(0,item.Label.Length-1)+(item.Label.EndsWith("9")?"8":"9");
                    Assert.AreEqual(item.Label.Length,trace.replacementLabel.Length);
                    stored[trace.target]=new ListItem(item.Id,item.Template,trace.replacementLabel);
                    data[trace.target]=stored[trace.target];
                    view.RefreshItem(trace.target);
                }
                var immediate=Capture(view,"immediate_after_dispatch");
                trace.snapshots.Add(immediate);
                trace.totalBinds=immediate.binds-before.binds;
                trace.reboundIndices=immediate.cells.Where(c=>before.cells.Any(b=>b.instance==c.instance && c.binds>b.binds)).Select(c=>c.key).ToArray();
                trace.targetBinds=trace.reboundIndices.Contains(trace.target)?1:0;
                trace.anchorAfter=view.CapturePosition().ItemId;
                if(!reset)
                {
                    Assert.AreEqual(trace.visibleBefore.Length,trace.totalBinds);
                    CollectionAssert.AreEquivalent(trace.visibleBefore,trace.reboundIndices);
                    Assert.AreEqual(trace.targetVisible?1:0,trace.targetBinds);
                    Assert.AreEqual(before.created,immediate.created);
                    Assert.AreEqual(before.destroyed,immediate.destroyed);
                    Assert.AreEqual(before.unbinds+trace.totalBinds,immediate.unbinds);
                    foreach(var c in immediate.cells)
                    {
                        string expected=c.key==trace.target&&!trace.targetVisible ? before.cells.Single(b=>b.key==c.key).label : data[c.key].Label;
                        Assert.AreEqual(expected,c.label,"label at "+c.key);
                    }
                }
                else
                {
                    Assert.AreEqual(trace.anchorBefore,trace.anchorAfter,"Reset preserves stable anchor ID.");
                    Assert.AreEqual(view.Cells.Count,trace.totalBinds);
                    foreach(var c in immediate.cells) Assert.AreEqual(data[c.key].Label,c.label);
                }
                // New reset cells may already have been dirtied. Observe subsequent work only.
                Install(view);
                yield return null;
                trace.snapshots.Add(Capture(view,"after_natural_frame"));
                Canvas.ForceUpdateCanvases();
                trace.snapshots.Add(Capture(view,"after_explicit_canvas_flush"));
                foreach(var c in trace.snapshots.Last().cells)
                {
                    Assert.AreEqual(c.key*48,c.top,.05f);
                    Assert.AreEqual(48,c.height,.05f);
                }
                if(name=="off_prefetch" || name=="off_far")
                {
                    view.SetPixelOffset(trace.target*48+12);
                    yield return null;
                    Canvas.ForceUpdateCanvases();
                    var reentry=Capture(view,"after_target_reentry");
                    trace.snapshots.Add(reentry);
                    trace.reentryLabel=view.Cells[trace.target].Label.text;
                    trace.reentryStale=trace.reentryLabel!=trace.replacementLabel;
                    Assert.AreEqual(name=="off_prefetch" || !virtualized,trace.reentryStale,"Record retained-cell baseline stale label gap.");
                }
                report.traces.Add(trace);
                Unsubscribe();
                var pool=view.Pool;
                Object.Destroy(root);root=null;yield return null;
                Assert.AreEqual(0,pool.UniqueTotal);
                Assert.AreEqual(pool.Created,pool.Destroyed);
            }
            Assert.AreEqual(18,report.traces.Count);
            string directory=Path.GetFullPath(Path.Combine(Application.dataPath,"../../Artifacts/list-refresh-trace-r1"));
            Directory.CreateDirectory(directory);
            string output=Path.Combine(directory,"trace.json");
            Assert.IsFalse(File.Exists(output),"Never overwrite a previous diagnostic.");
            File.WriteAllText(output,JsonUtility.ToJson(report,true));
        }
    }
}

