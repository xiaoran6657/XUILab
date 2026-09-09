using UnityEngine;
using UnityEngine.UI;

namespace XUILab.ListLab
{
    public sealed class ListLabDemo : MonoBehaviour
    {
        public ListView View { get; private set; }
        public string CurrentAction { get; private set; } = "Ready";
        public bool MeasurementMode { get; set; }
        private GameObject root;
        private Text diagnostic;
        private int count = 1000;
        private bool virtualized = true;
        private bool dual;
        private bool effects;
        private ListRefreshPolicy refreshPolicy;
        private int revision;
        private ListPosition saved;
        private float nextDiagnostic;
        private void Start() { if (!MeasurementMode) Rebuild(); }
        public void Rebuild()
        {
            if (root) { root.SetActive(false); Destroy(root); }
            View = ListLabFactory.Create(virtualized, out root);
            root.GetComponent<CanvasScaler>().referenceResolution = new Vector2(960,600);
            root.GetComponent<CanvasScaler>().uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
            root.GetComponent<CanvasScaler>().screenMatchMode = CanvasScaler.ScreenMatchMode.Expand;
            View.RefreshPolicy = refreshPolicy;
            View.Animate = effects; View.EdgeFade = effects;
            View.SetItems(ListItem.Generate(count, dual), false);
            TextAt("LIST LAB  /  FIXED-HEIGHT VIRTUALIZATION", 245, 22);
            ButtonAt("Backend", -360, 216, () => { virtualized = !virtualized; Rebuild(); });
            ButtonAt("100 / 1000", -240, 216, () => { count = count == 100 ? 1000 : 100; Rebuild(); });
            ButtonAt("2 templates", -120, 216, () => { dual = !dual; Rebuild(); });
            ButtonAt("Effects", 0, 216, () => { effects = !effects; Rebuild(); });
            ButtonAt("Top", 120, 216, () => { View.SetPixelOffset(0); CurrentAction = "Jump to top"; });
            ButtonAt("Bottom", 240, 216, () => { View.SetPixelOffset(View.MaxOffset); CurrentAction = "Jump to bottom"; });
            ButtonAt("Save", 360, 216, () => { saved = View.CapturePosition(); CurrentAction = "Position saved"; });
            ButtonAt("Restore", -180, -216, () => { View.RestorePosition(saved); CurrentAction = "Position restored"; });
            ButtonAt("Clear / refill", -60, -216, () => { View.SetItems(View.Count == 0 ? ListItem.Generate(count, dual) : new ListItem[0]); CurrentAction = "Clear / refill"; });
            ButtonAt("Reopen", 60, -216, () => { View.gameObject.SetActive(false); View.gameObject.SetActive(true); CurrentAction = "Disable / reopen"; });
            ButtonAt("Update item", 180, -216, UpdateVisibleItem);
            ButtonAt("Policy", 300, -216, ToggleRefreshPolicy);
            diagnostic = TextAt("", -249, 14); saved = View.CapturePosition(); CurrentAction = "Drag / wheel to scroll"; UpdateDiagnostic();
        }
        public void ToggleRefreshPolicy()
        {
            refreshPolicy = refreshPolicy == ListRefreshPolicy.VisibleWindow ? ListRefreshPolicy.TargetOnly : ListRefreshPolicy.VisibleWindow;
            if (View) View.RefreshPolicy = refreshPolicy;
            CurrentAction = "Refresh policy: " + refreshPolicy;
        }
        public void UpdateVisibleItem()
        {
            if (!View || View.Count == 0) { CurrentAction = "No item to update"; return; }
            int index = View.CapturePosition().Index;
            var item = View.GetItem(index);
            int before = View.Pool.BindCount;
            View.UpdateItem(index, new ListItem(item.Id, item.Template, "Item " + item.Id + " / revision " + (++revision)));
            CurrentAction = "Updated " + index + " / binds +" + (View.Pool.BindCount - before);
        }
        private void Update()
        {
            if (!MeasurementMode && View && Time.unscaledTime >= nextDiagnostic)
            { nextDiagnostic = Time.unscaledTime + .1f; UpdateDiagnostic(); }
        }
        private void UpdateDiagnostic()
        {
            // Diagnostic-only mode: read settled rectangles, never pending layout.
            Canvas.ForceUpdateCanvases();
            diagnostic.text = (virtualized ? "VIRTUAL" : "NORMAL") + "   N " + View.Count + "   visible " + View.VisibleCount +
                "   leased " + View.Pool.Leased + "   cached " + View.Pool.Cached + "   created " + View.Pool.Created +
                "   binds " + View.Pool.BindCount + " / " + refreshPolicy + "   | " + CurrentAction;
        }
        private Text TextAt(string value, float y, int size)
        {
            var rect = ListLabFactory.Rect("Text", root.transform); rect.sizeDelta = new Vector2(940, 28); rect.anchoredPosition = new Vector2(0,y);
            var text = rect.gameObject.AddComponent<Text>(); text.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            text.fontSize = size; text.alignment = TextAnchor.MiddleCenter; text.color = Color.white; text.text = value; text.raycastTarget = false; return text;
        }
        private void ButtonAt(string label, float x, float y, UnityEngine.Events.UnityAction action)
        {
            var rect = ListLabFactory.Rect(label, root.transform); rect.sizeDelta = new Vector2(112,26); rect.anchoredPosition = new Vector2(x,y);
            rect.gameObject.AddComponent<Image>().color = new Color(.16f,.29f,.40f);
            var button = rect.gameObject.AddComponent<Button>(); button.onClick.AddListener(action);
            var child = ListLabFactory.Rect("Label",rect); ListLabFactory.Stretch(child); var text = child.gameObject.AddComponent<Text>();
            text.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf"); text.fontSize = 14; text.alignment = TextAnchor.MiddleCenter;
            text.text = label; text.color = Color.white; text.raycastTarget = false;
        }
        private void OnDestroy() { if (root) Destroy(root); }
    }
}
