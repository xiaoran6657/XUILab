using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

namespace XUILab.ListLab
{
    public sealed class ListView : MonoBehaviour
    {
        public const int Prefetch = 2;
        public ScrollRect Scroll { get; private set; }
        public ListCellPool Pool { get; private set; }
        public bool Virtualized { get; private set; }
        public bool Animate { get; set; }
        public bool EdgeFade { get; set; }
        public int Count => items.Length;
        public float PixelOffset => Scroll ? Mathf.Clamp(Scroll.content.anchoredPosition.y, 0, MaxOffset) : 0;
        public float MaxOffset => Mathf.Max(0, Count * FixedRowLayout.RowHeight - Scroll.viewport.rect.height);
        public IReadOnlyDictionary<int, ListCell> Cells => cells;
        public int VisibleCount
        {
            get
            {
                int count = 0;
                foreach (var p in cells) if (p.Value && p.Value.gameObject.activeInHierarchy)
                {
                    var rect = (RectTransform)p.Value.transform;
                    float top = -rect.anchoredPosition.y;
                    if (top + rect.rect.height > PixelOffset && top < PixelOffset + Scroll.viewport.rect.height) count++;
                }
                return count;
            }
        }
        public int ActiveCount
        {
            get { return Pool == null ? 0 : Pool.Active; }
        }
        private ListItem[] items = Array.Empty<ListItem>();
        private readonly Dictionary<int, ListCell> cells = new Dictionary<int, ListCell>();
        private readonly List<int> remove = new List<int>();
        private FixedRowLayout layout;
        private bool initialized;
        private bool reconciling;
        private float lastHeight;
        private int observedDestructionVersion;

