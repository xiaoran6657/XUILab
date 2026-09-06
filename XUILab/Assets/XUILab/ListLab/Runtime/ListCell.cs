using System;
using UnityEngine;
using UnityEngine.UI;

namespace XUILab.ListLab
{
    public sealed class ListCell : MonoBehaviour
    {
        public int Template { get; private set; }
        public int Index { get; private set; } = -1;
        public long ItemId { get; private set; }
        public bool IsBound { get; private set; }
        public RectTransform Wrapper { get; private set; }
        public CanvasGroup Group { get; private set; }
        public Text Label { get; private set; }
        public int BindCount { get; private set; }
        public int UnbindCount { get; private set; }
        private float transition;
        private float edgeAlpha = 1;
        internal Action<int> DestroyedExternally;

        public static ListCell Create(int template, Transform parent, Font font)
        {
            if (template < 0 || template > 1) throw new ArgumentOutOfRangeException(nameof(template));
            var root = new GameObject("Cell", typeof(RectTransform), typeof(ListCell));
            root.transform.SetParent(parent, false);
            ((RectTransform)root.transform).pivot = new Vector2(.5f, 1);
            var cell = root.GetComponent<ListCell>(); cell.Template = template;
            var wrapper = new GameObject("Wrapper", typeof(RectTransform), typeof(CanvasGroup), typeof(Image));
            wrapper.transform.SetParent(root.transform, false);
            cell.Wrapper = (RectTransform)wrapper.transform;
            cell.Wrapper.anchorMin = Vector2.zero; cell.Wrapper.anchorMax = Vector2.one;
            cell.Wrapper.offsetMin = new Vector2(2, 2); cell.Wrapper.offsetMax = new Vector2(-2, -2);
            wrapper.GetComponent<Image>().color = template == 0 ? new Color(.10f,.18f,.28f) : new Color(.20f,.13f,.29f);
            cell.Group = wrapper.GetComponent<CanvasGroup>();
            var text = new GameObject("Label", typeof(RectTransform), typeof(Text));
            text.transform.SetParent(wrapper.transform, false);
            var rect = (RectTransform)text.transform; rect.anchorMin = Vector2.zero; rect.anchorMax = Vector2.one;
            rect.offsetMin = new Vector2(16, 0); rect.offsetMax = new Vector2(-16, 0);
            cell.Label = text.GetComponent<Text>(); cell.Label.font = font; cell.Label.fontSize = 18;
            cell.Label.alignment = TextAnchor.MiddleLeft; cell.Label.color = Color.white;
            cell.Label.raycastTarget = false;
            cell.enabled = false;
            return cell;
        }
        public void Bind(ListItem item, int index, bool animate)
        {
            if (IsBound || item == null || item.Template != Template || index < 0) throw new InvalidOperationException("Invalid cell bind.");
            ResetVisual(); Index = index; ItemId = item.Id; Label.text = item.Label;
            IsBound = true; BindCount++;
            transition = animate ? .2f : 0;
            enabled = animate;
        }
        public void Unbind()
        {
            if (IsBound) UnbindCount++;
            IsBound = false; Index = -1; ItemId = 0; Label.text = string.Empty; ResetVisual();
        }
        public void SetEdgeAlpha(float alpha) { edgeAlpha = Mathf.Clamp01(alpha); ApplyVisual(); }
        private void ResetVisual()
        {
            transition = 0; edgeAlpha = 1;
            enabled = false;
            Wrapper.localScale = Vector3.one; Wrapper.anchoredPosition = Vector2.zero; Group.alpha = 1;
        }
        private void Update()
        {
            if (transition <= 0) return;
            transition = Mathf.Max(0, transition - Time.unscaledDeltaTime); ApplyVisual();
            if (transition <= 0) enabled = false;
        }
        private void OnDestroy() { DestroyedExternally?.Invoke(GetInstanceID()); }
        private void ApplyVisual()
        {
            float t = transition / .2f;
            Wrapper.localScale = Vector3.one * (1 - .08f * t);
            Wrapper.anchoredPosition = new Vector2(12 * t, 0); Group.alpha = (1 - t) * edgeAlpha;
        }
    }
}
