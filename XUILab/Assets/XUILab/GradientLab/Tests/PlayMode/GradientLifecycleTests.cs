using System;
using System.Collections;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.TestTools;
using UnityEngine.UI;

namespace XUILab.GradientLab.Tests
{
    public sealed class GradientLifecycleTests
    {
        private GameObject root;
        private GradientEffect effect;
        private GradientTransitionController controller;
        [UnitySetUp] public IEnumerator SetUp()
        {
            root=new GameObject("GradientCanvas",typeof(Canvas));root.GetComponent<Canvas>().renderMode=RenderMode.ScreenSpaceOverlay;
            var item=new GameObject("Gradient",typeof(RectTransform),typeof(Image));item.transform.SetParent(root.transform,false);
            ((RectTransform)item.transform).sizeDelta=new Vector2(300,180);effect=item.AddComponent<GradientEffect>();controller=item.AddComponent<GradientTransitionController>();controller.Automatic=false;yield return null;
        }
        [UnityTearDown] public IEnumerator TearDown(){UnityEngine.Object.Destroy(root);yield return null;}
        [UnityTest] public IEnumerator CanvasRebuildUsesSharedMaterialAndRepeatedAssignmentStaysIdle()
        {
            effect.Bias=.25f;Canvas.ForceUpdateCanvases();yield return null;
            Assert.AreEqual(66,effect.LastVertexCount);Assert.AreEqual(GradientMeshMode.FixedSegments,effect.LastMode);
            var image=effect.GetComponent<Image>();var material=image.material;int rebuilds=effect.RebuildCount;
            for(int i=0;i<3;i++){effect.Bias=.25f;yield return null;}
            Assert.AreEqual(rebuilds,effect.RebuildCount);Assert.AreSame(material,image.material);
            effect.Bias=.75f;yield return null;Assert.Greater(effect.RebuildCount,rebuilds);
        }
        [UnityTest] public IEnumerator AdaptiveCacheSurvivesGeometryChangesAndReenableWithoutStaleMesh()
        {
            effect.SubdivisionMode=GradientSubdivisionMode.Adaptive;effect.Bias=.05f;
            Canvas.ForceUpdateCanvases();yield return null;
            int selects=effect.SelectionCount,rebuilds=effect.RebuildCount;
            Assert.Greater(selects,0);Assert.AreEqual(GradientMeshMode.AdaptiveSegments,effect.LastMode);
            for(int i=0;i<3;i++){effect.ConfigureAdaptive(1,64,.01f);effect.Bias=.05f;yield return null;}
            Assert.AreEqual(rebuilds,effect.RebuildCount);Assert.AreEqual(selects,effect.SelectionCount);
            ((RectTransform)effect.transform).sizeDelta=new Vector2(600,240);effect.Direction=GradientDirection.Vertical;
            Canvas.ForceUpdateCanvases();yield return null;
            Assert.AreEqual(selects,effect.SelectionCount);Assert.Greater(effect.SelectionCacheHits,0);
            effect.enabled=false;Canvas.ForceUpdateCanvases();yield return null;
            Mesh mesh=null;
            try
            {
                if(mesh)UnityEngine.Object.Destroy(mesh);mesh=UnityEngine.Object.Instantiate(effect.GetComponent<CanvasRenderer>().GetMesh());Assert.AreEqual(4,mesh.vertexCount);
                effect.Bias=.95f;effect.enabled=true;Canvas.ForceUpdateCanvases();yield return null;
                Assert.AreEqual(selects+1,effect.SelectionCount);Assert.AreEqual(GradientMeshMode.AdaptiveSegments,effect.LastMode);
                if(mesh)UnityEngine.Object.Destroy(mesh);mesh=UnityEngine.Object.Instantiate(effect.GetComponent<CanvasRenderer>().GetMesh());Assert.AreEqual(2*(effect.SelectedSegments+1),mesh.vertexCount);
                Assert.AreEqual(6*effect.SelectedSegments,mesh.triangles.Length);
                effect.ConfigureAdaptive(1,4,.01f);Canvas.ForceUpdateCanvases();yield return null;
                Assert.True(effect.GradientQualityLimited);Assert.AreEqual(4,effect.SelectedSegments);
                effect.SubdivisionMode=GradientSubdivisionMode.Fixed;Canvas.ForceUpdateCanvases();yield return null;
                if(mesh)UnityEngine.Object.Destroy(mesh);mesh=UnityEngine.Object.Instantiate(effect.GetComponent<CanvasRenderer>().GetMesh());Assert.AreEqual(66,mesh.vertexCount);Assert.False(effect.HasGradientEstimate);
            }
            finally{UnityEngine.Object.Destroy(mesh);}
        }
        [UnityTest] public IEnumerator TransitionInterruptCancelAndReuseHaveStableTerminals()
        {
            controller.StartTransition(.1f,.9f,1);controller.SetProgress(.5f);Assert.That(effect.Bias,Is.EqualTo(.5f).Within(1e-6));
            controller.StartTransition(.8f,.2f,1);controller.SetProgress(.5f);controller.Cancel();float saved=effect.Bias;
            controller.SetProgress(1);Assert.AreEqual(saved,effect.Bias);Assert.AreEqual(GradientEndReason.Cancelled,controller.EndReason);
            controller.StartTransition(.1f,.9f,1);controller.SetProgress(.25f);saved=effect.Bias;controller.enabled=false;yield return null;
            Assert.False(controller.IsRunning);Assert.AreEqual(GradientEndReason.Disabled,controller.EndReason);controller.enabled=true;yield return null;Assert.AreEqual(saved,effect.Bias);
            controller.StartTransition(.9f,.1f,0);Assert.AreEqual(1,controller.Progress);Assert.AreEqual(.1f,effect.Bias);Assert.AreEqual(GradientEndReason.Completed,controller.EndReason);
            controller.StartTransition(.1f,.9f,1);controller.Cancel(true);Assert.AreEqual(.9f,effect.Bias);Assert.False(controller.IsRunning);
        }
        [UnityTest] public IEnumerator InvalidStartAndProgressCannotPartiallyMutateAnActiveTransition()
        {
            controller.StartTransition(.1f,.9f,1);controller.SetProgress(.25f);float before=effect.Bias;
            Assert.Throws<ArgumentOutOfRangeException>(()=>controller.StartTransition(.2f,.8f,float.NaN));
            Assert.Throws<ArgumentOutOfRangeException>(()=>controller.SetProgress(float.PositiveInfinity));Assert.AreEqual(before,effect.Bias);Assert.True(controller.IsRunning);
            controller.SetProgress(1);yield return null;Assert.AreEqual(GradientEndReason.Completed,controller.EndReason);
        }
        [UnityTest] public IEnumerator SmoothStepNegativeDurationAndDestroyTerminateWithoutFurtherWrites()
        {
            controller.Easing=GradientEasing.SmoothStep;controller.StartTransition(.1f,.9f,1);controller.SetProgress(.25f);
            Assert.That(effect.Bias,Is.EqualTo(.225f).Within(1e-6));
            controller.StartTransition(-1,2,-1);Assert.AreEqual(.95f,effect.Bias);Assert.AreEqual(1,controller.Progress);Assert.False(controller.IsRunning);
            controller.StartTransition(.1f,.9f,1);controller.SetProgress(.25f);float before=effect.Bias;
            UnityEngine.Object.Destroy(controller);yield return null;yield return null;
            Assert.AreEqual(before,effect.Bias);Assert.IsNull(effect.GetComponent<GradientTransitionController>());
        }
        [UnityTest] public IEnumerator UnscaledAutomaticProgressEndsWhileScaledClockIsPaused()
        {
            float old=Time.timeScale;
            try{Time.timeScale=0;controller.Automatic=true;controller.Clock=GradientClock.Scaled;controller.StartTransition(.1f,.9f,.02f);yield return null;yield return null;Assert.AreEqual(0,controller.Progress);
                controller.Clock=GradientClock.Unscaled;for(int i=0;i<120&&controller.IsRunning;i++)yield return null;Assert.False(controller.IsRunning);Assert.AreEqual(.9f,effect.Bias);}
            finally{Time.timeScale=old;}
        }
    }
}
