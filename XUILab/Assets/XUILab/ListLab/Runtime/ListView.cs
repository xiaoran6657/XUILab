using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

namespace XUILab.ListLab
{
    public enum ListRefreshPolicy { VisibleWindow, TargetOnly }

    public readonly struct ListItemUpdate
    {
        public readonly int Index;
        public readonly ListItem Item;
        public ListItemUpdate(int index, ListItem item) { Index = index; Item = item; }
    }

    public sealed class ListView : MonoBehaviour
    {
        public const int Prefetch = 2;
        public ScrollRect Scroll { get; private set; }
        public ListCellPool Pool { get; private set; }
        public bool Virtualized { get; private set; }
        public bool Animate { get; set; }
        public bool EdgeFade { get; set; }
        public int Count => items.Length;
        public int PendingRefreshCount => pending.Count;
        public ListRefreshPolicy RefreshPolicy
        {
            get => refreshPolicy;
            set
            {
                if (mutating) throw new InvalidOperationException("Nested list mutation is not supported.");
                if (value != ListRefreshPolicy.VisibleWindow && value != ListRefreshPolicy.TargetOnly)
                    throw new ArgumentOutOfRangeException(nameof(value));
                refreshPolicy = value;
            }
        }
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
        private readonly List<int> visibleScratch = new List<int>(16);
        private readonly HashSet<int> pending = new HashSet<int>();
        private readonly HashSet<int> batchIndices = new HashSet<int>();
        private readonly List<ListItemUpdate> batch = new List<ListItemUpdate>(16);
        private ListRefreshPolicy refreshPolicy;
        private bool mutating, lifecycleDeferred, scrollDeferred, dispatchFaulted;
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
        private void BeginMutation(bool recovery = false)
        {
            if (!initialized) throw new InvalidOperationException("List is not initialized.");
            if (mutating) throw new InvalidOperationException("Nested list mutation is not supported.");
            if (dispatchFaulted && !recovery) throw new InvalidOperationException("Recover the failed dispatch with UpdateEffects or SetItems first.");
            mutating = true;
        }
        private void EndMutation(Exception primaryError = null)
        {
            try
            {
                if (primaryError != null)
                {
                    lifecycleDeferred = scrollDeferred = false;
                    if (!isActiveAndEnabled)
                    {
                        try { ReleaseAll(); } catch { }
                    }
                    return; // The caller rethrows the original exception; never replace it here.
                }
                for (int iteration = 0; lifecycleDeferred || scrollDeferred; iteration++)
                {
                    if (iteration == 8)
                    {
                        dispatchFaulted = true; lifecycleDeferred = scrollDeferred = false;
                        if (!isActiveAndEnabled) ReleaseAll();
                        throw new InvalidOperationException("List callbacks did not reach a stable lifecycle/window state.");
                    }
                    lifecycleDeferred = scrollDeferred = false;
                    if (isActiveAndEnabled) Reconcile(); else ReleaseAll();
                }
            }
            catch { dispatchFaulted = true; throw; }
            finally { mutating = false; }
        }
        private void CheckIndex(int index)
        {
            if (index < 0 || index >= Count) throw new ArgumentOutOfRangeException(nameof(index));
        }
        private void ValidateUpdate(int index, ListItem item)
        {
            CheckIndex(index);
            if (item == null) throw new ArgumentNullException(nameof(item));
            if (item.Id != items[index].Id)
                throw new ArgumentException("Single updates preserve the stable item ID; use SetItems for structural changes.");
        }
        private bool Publish(int index, ListItem item)
        {
            var previous = items[index];
            if (previous.Template == item.Template && previous.Label == item.Label) return false;
            items[index] = item; pending.Add(index); return true;
        }
        public ListItem GetItem(int index) { CheckIndex(index); return items[index]; }
        public void UpdateItem(int index, ListItem item)
        {
            BeginMutation();
            Exception primaryError = null;
            try
            {
                ValidateUpdate(index, item);
                if (!Publish(index, item) || !isActiveAndEnabled) return;
                if (refreshPolicy == ListRefreshPolicy.VisibleWindow) RefreshWindowCore();
                else if (Intersects(index)) RefreshIndexCore(index);
            }
            catch (Exception error) { primaryError = error; throw; }
            finally { EndMutation(primaryError); }
        }
        public void UpdateItems(IReadOnlyList<ListItemUpdate> updates)
        {
            BeginMutation();
            Exception primaryError = null;
            try
            {
                if (updates == null) throw new ArgumentNullException(nameof(updates));
                batch.Clear(); batchIndices.Clear();
                // Snapshot and validate before publishing or invoking UI callbacks.
                for (int i = 0; i < updates.Count; i++)
                {
                    var update = updates[i]; ValidateUpdate(update.Index, update.Item);
                    if (!batchIndices.Add(update.Index)) throw new ArgumentException("Duplicate update index.");
                    batch.Add(update);
                }
                for (int i = batch.Count - 1; i >= 0; i--)
                    if (!Publish(batch[i].Index, batch[i].Item)) batch.RemoveAt(i);
                if (!isActiveAndEnabled || batch.Count == 0) return;
                if (refreshPolicy == ListRefreshPolicy.VisibleWindow) RefreshWindowCore();
                else for (int i = 0; i < batch.Count; i++)
                    if (Intersects(batch[i].Index)) RefreshIndexCore(batch[i].Index);
            }
            catch (Exception error) { primaryError = error; throw; }
            finally { batch.Clear(); batchIndices.Clear(); EndMutation(primaryError); }
        }
        private void RefreshWindowCore()
        {
            visibleScratch.Clear();
            foreach (var pair in cells) if (Intersects(pair.Key)) visibleScratch.Add(pair.Key);
            // Template replacement mutates cells; do not keep its enumerator alive.
            for (int i = 0; i < visibleScratch.Count; i++) RefreshIndexCore(visibleScratch[i]);
            visibleScratch.Clear();
        }
        private void ReturnAfterFailedBind(ListCell cell)
        {
            if (!Pool.IsLeased(cell)) return;
            // Return attempts every ownership cleanup step. Preserve the first callback exception.
            try { Pool.Return(cell); } catch { }
        }
        private void RefreshIndexCore(int index)
        {
            cells.TryGetValue(index, out var cell);
            try
            {
                if (cell && cell.Template == items[index].Template)
                    Pool.Rebind(cell, items[index], index, Animate);
                else
                {
                    cells.Remove(index);
                    if (cell) Pool.Return(cell); else Pool.Sweep();
                    cell = Pool.Rent(items[index].Template, Scroll.content);
                    Pool.Bind(cell, items[index], index, Animate);
                    cells.Add(index, cell);
                    layout.Invalidate();
                }
                pending.Remove(index);
            }
            catch
            {
                dispatchFaulted = true; cells.Remove(index); pending.Add(index); ReturnAfterFailedBind(cell);
                throw;
            }
        }
        private void FlushPendingVisible()
        {
            if (pending.Count == 0 || !isActiveAndEnabled) return;
            int first = Mathf.Max(0, Mathf.FloorToInt(PixelOffset / FixedRowLayout.RowHeight));
            int end = Mathf.Min(Count, Mathf.CeilToInt((PixelOffset + Scroll.viewport.rect.height) / FixedRowLayout.RowHeight));
            for (int i = first; i < end; i++) if (pending.Contains(i)) RefreshIndexCore(i);
        }
        public void SetItems(IReadOnlyList<ListItem> source, bool restore = true)
        {
            BeginMutation(true);
            Exception primaryError = null;
            try
            {
                var validated = ListItem.CopyAndValidate(source);
                var position = CapturePosition();
                ReleaseAll(); pending.Clear(); items = validated;
                Scroll.content.SetSizeWithCurrentAnchors(RectTransform.Axis.Vertical, Count * FixedRowLayout.RowHeight);
                RestorePositionCore(restore ? position : default(ListPosition));
                dispatchFaulted = false;
            }
            catch (Exception error) { primaryError = error; throw; }
            finally { EndMutation(primaryError); }
        }
        public ListPosition CapturePosition()
        {
            if (Count == 0) return default(ListPosition);
            int index = Mathf.Min(Count - 1, Mathf.FloorToInt(PixelOffset / FixedRowLayout.RowHeight));
            return new ListPosition { HasItem = true, ItemId = items[index].Id, Index = index, Offset = PixelOffset - index * FixedRowLayout.RowHeight };
        }
        public void RestorePosition(ListPosition position)
        {
            BeginMutation(); Exception first = null;
            try { RestorePositionCore(position); } catch (Exception error) { first = error; throw; } finally { EndMutation(first); }
        }
        private void RestorePositionCore(ListPosition position)
        {
            int index = Mathf.Clamp(position.Index, 0, Mathf.Max(0, Count - 1));
            if (position.HasItem) for (int i = 0; i < Count; i++) if (items[i].Id == position.ItemId) { index = i; break; }
            float offset = float.IsNaN(position.Offset) || float.IsInfinity(position.Offset) ? 0 : Mathf.Clamp(position.Offset, 0, FixedRowLayout.RowHeight - .0001f);
            SetPixelOffsetCore(position.HasItem ? index * FixedRowLayout.RowHeight + offset : 0);
        }
        public void SetPixelOffset(float offset)
        {
            BeginMutation(); Exception first = null;
            try { SetPixelOffsetCore(offset); } catch (Exception error) { first = error; throw; } finally { EndMutation(first); }
        }
        private void SetPixelOffsetCore(float offset)
        {
            if (float.IsNaN(offset) || float.IsInfinity(offset)) throw new ArgumentOutOfRangeException(nameof(offset));
            Scroll.StopMovement(); Scroll.content.anchoredPosition = new Vector2(0, Mathf.Clamp(offset, 0, MaxOffset));
            if (Virtualized || cells.Count != Count || EdgeFade || observedDestructionVersion != Pool.ExternalDestructionVersion) Reconcile();
            else FlushPendingVisible();
        }
        public void RefreshItem(int index)
        {
            BeginMutation();
            Exception first = null;
            try
            {
                CheckIndex(index);
                if (!isActiveAndEnabled) return;
                if (refreshPolicy == ListRefreshPolicy.VisibleWindow) RefreshWindowCore();
                else if (Intersects(index)) RefreshIndexCore(index);
            }
            catch (Exception error) { first = error; throw; }
            finally { EndMutation(first); }
        }
        public bool ValidateState(out string reason)
        {
            if (dispatchFaulted) { reason = "UI dispatch failed; explicit recovery is required."; return false; }
            if (!Pool.ValidateOwnership(out reason)) return false;
            var identities = new HashSet<int>();
            foreach (var pair in cells)
            {
                var cell = pair.Value;
                if (!cell || pair.Key < 0 || pair.Key >= Count || !cell.IsBound || cell.Index != pair.Key || cell.ItemId != items[pair.Key].Id ||
                    !cell.gameObject.activeInHierarchy || !identities.Add(cell.GetInstanceID()))
                { reason = "Cell identity/binding mismatch."; return false; }
                bool mayLag = pending.Contains(pair.Key) && !Intersects(pair.Key);
                if (!mayLag && (cell.Template != items[pair.Key].Template || cell.Label.text != items[pair.Key].Label))
                { reason = "Cell content is stale without an off-screen pending update."; return false; }
            }
            foreach (int index in pending) if (index < 0 || index >= Count)
            { reason = "Pending index escaped the data set."; return false; }
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
            if (!initialized || dispatchFaulted) return;
            if (mutating) { scrollDeferred = true; return; }
            BeginMutation(); Exception first = null;
            try
            {
                if (Virtualized || EdgeFade || observedDestructionVersion != Pool.ExternalDestructionVersion) Reconcile();
                else FlushPendingVisible();
            }
            catch (Exception error) { first = error; throw; }
            finally { EndMutation(first); }
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
                foreach (var p in cells) if (p.Key < first || p.Key >= end || !p.Value || (p.Value.Template != items[p.Key].Template && (!pending.Contains(p.Key) || Intersects(p.Key)))) remove.Add(p.Key);
                bool changed = remove.Count > 0;
                foreach (int index in remove)
                {
                    var old = cells[index]; cells.Remove(index);
                    if (old) Pool.Return(old);
                }
                for (int i = first; i < end; i++) if (!cells.ContainsKey(i))
                {
                    var cell = Pool.Rent(items[i].Template, Scroll.content);
                    try
                    {
                        Pool.Bind(cell, items[i], i, Animate);
                        cells.Add(i, cell); pending.Remove(i); changed = true;
                    }
                    catch { pending.Add(i); ReturnAfterFailedBind(cell); throw; }
                }
                FlushPendingVisible();
                if (changed) layout.Invalidate();
                if (EdgeFade) foreach (var p in cells)
                {
                    float middle = (p.Key + .5f) * FixedRowLayout.RowHeight - PixelOffset;
                    p.Value.SetEdgeAlpha(Mathf.Clamp01(Mathf.Min(middle, Scroll.viewport.rect.height - middle) / 48));
                }
                dispatchFaulted = false;
            }
            catch { dispatchFaulted = true; throw; }
            finally { reconciling = false; }
        }
        public void UpdateEffects()
        {
            BeginMutation(true);
            Exception primaryError = null;
            try
            {
                if (!EdgeFade) foreach (var p in cells) if (p.Value) p.Value.SetEdgeAlpha(1);
                Reconcile();
            }
            catch (Exception error) { primaryError = error; throw; }
            finally { EndMutation(primaryError); }
        }
        private void LateUpdate()
        {
            if (!initialized || mutating || dispatchFaulted) return;
            if (observedDestructionVersion != Pool.ExternalDestructionVersion)
            {
                BeginMutation(true); Exception first = null;
            try { Reconcile(); } catch (Exception error) { first = error; throw; } finally { EndMutation(first); }
            }
            if (!Mathf.Approximately(lastHeight, Scroll.viewport.rect.height))
            { lastHeight = Scroll.viewport.rect.height; SetPixelOffset(PixelOffset); }
        }
        private void OnEnable()
        {
            if (!initialized) return;
            if (mutating) { lifecycleDeferred = true; return; }
            BeginMutation(true); Exception first = null;
            try { Reconcile(); } catch (Exception error) { first = error; throw; } finally { EndMutation(first); }
        }
        private void OnDisable()
        {
            if (!initialized) return;
            if (mutating) { lifecycleDeferred = true; return; }
            BeginMutation(true); Exception first = null;
            try { ReleaseAll(); } catch (Exception error) { first = error; throw; } finally { EndMutation(first); }
        }
        private void ReleaseAll()
        {
            remove.Clear();
            foreach (var pair in cells) remove.Add(pair.Key);
            Exception firstError = null;
            foreach (int index in remove)
            {
                var old = cells[index]; cells.Remove(index);
                try { if (old) Pool.Return(old); }
                catch (Exception error) { if (firstError == null) firstError = error; }
            }
            Pool.Sweep();
            if (firstError != null) { dispatchFaulted = true; System.Runtime.ExceptionServices.ExceptionDispatchInfo.Capture(firstError).Throw(); }
        }
        private void OnDestroy()
        {
            if (!initialized) return;
            Scroll.onValueChanged.RemoveListener(OnScroll); Pool.Dispose(); pending.Clear(); batch.Clear(); batchIndices.Clear(); initialized = false;
        }
    }
}
