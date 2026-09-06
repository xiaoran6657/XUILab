using System.Collections;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.TestTools;
using UnityEngine.UI;

namespace XUILab.ListLab.Tests
{
    public class ListViewTests
    {
        private GameObject root;
        [UnityTest] public IEnumerator ActualActivityDetectsDisabledLeasedCell()
        {
            var view=ListLabFactory.Create(true,out root);view.SetItems(ListItem.Generate(100));yield return null;
            int before=view.ActiveCount;
            view.Cells[0].gameObject.SetActive(false);
            Assert.AreEqual(before-1,view.ActiveCount);
            Assert.False(view.ValidateState(out _));
            view.Cells[0].gameObject.SetActive(true);
            Assert.AreEqual(before,view.ActiveCount);
            Assert.True(view.ValidateState(out var reason),reason);
        }
        [UnityTearDown] public IEnumerator Cleanup() { if(root) Object.Destroy(root); yield return null; }
        [UnityTest] public IEnumerator BothBackendsHaveMatchingContentAndLayout()
        {
            foreach(bool virtualized in new[]{false,true})
            {
                var view=ListLabFactory.Create(virtualized,out root); view.SetItems(ListItem.Generate(100)); yield return null;
                foreach(float offset in new[]{0f,485.25f,100000f})
                {
                    view.SetPixelOffset(offset); Canvas.ForceUpdateCanvases(); yield return null;
                    Assert.True(view.ValidateState(out var reason),reason); Assert.LessOrEqual(view.VisibleCount,9);
                    foreach(var pair in view.Cells)
                    {
                        var rect=(RectTransform)pair.Value.transform;
                        Assert.AreEqual(pair.Key*48,-rect.anchoredPosition.y, .05f);
                        Assert.AreEqual(48,rect.rect.height,.05f);
                    }
                }
                Assert.AreEqual(virtualized?10:100,view.Pool.Leased);
                Object.Destroy(root); yield return null; root=null;
            }
        }
        [UnityTest] public IEnumerator VirtualWindowStabilizesAndReopenDoesNotLeak()
        {
            var view=ListLabFactory.Create(true,out root);view.SetItems(ListItem.Generate(1000));yield return null;
            for(int i=0;i<200;i++) view.SetPixelOffset(500+i*5.25f);
            int created=view.Pool.Created;
            for(int round=0;round<10;round++)
            {
                for(int i=0;i<100;i++)view.SetPixelOffset(800+i*7.25f);
                Assert.True(view.ValidateState(out var reason),reason);
                view.gameObject.SetActive(false);Assert.AreEqual(0,view.Pool.Leased);
                view.gameObject.SetActive(true);
            }
            Assert.AreEqual(created,view.Pool.Created);Assert.LessOrEqual(created,13);Assert.AreEqual(0,view.Pool.Destroyed);
        }
        [UnityTest] public IEnumerator RestoreHandlesReorderRemovalShrinkAndEmpty()
        {
            var view=ListLabFactory.Create(true,out root);var data=ListItem.Generate(100);view.SetItems(data);yield return null;
            view.SetPixelOffset(20*48+7.125f);var saved=view.CapturePosition();
            view.SetItems(data);Assert.AreEqual(967.125f,view.PixelOffset,.05f);
            var reordered=(ListItem[])data.Clone();var temp=reordered[20];reordered[20]=reordered[10];reordered[10]=temp;
            view.SetItems(reordered);Assert.AreEqual(487.125f,view.PixelOffset,.05f);
            view.SetItems(ListItem.Generate(10));Assert.AreEqual(96,view.PixelOffset,.05f);
            view.SetItems(new ListItem[0]);Assert.AreEqual(0,view.Pool.Leased);Assert.AreEqual(0,view.PixelOffset);
            view.SetItems(data);view.Scroll.velocity=new Vector2(0,200);view.RestorePosition(saved);Assert.AreEqual(Vector2.zero,view.Scroll.velocity);
            Assert.AreEqual(967.125f,view.PixelOffset,.05f);
        }
        [UnityTest] public IEnumerator RebindResetsWrapperAndRoutesTemplates()
        {
            var view=ListLabFactory.Create(true,out root);view.SetItems(ListItem.Generate(100,true));yield return null;
            var cell=view.Cells[0];cell.Wrapper.localScale=Vector3.one*2;cell.Wrapper.anchoredPosition=Vector2.one*60;cell.Group.alpha=.1f;
            view.SetItems(new ListItem[0]);Assert.AreEqual(Vector3.one,cell.Wrapper.localScale);Assert.AreEqual(Vector2.zero,cell.Wrapper.anchoredPosition);Assert.AreEqual(1,cell.Group.alpha);
            view.SetItems(ListItem.Generate(100,true));
            for(int i=0;i<20;i++){view.SetPixelOffset(i*150);Assert.True(view.ValidateState(out var reason),reason);}
            var changed=ListItem.Generate(100,true);changed[0]=new ListItem(1,1,"changed");view.SetItems(changed,false);
            Assert.AreEqual(1,view.Cells[0].Template);Assert.AreEqual("changed",view.Cells[0].Label.text);
            view.EdgeFade=true;view.UpdateEffects();Assert.Less(view.Cells[0].Group.alpha,1);view.EdgeFade=false;view.UpdateEffects();Assert.AreEqual(1,view.Cells[0].Group.alpha);
        }
        [UnityTest] public IEnumerator ExternalDestructionRecoversAndInvalidInputIsAtomic()
        {
            foreach(bool virtualized in new[]{false,true})
            {
            var view=ListLabFactory.Create(virtualized,out root);view.SetItems(ListItem.Generate(100));yield return null;
            Object.Destroy(view.Cells[0].gameObject);yield return null;view.SetPixelOffset(0);
            Assert.True(view.ValidateState(out var reason),reason);
            Assert.Throws<System.ArgumentException>(()=>view.SetItems(new[]{new ListItem(1,0,"A"),new ListItem(1,0,"B")}));
            Assert.AreEqual(100,view.Count);Assert.True(view.ValidateState(out reason),reason);
            var pool=view.Pool;Object.Destroy(root);yield return null;root=null;Assert.AreEqual(pool.Created,pool.Destroyed);Assert.AreEqual(0,pool.UniqueTotal);
            }
        }
    }
}