        public void Initialize(ScrollRect scroll, Transform cacheRoot, bool virtualized, Font font)
        {
            if (initialized || !scroll || !scroll.content || !scroll.viewport) throw new InvalidOperationException("Invalid list initialization.");
            Scroll = scroll; Virtualized = virtualized; Pool = new ListCellPool(cacheRoot, font);
            layout = Scroll.content.GetComponent<FixedRowLayout>();
            if (!layout) layout = Scroll.content.gameObject.AddComponent<FixedRowLayout>();
            initialized = true; lastHeight = Scroll.viewport.rect.height;
            Scroll.onValueChanged.AddListener(OnScroll);
        }
        public void SetItems(IReadOnlyList<ListItem> source, bool restore = true)
        {
            var validated = ListItem.CopyAndValidate(source);
            var position = CapturePosition();
            ReleaseAll(); items = validated;
            Scroll.content.SetSizeWithCurrentAnchors(RectTransform.Axis.Vertical, Count * FixedRowLayout.RowHeight);
            RestorePosition(restore ? position : default(ListPosition));
        }
        public ListPosition CapturePosition()
        {
            if (Count == 0) return default(ListPosition);
            int index = Mathf.Min(Count - 1, Mathf.FloorToInt(PixelOffset / FixedRowLayout.RowHeight));
            return new ListPosition { HasItem = true, ItemId = items[index].Id, Index = index, Offset = PixelOffset - index * FixedRowLayout.RowHeight };
        }
        public void RestorePosition(ListPosition position)
        {
            int index = Mathf.Clamp(position.Index, 0, Mathf.Max(0, Count - 1));
            if (position.HasItem) for (int i = 0; i < Count; i++) if (items[i].Id == position.ItemId) { index = i; break; }
            float offset = float.IsNaN(position.Offset) || float.IsInfinity(position.Offset) ? 0 : Mathf.Clamp(position.Offset, 0, FixedRowLayout.RowHeight - .0001f);
            SetPixelOffset(position.HasItem ? index * FixedRowLayout.RowHeight + offset : 0);
        }
        public void SetPixelOffset(float offset)
        {
            if (float.IsNaN(offset) || float.IsInfinity(offset)) throw new ArgumentOutOfRangeException(nameof(offset));
            Scroll.StopMovement(); Scroll.content.anchoredPosition = new Vector2(0, Mathf.Clamp(offset, 0, MaxOffset));
            if (Virtualized || cells.Count != Count || EdgeFade || observedDestructionVersion != Pool.ExternalDestructionVersion) Reconcile();
        }
        public void RefreshItem(int index)
        {
            if (index < 0 || index >= Count) throw new ArgumentOutOfRangeException(nameof(index));
            // Deliberately retain the M1 visible-window refresh baseline for M3.
            foreach (var pair in cells) if (pair.Value && Intersects(pair.Key)) Pool.Rebind(pair.Value, items[pair.Key], pair.Key, Animate);
        }
        public bool ValidateState(out string reason)
        {
            if (!Pool.ValidateOwnership(out reason)) return false;
            var identities = new HashSet<int>();
            foreach (var pair in cells)
            {
                var cell = pair.Value;
                if (!cell || pair.Key < 0 || pair.Key >= Count || !cell.IsBound || cell.Index != pair.Key || cell.ItemId != items[pair.Key].Id ||
                    cell.Template != items[pair.Key].Template || !cell.gameObject.activeInHierarchy || !identities.Add(cell.GetInstanceID()))
                { reason = "Cell identity/binding mismatch."; return false; }
            }
            GetWindow(out int first, out int end);
            int expected = isActiveAndEnabled ? (Virtualized ? end - first : Count) : 0;
            if (cells.Count != expected || ActiveCount != expected || Pool.Leased != cells.Count || Pool.UniqueTotal != Pool.Leased + Pool.Cached || Pool.Created - Pool.Destroyed != Pool.UniqueTotal)
            { reason = "Ownership/window count mismatch."; return false; }
            reason = string.Empty; return true;
        }
        private bool Intersects(int index) => (index + 1) * FixedRowLayout.RowHeight > PixelOffset && index * FixedRowLayout.RowHeight < PixelOffset + Scroll.viewport.rect.height;
        private void GetWindow(out int first, out int end)
        {
            first = Mathf.Max(0, Mathf.FloorToInt(PixelOffset / FixedRowLayout.RowHeight) - Prefetch);
            end = Mathf.Min(Count, Mathf.CeilToInt((PixelOffset + Scroll.viewport.rect.height) / FixedRowLayout.RowHeight) + Prefetch);
        }
        private void OnScroll(Vector2 value)
        {
            // A fully populated ordinary ScrollRect has no window work during scrolling.
            if (Virtualized || EdgeFade || observedDestructionVersion != Pool.ExternalDestructionVersion) Reconcile();
        }
        private void Reconcile()
        {
            if (!initialized || !isActiveAndEnabled || reconciling) return;
            reconciling = true;
            try
            {
                Pool.Sweep(); observedDestructionVersion = Pool.ExternalDestructionVersion; GetWindow(out int first, out int end);
                if (!Virtualized) { first = 0; end = Count; }
                remove.Clear();
                foreach (var p in cells) if (p.Key < first || p.Key >= end || !p.Value || p.Value.Template != items[p.Key].Template) remove.Add(p.Key);
                bool changed = remove.Count > 0;
                foreach (int index in remove) { if (cells[index]) Pool.Return(cells[index]); cells.Remove(index); }
                for (int i = first; i < end; i++) if (!cells.ContainsKey(i))
                {
                    var cell = Pool.Rent(items[i].Template, Scroll.content); cells.Add(i, cell); Pool.Bind(cell, items[i], i, Animate); changed = true;
                }
                if (changed) layout.Invalidate();
                if (EdgeFade) foreach (var p in cells)
                {
                    float middle = (p.Key + .5f) * FixedRowLayout.RowHeight - PixelOffset;
                    p.Value.SetEdgeAlpha(Mathf.Clamp01(Mathf.Min(middle, Scroll.viewport.rect.height - middle) / 48));
                }
            }
            finally { reconciling = false; }
        }
        public void UpdateEffects()
        {
            if (!EdgeFade) foreach (var p in cells) if (p.Value) p.Value.SetEdgeAlpha(1);
            Reconcile();
        }
        private void LateUpdate()
        {
            if (initialized && observedDestructionVersion != Pool.ExternalDestructionVersion) Reconcile();
            if (initialized && !Mathf.Approximately(lastHeight, Scroll.viewport.rect.height))
            { lastHeight = Scroll.viewport.rect.height; SetPixelOffset(PixelOffset); }
        }
        private void OnEnable() { if (initialized) Reconcile(); }
        private void OnDisable() { if (initialized) ReleaseAll(); }
        private void ReleaseAll()
        {
            foreach (var p in cells) if (p.Value) Pool.Return(p.Value);
            cells.Clear(); Pool.Sweep();
        }
        private void OnDestroy()
        {
            if (!initialized) return;
            Scroll.onValueChanged.RemoveListener(OnScroll); Pool.Dispose(); initialized = false;
        }
    }
}
