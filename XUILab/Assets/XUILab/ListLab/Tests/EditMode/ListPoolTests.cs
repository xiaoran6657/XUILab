using NUnit.Framework;
using UnityEngine;

namespace XUILab.ListLab.Tests
{
    public class ListPoolTests
    {
        private GameObject root;
        private ListCellPool pool;
        [SetUp] public void Setup() { root = new GameObject("pool-test"); pool = new ListCellPool(root.transform, Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf"), 2); }
        [TearDown] public void Teardown() { pool.Dispose(); Object.DestroyImmediate(root); }
        [Test] public void DuplicateReturnCannotProduceDuplicateLease()
        {
            var first = pool.Rent(0, root.transform); pool.Bind(first, new ListItem(1,0,"A"),0,false);
            Assert.True(pool.Return(first)); Assert.False(pool.Return(first));
            var a = pool.Rent(0,root.transform); var b = pool.Rent(0,root.transform);
            Assert.AreNotSame(a,b); Assert.AreEqual(2,pool.Leased); Assert.AreEqual(0,pool.Cached); Assert.AreEqual(1,pool.RejectedReturns);
            Assert.AreEqual(1,pool.BindCount); Assert.AreEqual(1,pool.UnbindCount);
        }
        [Test] public void ForeignReturnPreservesLeaseAndTemplateRouting()
        {
            using (var other = new ListCellPool(root.transform,Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf")))
            {
                var foreign = other.Rent(0,root.transform); Assert.False(pool.Return(foreign)); Assert.AreEqual(1,other.Leased);
                var a = pool.Rent(0,root.transform); pool.Return(a); var b = pool.Rent(1,root.transform);
                Assert.AreNotSame(a,b); Assert.AreEqual(1,b.Template);
            }
        }
        [Test] public void DestroyedCachedAndLeasedReferencesConverge()
        {
            var a = pool.Rent(0,root.transform); var b = pool.Rent(1,root.transform); pool.Return(a);
            Object.DestroyImmediate(a.gameObject); Object.DestroyImmediate(b.gameObject); pool.Sweep();
            Assert.AreEqual(0,pool.UniqueTotal); Assert.AreEqual(0,pool.Leased); Assert.AreEqual(0,pool.Cached); Assert.AreEqual(2,pool.Destroyed);
            Assert.False(pool.Return(b)); Assert.IsNotNull(pool.Rent(0,root.transform));
        }
        [Test] public void CacheCapAndDisposeAreIdempotent()
        {
            var a=pool.Rent(0,root.transform); var b=pool.Rent(0,root.transform); var c=pool.Rent(0,root.transform);
            pool.Return(a);pool.Return(b);pool.Return(c); Assert.AreEqual(2,pool.Cached);Assert.AreEqual(1,pool.Destroyed);
            pool.Dispose();pool.Dispose(); Assert.AreEqual(pool.Created,pool.Destroyed); Assert.AreEqual(0,pool.UniqueTotal);
        }
    }
}
