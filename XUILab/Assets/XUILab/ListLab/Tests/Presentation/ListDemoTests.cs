using System.Collections;
using System.Linq;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.TestTools;
using UnityEngine.UI;

namespace XUILab.ListLab.Tests
{
    public class ListDemoTests
    {
        private GameObject root;
        [UnityTearDown] public IEnumerator Cleanup(){ if(root)Object.Destroy(root);yield return null;yield return null; }
        [UnityTest] public IEnumerator ControlsSwitchBackendRestoreAndAcceptScrollInput()
        {
            root=new GameObject("demo-test",typeof(ListLabDemo));var demo=root.GetComponent<ListLabDemo>();yield return null;yield return null;
            Assert.AreEqual(1000,demo.View.Count);Assert.True(demo.View.Virtualized);
            Click("Bottom");Assert.AreEqual(demo.View.MaxOffset,demo.View.PixelOffset,.05f);Click("Save");Click("Top");Click("Restore");
            Assert.AreEqual(demo.View.MaxOffset,demo.View.PixelOffset,.05f);
            Click("100 / 1000");yield return null;Assert.AreEqual(100,demo.View.Count);
            Click("100 / 1000");yield return null;Assert.AreEqual(1000,demo.View.Count);
            Click("2 templates");yield return null;Assert.AreEqual(1,demo.View.Cells[1].Template);
            Click("Effects");yield return null;Assert.True(demo.View.Animate);Assert.True(demo.View.EdgeFade);
            Click("Effects");yield return null;Assert.False(demo.View.Animate);Assert.False(demo.View.EdgeFade);
            int binds=demo.View.Pool.BindCount;Click("Update item");Assert.AreEqual(binds+demo.View.VisibleCount,demo.View.Pool.BindCount);
            Click("Policy");Assert.AreEqual(ListRefreshPolicy.TargetOnly,demo.View.RefreshPolicy);
            binds=demo.View.Pool.BindCount;Click("Update item");Assert.AreEqual(binds+1,demo.View.Pool.BindCount);
            Assert.That(demo.View.GetItem(demo.View.CapturePosition().Index).Label,Does.Contain("revision"));
            Click("Backend");yield return null;Assert.False(demo.View.Virtualized);Assert.AreEqual(1000,demo.View.Pool.Leased);
            Assert.AreEqual(ListRefreshPolicy.TargetOnly,demo.View.RefreshPolicy);
            Click("Clear / refill");Assert.AreEqual(0,demo.View.Count);Click("Clear / refill");Click("Reopen");
            Assert.True(demo.View.ValidateState(out var reason),reason);
            var system=new GameObject("test-events",typeof(EventSystem));system.transform.SetParent(root.transform);
            var pointer=new PointerEventData(system.GetComponent<EventSystem>()){scrollDelta=new Vector2(0,-1)};
            ExecuteEvents.Execute(demo.View.Scroll.gameObject,pointer,ExecuteEvents.scrollHandler);
            yield return null;Assert.Greater(demo.View.PixelOffset,0);
        }
        [UnityTest] public IEnumerator AnimatedWrapperSettlesAndFadePreservesMaskMaterialAndRaycast()
        {
            var view=ListLabFactory.Create(true,out root);view.Animate=true;view.EdgeFade=true;view.SetItems(ListItem.Generate(100,true));yield return null;
            var cell=view.Cells[0];var image=cell.Wrapper.GetComponent<Image>();var material=image.material;
            yield return new WaitForSecondsRealtime(.3f);Assert.AreEqual(Vector3.one,cell.Wrapper.localScale);Assert.AreEqual(Vector2.zero,cell.Wrapper.anchoredPosition);
            Assert.Less(cell.Group.alpha,1);Assert.AreSame(material,image.material);Assert.True(image.raycastTarget);Assert.True(cell.Group.blocksRaycasts);
            Assert.IsNotNull(view.Scroll.viewport.GetComponent<RectMask2D>());
            view.SetItems(new ListItem[0]);yield return new WaitForSecondsRealtime(.25f);Assert.AreEqual(1,cell.Group.alpha);Assert.AreEqual(Vector3.one,cell.Wrapper.localScale);
        }
        private static void Click(string name)
        { Object.FindObjectsOfType<Button>().Single(b=>b.name==name).onClick.Invoke(); }
    }
}
