using UnityEngine;
using UnityEngine.UI;
using UnityEngine.EventSystems;

namespace XUILab.ListLab
{
    public static class ListLabFactory
    {
        public static ListView Create(bool virtualized, out GameObject root)
        {
            root = new GameObject("ListLab", typeof(RectTransform), typeof(Canvas), typeof(CanvasScaler), typeof(GraphicRaycaster));
            var canvas = root.GetComponent<Canvas>(); canvas.renderMode = RenderMode.ScreenSpaceOverlay;
            var scaler = root.GetComponent<CanvasScaler>(); scaler.uiScaleMode = CanvasScaler.ScaleMode.ConstantPixelSize;
            var panel = Rect("List", root.transform); panel.sizeDelta = new Vector2(720, 384);
            var scroll = panel.gameObject.AddComponent<ScrollRect>(); scroll.horizontal = false; scroll.vertical = true;
            scroll.movementType = ScrollRect.MovementType.Clamped; scroll.scrollSensitivity = 48;
            var viewport = Rect("Viewport", panel); Stretch(viewport); viewport.gameObject.AddComponent<Image>().color = new Color(.04f,.07f,.12f);
            viewport.gameObject.AddComponent<RectMask2D>();
            var content = Rect("Content", viewport); content.anchorMin = new Vector2(0, 1); content.anchorMax = Vector2.one;
            content.pivot = new Vector2(.5f, 1); content.anchoredPosition = Vector2.zero; content.sizeDelta = Vector2.zero;
            scroll.viewport = viewport; scroll.content = content;
            var cache = new GameObject("PoolCache"); cache.transform.SetParent(root.transform, false); cache.SetActive(false);
            var view = panel.gameObject.AddComponent<ListView>();
            view.Initialize(scroll, cache.transform, virtualized, Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf"));
            Canvas.ForceUpdateCanvases(); return view;
        }
        public static RectTransform Rect(string name, Transform parent)
        {
            var rect = (RectTransform)new GameObject(name, typeof(RectTransform)).transform; rect.SetParent(parent, false); return rect;
        }
        public static void Stretch(RectTransform rect)
        { rect.anchorMin = Vector2.zero; rect.anchorMax = Vector2.one; rect.offsetMin = Vector2.zero; rect.offsetMax = Vector2.zero; }
    }
}
