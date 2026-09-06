using UnityEngine;
using UnityEngine.UI;

namespace XUILab.ListLab
{
    public sealed class FixedRowLayout : LayoutGroup
    {
        public const float RowHeight = 48;
        public override void CalculateLayoutInputVertical() { SetLayoutInputForAxis(0, 0, -1, 1); }
        public override void SetLayoutHorizontal()
        {
            foreach (var child in rectChildren) SetChildAlongAxis(child, 0, 0, rectTransform.rect.width);
        }
        public override void SetLayoutVertical()
        {
            foreach (var child in rectChildren)
            {
                var cell = child.GetComponent<ListCell>();
                if (cell && cell.IsBound) SetChildAlongAxis(child, 1, cell.Index * RowHeight, RowHeight);
            }
        }
        public void Invalidate() { SetDirty(); }
    }
}
