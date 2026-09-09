using System;
using UnityEngine;

namespace XUILab.GradientLab
{
    public enum GradientDirection { Horizontal, Vertical }
    public enum GradientCurve { Linear, Nonlinear }
    public enum GradientMeshMode { Disabled, Empty, Degenerate, LinearVertices, FixedSegments, VertexFallback, InvalidInput, AdaptiveSegments }

    public static class GradientFunction
    {
        public const float MinBias = .05f, MaxBias = .95f;
        public static bool Finite(float x) => !float.IsNaN(x) && !float.IsInfinity(x);
        public static float NormalizeBias(float value)
        {
            if (!Finite(value)) throw new ArgumentOutOfRangeException(nameof(value));
            return Mathf.Clamp(value, MinBias, MaxBias);
        }
        public static Color NormalizeColor(Color value)
        {
            if (!Finite(value.r) || !Finite(value.g) || !Finite(value.b) || !Finite(value.a))
                throw new ArgumentOutOfRangeException(nameof(value));
            return new Color(Mathf.Clamp01(value.r), Mathf.Clamp01(value.g), Mathf.Clamp01(value.b), Mathf.Clamp01(value.a));
        }
        public static Color32 Quantize(Color c)
        {
            c = NormalizeColor(c);
            return new Color32(Byte(c.r),Byte(c.g),Byte(c.b),Byte(c.a));
        }
        private static byte Byte(float x) => (byte)Mathf.FloorToInt(Mathf.Clamp01(x)*255f+.5f);
        public static bool Same(Color a, Color b) => a.r == b.r && a.g == b.g && a.b == b.b && a.a == b.a;
        public static float Weight(float t, float bias, GradientCurve curve)
        {
            if (!Finite(t)) throw new ArgumentOutOfRangeException(nameof(t));
            bias = NormalizeBias(bias); t = Mathf.Clamp01(t);
            if (curve == GradientCurve.Linear) return t;
            if (curve != GradientCurve.Nonlinear) throw new ArgumentOutOfRangeException(nameof(curve));
            return t / ((1f / bias - 2f) * (1f - t) + 1f);
        }
        public static Color Evaluate(float t, Color start, Color end, float bias, GradientCurve curve)
        {
            start = NormalizeColor(start); end = NormalizeColor(end);
            return Color.LerpUnclamped(start, end, Weight(t, bias, curve));
        }
    }
}
