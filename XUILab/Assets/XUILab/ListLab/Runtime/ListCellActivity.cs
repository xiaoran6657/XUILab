using System;
using UnityEngine;

namespace XUILab.ListLab
{
    // Separate from the animation component, whose enabled flag is transient.
    public sealed class ListCellActivity : MonoBehaviour
    {
        internal Action<bool> Changed;
        private void OnEnable() => Changed?.Invoke(true);
        private void OnDisable() => Changed?.Invoke(false);
    }
}
