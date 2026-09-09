using System;
using System.Collections.Generic;
using UnityEngine;

namespace XUILab.ListLab
{
    public sealed class ListCellPool : IDisposable
    {
        private readonly Dictionary<int, ListCell> owned = new Dictionary<int, ListCell>();
        private readonly HashSet<int> leased = new HashSet<int>();
        private readonly HashSet<int> active = new HashSet<int>();
        private readonly List<ListCell>[] cache = { new List<ListCell>(), new List<ListCell>() };
        private readonly List<int> dead = new List<int>();
        private readonly Transform cacheRoot;
        private readonly Font font;
        private readonly int capacity;
        private bool disposed;
        public int Created { get; private set; }
        public int Destroyed { get; private set; }
        public int RejectedReturns { get; private set; }
        public int ExternalDestructionVersion { get; private set; }
        public int BindCount { get; private set; }
        public int UnbindCount { get; private set; }
        public int Leased => leased.Count;
        public int Active => active.Count;
        public int Cached => cache[0].Count + cache[1].Count;
        public int UniqueTotal => owned.Count;
        public ListCellPool(Transform cacheRoot, Font font, int capacity = 16)
        {
            if (!cacheRoot || !font || capacity < 0) throw new ArgumentException("Pool requires parent, font and non-negative capacity.");
            this.cacheRoot = cacheRoot; this.font = font; this.capacity = capacity;
        }
        public ListCell Rent(int template, Transform parent)
        {
            if (disposed) throw new ObjectDisposedException(nameof(ListCellPool));
            if (template < 0 || template > 1 || !parent) throw new ArgumentException("Invalid rent.");
            var list = cache[template]; ListCell cell;
            // Avoid an O(N) lease scan for each of N cold-open rents.
            for (int i = list.Count - 1; i >= 0; i--) if (!list[i]) { Sweep(); break; }
            if (list.Count > 0) { int last = list.Count - 1; cell = list[last]; list.RemoveAt(last); }
            else
            {
                cell = ListCell.Create(template, cacheRoot, font);
                int id = cell.GetInstanceID(); owned.Add(id, cell);
                var activity = cell.gameObject.AddComponent<ListCellActivity>();
                activity.Changed = value => { if (value) active.Add(id); else active.Remove(id); };
                if (cell.gameObject.activeInHierarchy) active.Add(id);
                cell.DestroyedExternally = OnExternalDestroy; Created++;
            }
            if (!leased.Add(cell.GetInstanceID())) throw new InvalidOperationException("Duplicate lease.");
            try
            {
                cell.transform.SetParent(parent, false); cell.gameObject.SetActive(true); return cell;
            }
            catch
            {
                // A failed activation/parent callback must not keep an unreturned lease.
                try { Return(cell); } catch { }
                throw;
            }
        }
        public void Bind(ListCell cell, ListItem item, int index, bool animate)
        {
            if (!cell || !leased.Contains(cell.GetInstanceID()) || !owned.TryGetValue(cell.GetInstanceID(), out var known) || known != cell)
                throw new InvalidOperationException("Binding requires an owned lease.");
            cell.Bind(item, index, animate); BindCount++;
        }
        public void Rebind(ListCell cell, ListItem item, int index, bool animate)
        {
            if (!cell || !leased.Contains(cell.GetInstanceID()) || !owned.TryGetValue(cell.GetInstanceID(), out var known) || known != cell ||
                item == null || item.Template != cell.Template || index < 0) throw new InvalidOperationException("Invalid rebind.");
            if (cell.IsBound) { UnbindCount++; cell.Unbind(); }
            Bind(cell, item, index, animate);
        }
        public bool ValidateOwnership(out string reason)
        {
            Sweep(); var seen = new HashSet<int>();
            foreach (int id in leased) if (!owned.TryGetValue(id, out var cell) || !cell || !seen.Add(id))
            { reason = "Invalid leased identity."; return false; }
            for (int t = 0; t < 2; t++) foreach (var cell in cache[t])
            {
                if (!cell || cell.Template != t || cell.IsBound || cell.gameObject.activeSelf || !seen.Add(cell.GetInstanceID()) ||
                    !owned.TryGetValue(cell.GetInstanceID(), out var known) || known != cell)
                { reason = "Invalid or duplicate cached identity."; return false; }
            }
            if (seen.Count != owned.Count || owned.Count != Created - Destroyed)
            { reason = "Unowned identity or counter mismatch."; return false; }
            reason = string.Empty; return true;
        }
        internal bool IsLeased(ListCell cell)
        {
            return cell && leased.Contains(cell.GetInstanceID());
        }
        public bool Return(ListCell cell)
        {
            if (disposed || !cell || !owned.TryGetValue(cell.GetInstanceID(), out var known) || known != cell || !leased.Remove(cell.GetInstanceID()))
            { RejectedReturns++; Sweep(); return false; }
            // Complete each ownership cleanup step and preserve the first callback error.
            Exception firstError = null;
            try { if (cell.IsBound) { UnbindCount++; cell.Unbind(); } }
            catch (Exception error) { firstError = error; }
            try { if (cell) cell.gameObject.SetActive(false); }
            catch (Exception error) { if (firstError == null) firstError = error; }
            try { if (cell) cell.transform.SetParent(cacheRoot, false); }
            catch (Exception error) { if (firstError == null) firstError = error; }
            try
            {
                if (!cell) Sweep();
                else if (cell.gameObject.activeSelf || cell.transform.parent != cacheRoot) DestroyOwned(cell);
                else if (cache[cell.Template].Count < capacity) cache[cell.Template].Add(cell);
                else DestroyOwned(cell);
            }
            catch (Exception error) { if (firstError == null) firstError = error; }
            if (firstError != null) System.Runtime.ExceptionServices.ExceptionDispatchInfo.Capture(firstError).Throw();
            return true;
        }
        public void Sweep()
        {
            dead.Clear();
            foreach (var pair in owned) if (!pair.Value) dead.Add(pair.Key);
            foreach (int id in dead) { owned.Remove(id); leased.Remove(id); active.Remove(id); Destroyed++; ExternalDestructionVersion++; }
            for (int t = 0; t < 2; t++) for (int i = cache[t].Count - 1; i >= 0; i--) if (!cache[t][i]) cache[t].RemoveAt(i);
        }
        public void Dispose()
        {
            if (disposed) return;
            Sweep();
            disposed = true;
            foreach (var pair in owned)
            {
                var cell = pair.Value;
                cell.DestroyedExternally = null;
                if (cell.IsBound) { cell.Unbind(); UnbindCount++; }
                DestroyObject(cell.gameObject); Destroyed++;
            }
            owned.Clear(); leased.Clear(); active.Clear(); cache[0].Clear(); cache[1].Clear(); disposed = true;
        }
        private void OnExternalDestroy(int id)
        {
            if (disposed || !owned.TryGetValue(id, out var cell)) return;
            owned.Remove(id); leased.Remove(id); active.Remove(id);
            cache[cell.Template].Remove(cell); Destroyed++; ExternalDestructionVersion++;
        }
        private void DestroyOwned(ListCell cell)
        { cell.DestroyedExternally = null; owned.Remove(cell.GetInstanceID()); Destroyed++; DestroyObject(cell.gameObject); }
        internal static void DestroyObject(UnityEngine.Object value)
        {
            if (Application.isPlaying) UnityEngine.Object.Destroy(value); else UnityEngine.Object.DestroyImmediate(value);
        }
    }
}
