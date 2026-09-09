using System;
using UnityEngine;

namespace XUILab.GradientLab
{
    public enum GradientClock { Unscaled, Scaled }
    public enum GradientEasing { Linear, SmoothStep }
    public enum GradientEndReason { None, Completed, Cancelled, Disabled }

    [DisallowMultipleComponent, RequireComponent(typeof(GradientEffect))]
    public sealed class GradientTransitionController : MonoBehaviour
    {
        private GradientClock clock;
        public GradientClock Clock { get=>clock; set { if(value!=GradientClock.Unscaled && value!=GradientClock.Scaled)throw new ArgumentOutOfRangeException(nameof(value));clock=value; } }
        private GradientEasing easing;
        public GradientEasing Easing { get=>easing;set { if(value!=GradientEasing.Linear && value!=GradientEasing.SmoothStep)throw new ArgumentOutOfRangeException(nameof(value));easing=value;} }
        public bool Automatic { get; set; } = true;
        public bool IsRunning { get; private set; }
        public float Progress { get; private set; }
        public GradientEndReason EndReason { get; private set; }
        public float CurrentBias => effect ? effect.Bias : GetComponent<GradientEffect>().Bias;
        private GradientEffect effect;
        private float from, to, duration, elapsed;

        public void StartTransition(float startBias, float endBias, float seconds)
        {
            startBias = GradientFunction.NormalizeBias(startBias);
            endBias = GradientFunction.NormalizeBias(endBias);
            if (!GradientFunction.Finite(seconds)) throw new ArgumentOutOfRangeException(nameof(seconds));
            if (!isActiveAndEnabled) throw new InvalidOperationException("Controller must be enabled to start.");
            if (!effect) effect = GetComponent<GradientEffect>();
            if (!effect) throw new InvalidOperationException("GradientEffect is required.");
            from = startBias; to = endBias; duration = seconds; elapsed = 0; Progress = 0;
            effect.Bias = from; IsRunning = true; EndReason=GradientEndReason.None;
            if (duration <= 0) SetProgress(1);
        }
        public void SetProgress(float value)
        {
            if (!GradientFunction.Finite(value)) throw new ArgumentOutOfRangeException(nameof(value));
            if (!IsRunning) return;
            if (!effect) { IsRunning = false; return; }
            Progress = Mathf.Clamp01(value); elapsed = Mathf.Max(0, duration) * Progress;
            float eased = Easing == GradientEasing.SmoothStep ? Progress * Progress * (3 - 2 * Progress) : Progress;
            effect.Bias = Mathf.LerpUnclamped(from, to, eased);
            if (Progress >= 1) { IsRunning = false; EndReason=GradientEndReason.Completed; }
        }
        public void Cancel(bool complete = false)
        {
            if(!IsRunning)return;
            if (complete) { SetProgress(1); return; }
            IsRunning = false; EndReason=GradientEndReason.Cancelled;
        }
        private void Update()
        {
            if (!Automatic || !IsRunning) return;
            float delta = Clock == GradientClock.Scaled ? Time.deltaTime : Time.unscaledDeltaTime;
            SetProgress(duration <= 0 ? 1 : (elapsed + delta) / duration);
        }
        private void StopDisabled() { if(IsRunning){IsRunning=false;EndReason=GradientEndReason.Disabled;} }
        private void OnDisable() => StopDisabled();
        private void OnDestroy() => StopDisabled();
    }
}
