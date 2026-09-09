using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.Events;
using UnityEngine.TestTools;
using Object = UnityEngine.Object;

namespace XUILab.ListLab.Tests
{
    public class RefreshUpdateTests
    {
        private GameObject root;
        private static readonly ListRefreshPolicy[] Policies = { ListRefreshPolicy.VisibleWindow, ListRefreshPolicy.TargetOnly };
        private ListView Create(bool virtualized,ListRefreshPolicy policy)
        {
            var view=ListLabFactory.Create(virtualized,out root);
            view.RefreshPolicy=policy;view.SetItems(ListItem.Generate(1000,true),false);view.SetPixelOffset(492);
            return view;
        }
        private static ListItem Change(ListView view,int index,bool template=false,string suffix="9")
        {
            var old=view.GetItem(index);
            return new ListItem(old.Id,template?1-old.Template:old.Template,old.Label.Substring(0,old.Label.Length-1)+suffix);
        }
        private static void Valid(ListView view)
        {
            Assert.IsTrue(view.ValidateState(out var reason),reason);
            foreach(var pair in view.Cells)
                if((pair.Key+1)*48>view.PixelOffset && pair.Key*48<view.PixelOffset+view.Scroll.viewport.rect.height)
                {
                    Assert.AreEqual(view.GetItem(pair.Key).Label,pair.Value.Label.text);
                    Assert.AreEqual(view.GetItem(pair.Key).Template,pair.Value.Template);
                }
        }
        private IEnumerator DestroyView(ListView view)
        {
            var pool=view.Pool;Object.Destroy(root);root=null;yield return null;
            Assert.AreEqual(0,pool.UniqueTotal);Assert.AreEqual(pool.Created,pool.Destroyed);
        }
        [UnityTearDown] public IEnumerator Cleanup()
        {
            if(root)Object.Destroy(root);root=null;yield return null;
        }
        [UnityTest] public IEnumerator VisibleAndOffscreenTemplateUpdates()
        {
            foreach(bool virtualized in new[]{false,true})
            foreach(var policy in Policies)
            foreach(bool template in new[]{false,true})
            {
                var view=Create(virtualized,policy);yield return null;
                foreach(int index in new[]{14,10,18,9,700})
                {
                    view.SetItems(ListItem.Generate(1000,true),false);view.SetPixelOffset(492);
                    yield return null;
                    bool visible=index>=10&&index<=18;
                    int binds=view.Pool.BindCount,created=view.Pool.Created;
                    var oldCell=view.Cells.TryGetValue(index,out var retained)?retained:null;
                    var update=Change(view,index,template);
                    view.UpdateItem(index,update);
                    int expected=policy==ListRefreshPolicy.VisibleWindow?9:visible?1:0;
                    Assert.AreEqual(expected,view.Pool.BindCount-binds);
                    Assert.AreEqual(visible?0:1,view.PendingRefreshCount);
                    Assert.AreSame(update,view.GetItem(index));
                    if(!visible)
                    {
                        Assert.AreEqual(created,view.Pool.Created);
                        if(oldCell)Assert.AreSame(oldCell,view.Cells[index]);
                    }
                    Valid(view);yield return null;Valid(view);
                    if(!visible)
                    {
                        var before=root.GetComponentsInChildren<ListCell>(true).ToDictionary(c=>c.GetInstanceID(),c=>c.BindCount);
                        view.SetPixelOffset(index*48+12);yield return null;
                        var current=view.Cells[index];
                        int previous=before.TryGetValue(current.GetInstanceID(),out var oldBinds)?oldBinds:0;
                        Assert.AreEqual(1,current.BindCount-previous);
                        Assert.AreEqual(0,view.PendingRefreshCount);
                        Assert.AreEqual(update.Label,current.Label.text);Assert.AreEqual(update.Template,current.Template);
                    }
                    Valid(view);
                    TestContext.WriteLine($"{virtualized}/{policy}/template={template}/index={index}: dispatchBind={expected}; latest visible; valid");
                }
                yield return DestroyView(view);
            }
        }
        [UnityTest] public IEnumerator InvalidUpdatesAreAtomicAndBatchHasOneDispatch()
        {
            foreach(bool virtualized in new[]{false,true})
            foreach(var policy in Policies)
            {
                var view=Create(virtualized,policy);yield return null;
                var original=view.GetItem(14);int bind=view.Pool.BindCount;
                Assert.Throws<ArgumentOutOfRangeException>(()=>view.UpdateItem(-1,original));
                Assert.Throws<ArgumentOutOfRangeException>(()=>view.UpdateItem(1000,original));
                Assert.Throws<ArgumentNullException>(()=>view.UpdateItem(14,null));
                Assert.Throws<ArgumentException>(()=>view.UpdateItem(14,new ListItem(4000,0,"changed")));
                Assert.Throws<ArgumentException>(()=>view.UpdateItems(new[]{new ListItemUpdate(14,Change(view,14)),new ListItemUpdate(15,original)}));
                Assert.Throws<ArgumentException>(()=>view.UpdateItems(new[]{new ListItemUpdate(14,Change(view,14)),new ListItemUpdate(14,Change(view,14))}));
                Assert.Throws<ArgumentNullException>(()=>view.UpdateItems(null));
                Assert.AreSame(original,view.GetItem(14));Assert.AreEqual(bind,view.Pool.BindCount);Assert.AreEqual(0,view.PendingRefreshCount);
                view.UpdateItem(14,new ListItem(original.Id,original.Template,original.Label));
                Assert.AreEqual(bind,view.Pool.BindCount,"Frozen no-op semantics apply equally to both policies.");
                var updates=new[]{new ListItemUpdate(14,Change(view,14)),new ListItemUpdate(15,Change(view,15)),new ListItemUpdate(700,Change(view,700))};
                view.UpdateItems(updates);
                Assert.AreEqual(policy==ListRefreshPolicy.VisibleWindow?9:2,view.Pool.BindCount-bind);
                Assert.AreEqual(1,view.PendingRefreshCount);Valid(view);
                view.SetPixelOffset(700*48+12);yield return null;Valid(view);Assert.AreEqual(0,view.PendingRefreshCount);
                yield return DestroyView(view);
            }
        }
        [UnityTest] public IEnumerator PendingUpdatesSurviveScrollResizeDisableAndDestruction()
        {
            foreach(bool virtualized in new[]{false,true})
            foreach(var policy in Policies)
            {
                var view=Create(virtualized,policy);yield return null;
                view.UpdateItem(19,Change(view,19,true,"8"));
                var final=Change(view,19,false,"7");view.UpdateItem(19,final);
                Assert.AreEqual(1,view.PendingRefreshCount);
                ((RectTransform)view.Scroll.transform).SetSizeWithCurrentAnchors(RectTransform.Axis.Vertical,480);
                yield return null;yield return null;
                Valid(view);Assert.AreEqual(final.Label,view.Cells[19].Label.text);Assert.AreEqual(0,view.PendingRefreshCount);
                ((RectTransform)view.Scroll.transform).SetSizeWithCurrentAnchors(RectTransform.Axis.Vertical,384);
                view.SetPixelOffset(492);yield return null;
                view.UpdateItem(19,Change(view,19,false,"6"));
                float initial=view.PixelOffset;view.Scroll.velocity=new Vector2(0,1800);
                for(int i=0;i<60 && view.PendingRefreshCount>0;i++)yield return null;
                Assert.Greater(view.PixelOffset,initial+.01f);Assert.AreEqual(0,view.PendingRefreshCount);Valid(view);
                view.Scroll.StopMovement();
                view.UpdateItem(700,Change(view,700,true,"5"));
                view.gameObject.SetActive(false);Assert.AreEqual(0,view.Pool.Leased);
                var disabled=Change(view,14,true,"4");int bind=view.Pool.BindCount;
                view.UpdateItem(14,disabled);Assert.AreEqual(bind,view.Pool.BindCount);
                view.gameObject.SetActive(true);yield return null;Valid(view);
                view.SetPixelOffset(14*48+12);yield return null;Valid(view);
                Assert.AreEqual(disabled.Label,view.Cells[14].Label.text);
                Object.Destroy(view.Cells[14].gameObject);yield return null;
                view.SetPixelOffset(view.PixelOffset);yield return null;Valid(view);
                Assert.AreEqual(disabled.Label,view.Cells[14].Label.text);
                view.SetPixelOffset(700*48+12);yield return null;Valid(view);
                Assert.AreEqual(view.GetItem(700).Template,view.Cells[700].Template);
                yield return DestroyView(view);
            }
        }
        [UnityTest] public IEnumerator ResetClearsPendingAndPreservesStableAnchor()
        {
            foreach(bool virtualized in new[]{false,true})
            foreach(var policy in Policies)
            {
                var view=Create(virtualized,policy);yield return null;
                foreach(string op in new[]{"insert","delete","reorder","empty"})
                {
                    view.SetItems(ListItem.Generate(1000,true),false);view.SetPixelOffset(492);yield return null;
                    view.UpdateItem(700,Change(view,700,true));
                    var anchor=view.CapturePosition();int pending=view.PendingRefreshCount,bind=view.Pool.BindCount;
                    Assert.Throws<ArgumentException>(()=>view.SetItems(new[]{view.GetItem(0),view.GetItem(0)}));
                    Assert.AreEqual(pending,view.PendingRefreshCount);Assert.AreEqual(bind,view.Pool.BindCount);
                    var data=ListItem.Generate(1000,true).ToList();
                    if(op=="insert")data.Insert(5,new ListItem(10001,0,"inserted"));
                    if(op=="delete")data.RemoveAt(5);
                    if(op=="reorder"){var temp=data[10];data[10]=data[100];data[100]=temp;}
                    if(op=="empty")data.Clear();
                    view.SetItems(data);yield return null;Valid(view);Assert.AreEqual(0,view.PendingRefreshCount);
                    if(op!="empty")Assert.AreEqual(anchor.ItemId,view.CapturePosition().ItemId);
                    else {Assert.AreEqual(0,view.Count);view.SetItems(ListItem.Generate(1000,true),false);yield return null;Valid(view);}
                }
                yield return DestroyView(view);
            }
        }
        [UnityTest] public IEnumerator NestedMutationsAreRejectedAndGuardRecovers()
        {
            var view=Create(true,ListRefreshPolicy.TargetOnly);yield return null;
            int callbacks=0;
            UnityAction nested=()=>
            {
                callbacks++;
                Assert.Throws<InvalidOperationException>(()=>view.UpdateItem(14,Change(view,14)));
                Assert.Throws<InvalidOperationException>(()=>view.UpdateItems(new ListItemUpdate[0]));
                Assert.Throws<InvalidOperationException>(()=>view.SetItems(ListItem.Generate(10)));
                Assert.Throws<InvalidOperationException>(()=>view.RefreshItem(14));
                Assert.Throws<InvalidOperationException>(()=>view.SetPixelOffset(0));
                Assert.Throws<InvalidOperationException>(()=>view.RestorePosition(default(ListPosition)));
                Assert.Throws<InvalidOperationException>(()=>view.UpdateEffects());
                Assert.Throws<InvalidOperationException>(()=>view.RefreshPolicy=ListRefreshPolicy.VisibleWindow);
            };
            var text=view.Cells[14].Label;text.RegisterDirtyVerticesCallback(nested);
            try {view.UpdateItem(14,Change(view,14,false,"8"));}
            finally {text.UnregisterDirtyVerticesCallback(nested);}
            Assert.Greater(callbacks,0);Valid(view);
            view.UpdateItem(14,Change(view,14,false,"7"));Valid(view);
            yield return DestroyView(view);
        }
        [UnityTest] public IEnumerator ThrowingBindCallbacksLeaveNoOrphanLeaseAndCanRecover()
        {
            foreach(bool template in new[]{false,true})
            {
                var view=Create(true,ListRefreshPolicy.TargetOnly);yield return null;
                ListCell observed=view.Cells[14];
                if(template)
                {
                    observed=view.Pool.Rent(1,view.Scroll.content);
                    view.Pool.Bind(observed,new ListItem(5001,1,"cached"),500,false);
                    view.Pool.Return(observed);
                }
                var text=observed.Label;
                var injected=new InvalidOperationException("injected dirty callback");
                UnityAction crash=()=>throw injected;
                text.RegisterDirtyVerticesCallback(crash);
                var replacement=Change(view,14,template,"8");
                try
                {
                    // Unity logs OnEnable exceptions independently of the direct Bind exception.
                    if(template)LogAssert.Expect(LogType.Exception,"InvalidOperationException: injected dirty callback");
                    Assert.AreSame(injected,Assert.Throws<InvalidOperationException>(()=>view.UpdateItem(14,replacement)));
                    Assert.AreSame(replacement,view.GetItem(14),"Publication is committed; dispatch failure is not input rejection.");
                    Assert.IsFalse(view.Cells.ContainsKey(14));
                    Assert.IsTrue(view.Pool.ValidateOwnership(out var reason),reason);
                    Assert.IsFalse(view.ValidateState(out _),"Failed dispatch must not report a ready/valid window.");
                }
                finally{text.UnregisterDirtyVerticesCallback(crash);}
                view.UpdateEffects();yield return null;Valid(view);
                Assert.AreEqual(replacement.Label,view.Cells[14].Label.text);
                Assert.AreEqual(replacement.Template,view.Cells[14].Template);
                Assert.AreEqual(0,view.PendingRefreshCount);
                yield return DestroyView(view);
            }
        }
        [UnityTest] public IEnumerator BatchDispatchFailurePreservesPublishedDataAndExplicitRecovery()
        {
            var view=Create(true,ListRefreshPolicy.TargetOnly);yield return null;
            var updates=new[]{new ListItemUpdate(14,Change(view,14,false,"8")),new ListItemUpdate(15,Change(view,15,false,"8")),new ListItemUpdate(16,Change(view,16,false,"8"))};
            var text=view.Cells[15].Label;UnityAction crash=()=>throw new InvalidOperationException("batch callback");
            text.RegisterDirtyVerticesCallback(crash);
            try
            {
                Assert.Throws<InvalidOperationException>(()=>view.UpdateItems(updates));
                foreach(var update in updates)Assert.AreSame(update.Item,view.GetItem(update.Index));
                Assert.IsFalse(view.Cells.ContainsKey(15));
                Assert.IsTrue(view.Pool.ValidateOwnership(out var reason),reason);
                Assert.IsFalse(view.ValidateState(out _));Assert.AreEqual(2,view.PendingRefreshCount);
            }
            finally{text.UnregisterDirtyVerticesCallback(crash);}
            view.UpdateEffects();yield return null;Valid(view);Assert.AreEqual(0,view.PendingRefreshCount);
            yield return DestroyView(view);
        }
        [UnityTest] public IEnumerator DeferredScrollAndLifecycleReachFinalState()
        {
            var view=Create(true,ListRefreshPolicy.TargetOnly);yield return null;
            var first=view.Cells[14].Label;var returned=view.Cells[8].Label;
            bool moved=false,disabled=false;
            UnityAction move=()=>
            {
                if(moved)return;moved=true;
                view.gameObject.SetActive(false);view.gameObject.SetActive(true);
                view.Scroll.content.anchoredPosition=new Vector2(0,540);
                view.Scroll.onValueChanged.Invoke(Vector2.zero);
            };
            UnityAction disable=()=>
            {
                if(disabled)return;disabled=true;view.gameObject.SetActive(false);
            };
            first.RegisterDirtyVerticesCallback(move);returned.RegisterDirtyVerticesCallback(disable);
            try {view.UpdateItem(14,Change(view,14,false,"8"));}
            finally{first.UnregisterDirtyVerticesCallback(move);returned.UnregisterDirtyVerticesCallback(disable);}
            Assert.IsTrue(moved);Assert.IsTrue(disabled);Assert.IsFalse(view.gameObject.activeSelf);
            Assert.AreEqual(0,view.Pool.Leased);Valid(view);
            view.gameObject.SetActive(true);yield return null;Valid(view);
            // A direct ScrollRect event during a callback also needs one deferred reconciliation.
            first=view.Cells[14].Label;
            UnityAction jump=()=>
            {
                view.Scroll.content.anchoredPosition=new Vector2(0,2500);
                view.Scroll.onValueChanged.Invoke(Vector2.zero);
            };
            first.RegisterDirtyVerticesCallback(jump);
            try{view.UpdateItem(14,Change(view,14,false,"7"));}
            finally{first.UnregisterDirtyVerticesCallback(jump);}
            yield return null;Valid(view);Assert.Greater(view.PixelOffset,2400);
            yield return DestroyView(view);
        }
        [UnityTest] public IEnumerator ReleaseAllContinuesAfterEveryUnbindFailure()
        {
            var view=Create(true,ListRefreshPolicy.TargetOnly);yield return null;
            var texts=view.Cells.Values.Select(c=>c.Label).ToArray();
            var firstError=new InvalidOperationException("first unbind");int callbacks=0;
            UnityAction crash=()=>{callbacks++;throw firstError;};
            foreach(var text in texts)text.RegisterDirtyVerticesCallback(crash);
            try
            {
                Assert.AreSame(firstError,Assert.Throws<InvalidOperationException>(()=>view.SetItems(ListItem.Generate(12))));
                Assert.AreEqual(texts.Length,callbacks,"Every lease is cleaned even after earlier callbacks fail.");
                Assert.AreEqual(0,view.Cells.Count);Assert.AreEqual(0,view.Pool.Leased);
                Assert.IsTrue(view.Pool.ValidateOwnership(out var reason),reason);
                Assert.IsFalse(view.ValidateState(out _));
            }
            finally{foreach(var text in texts)if(text)text.UnregisterDirtyVerticesCallback(crash);}
            view.SetItems(ListItem.Generate(1000,true),false);yield return null;Valid(view);
            yield return DestroyView(view);
        }
        [UnityTest] public IEnumerator PrimaryDispatchErrorSurvivesDeferredDisabledCleanupFailure()
        {
            var view=Create(true,ListRefreshPolicy.TargetOnly);yield return null;
            var primaryText=view.Cells[14].Label;var secondaryText=view.Cells[15].Label;
            var primary=new InvalidOperationException("primary dispatch");var secondary=new InvalidOperationException("secondary cleanup");
            int secondaryCalls=0;
            UnityAction fail=()=>{view.enabled=false;throw primary;};
            UnityAction cleanupFail=()=>{secondaryCalls++;throw secondary;};
            primaryText.RegisterDirtyVerticesCallback(fail);secondaryText.RegisterDirtyVerticesCallback(cleanupFail);
            try
            {
                Assert.AreSame(primary,Assert.Throws<InvalidOperationException>(()=>view.UpdateItem(14,Change(view,14))));
                Assert.AreEqual(1,secondaryCalls);Assert.AreEqual(0,view.Pool.Leased);Assert.AreEqual(0,view.Cells.Count);
                Assert.IsTrue(view.Pool.ValidateOwnership(out var reason),reason);Assert.IsFalse(view.ValidateState(out _));
            }
            finally{primaryText.UnregisterDirtyVerticesCallback(fail);secondaryText.UnregisterDirtyVerticesCallback(cleanupFail);}
            view.enabled=true;view.UpdateEffects();yield return null;Valid(view);
            yield return DestroyView(view);
        }
        [UnityTest] public IEnumerator DirtyAndMeshFollowSelectedCells()
        {
            foreach(var policy in Policies)
            {
                var view=Create(true,policy);yield return null;
                var texts=view.Cells.Where(p=>p.Key>=10&&p.Key<=18).Select(p=>p.Value.Label).ToArray();
                var probes=texts.Select(t=>t.gameObject.AddComponent<RefreshMeshProbe>()).ToArray();
                Canvas.ForceUpdateCanvases();yield return null;Canvas.ForceUpdateCanvases();
                foreach(var probe in probes)probe.ResetObservation();
                int vertices=0,layouts=0;
                UnityAction vd=()=>vertices++,ld=()=>layouts++;
                foreach(var text in texts){text.RegisterDirtyVerticesCallback(vd);text.RegisterDirtyLayoutCallback(ld);}
                try
                {
                    int bind=view.Pool.BindCount;
                    view.UpdateItem(14,Change(view,14,false,"8"));
                    int expected=policy==ListRefreshPolicy.TargetOnly?1:9;
                    Assert.AreEqual(expected,view.Pool.BindCount-bind);
                    Assert.AreEqual(expected*2,vertices);Assert.AreEqual(expected,layouts);
                    yield return null;Canvas.ForceUpdateCanvases();
                    Assert.AreEqual(expected,probes.Sum(p=>p.Calls));
                    Valid(view);
                }
                finally {foreach(var text in texts)if(text){text.UnregisterDirtyVerticesCallback(vd);text.UnregisterDirtyLayoutCallback(ld);}}
                yield return DestroyView(view);
            }
        }
    }
}
