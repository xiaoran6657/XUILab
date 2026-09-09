using System;
using System.Collections.Generic;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.UI;

namespace XUILab.GradientLab.Tests
{
    public sealed class GradientAdaptiveTests
    {
        private GameObject root;
        private GradientEffect effect;
        [SetUp] public void SetUp()
        {
            root=new GameObject("AdaptiveTest",typeof(RectTransform),typeof(CanvasRenderer),typeof(Image));
            effect=root.AddComponent<GradientEffect>();
        }
        [TearDown] public void TearDown(){UnityEngine.Object.DestroyImmediate(root);}
        private static VertexHelper Quad(float width=100,float height=40,bool varying=false)
        {
            var vh=new VertexHelper();
            var points=new[]{new Vector2(0,0),new Vector2(0,height),new Vector2(width,height),new Vector2(width,0)};
            for(int i=0;i<4;i++)
            {
                var v=UIVertex.simpleVert;v.position=new Vector3(points[i].x,points[i].y,2);
                v.uv0=new Vector4(points[i].x/width,points[i].y/height,.3f,.6f);
                v.uv1=new Vector4(points[i].x,points[i].y,3,4);v.uv2=2*v.uv1;v.uv3=3*v.uv1;
                v.color=varying?new Color32((byte)(i*50),120,220,255):new Color32(255,255,255,255);
                vh.AddVert(v);
            }
            vh.AddTriangle(0,1,2);vh.AddTriangle(2,3,0);return vh;
        }
        private void Rebuild(float width=100,float height=40)
        {using(var vh=Quad(width,height))effect.ModifyMesh(vh);}
        [Test] public void InvalidConfigurationIsAtomicAndSameValuesDoNotDirty()
        {
            Assert.AreEqual(GradientSubdivisionMode.Fixed,effect.SubdivisionMode);
            Assert.AreEqual(1,effect.AdaptiveMinSegments);Assert.AreEqual(64,effect.AdaptiveMaxSegments);
            Assert.AreEqual(.01f,effect.AdaptiveTolerance);int dirty=effect.DirtyCount;
            effect.ConfigureAdaptive(1,64,.01f);effect.SubdivisionMode=GradientSubdivisionMode.Fixed;
            Assert.AreEqual(dirty,effect.DirtyCount);
            foreach(var bounds in new[]{new[]{0,64},new[]{1,65},new[]{3,2},new[]{-1,1},new[]{1,0}})
                Assert.Throws<ArgumentOutOfRangeException>(()=>effect.ConfigureAdaptive(bounds[0],bounds[1],.01f));
            foreach(float tolerance in new[]{0f,.000001f,1.01f,float.NaN,float.PositiveInfinity,float.NegativeInfinity})
                Assert.Throws<ArgumentOutOfRangeException>(()=>effect.ConfigureAdaptive(2,4,tolerance));
            Assert.Throws<ArgumentOutOfRangeException>(()=>effect.SubdivisionMode=(GradientSubdivisionMode)99);
            Assert.AreEqual(1,effect.AdaptiveMinSegments);Assert.AreEqual(64,effect.AdaptiveMaxSegments);
            Assert.AreEqual(.01f,effect.AdaptiveTolerance);Assert.AreEqual(dirty,effect.DirtyCount);
            effect.ConfigureAdaptive(2,4,.1f);Assert.AreEqual(dirty+1,effect.DirtyCount);
        }
        [Test] public void SelectorRejectsBadBuffersAndNonFiniteInputsBeforeWriting()
        {
            var positions=new float[65];var errors=new double[64];positions[0]=42;
            Assert.Throws<ArgumentException>(()=>GradientSegmentSelector.Select(Color.white,Color.black,.1f,GradientCurve.Nonlinear,1,64,.01f,positions,new double[1]));
            Assert.Throws<ArgumentOutOfRangeException>(()=>GradientSegmentSelector.Select(Color.white,Color.black,float.NaN,GradientCurve.Nonlinear,1,64,.01f,positions,errors));
            Assert.Throws<ArgumentOutOfRangeException>(()=>GradientSegmentSelector.Select(Color.white,Color.black,.1f,(GradientCurve)99,1,64,.01f,positions,errors));
            Assert.AreEqual(42,positions[0]);
        }
        [Test] public void DenseFloatOracleIsBoundedAcrossBiasColorAndTolerance()
        {
            var positions=new float[65];var errors=new double[64];var second=new float[65];var secondErrors=new double[64];
            foreach(float bias in new[]{.05f,.051f,.1f,.25f,.49999f,.5f,.50001f,.75f,.9f,.949f,.95f})
            foreach(float tolerance in new[]{.01f,.001f,.00001f})
            foreach(int minimum in new[]{1,3,7})
            {
                Color start=new Color(.9f,.1f,.7f,.2f),end=new Color(.05f,.8f,.4f,.95f);
                var result=GradientSegmentSelector.Select(start,end,bias,GradientCurve.Nonlinear,minimum,64,tolerance,positions,errors);
                var repeat=GradientSegmentSelector.Select(start,end,bias,GradientCurve.Nonlinear,minimum,64,tolerance,second,secondErrors);
                Assert.AreEqual(result.Segments,repeat.Segments);Assert.AreEqual(result.EstimatedMaxError,repeat.EstimatedMaxError);
                Assert.That(result.Segments,Is.InRange(minimum,64));Assert.AreEqual(0,positions[0]);Assert.AreEqual(1,positions[result.Segments]);
                double max=0;
                for(int s=0;s<result.Segments;s++)
                {
                    Assert.Greater(positions[s+1],positions[s]);Assert.AreEqual(positions[s],second[s]);
                    Color left=GradientFunction.Evaluate(positions[s],start,end,bias,GradientCurve.Nonlinear);
                    Color right=GradientFunction.Evaluate(positions[s+1],start,end,bias,GradientCurve.Nonlinear);
                    for(int j=0;j<=128;j++)
                    {
                        float t=Mathf.Lerp(positions[s],positions[s+1],j/128f);
                        Color chord=Color.LerpUnclamped(left,right,(t-positions[s])/(positions[s+1]-positions[s]));
                        Color exact=GradientFunction.Evaluate(t,start,end,bias,GradientCurve.Nonlinear);
                        for(int c=0;c<4;c++)max=Math.Max(max,Math.Abs(chord[c]-exact[c]));
                    }
                }
                Assert.LessOrEqual(max,result.EstimatedMaxError,"bias="+bias+" tolerance="+tolerance);
                Assert.AreEqual(result.EstimatedMaxError>tolerance,result.QualityLimited);
                if(result.QualityLimited)Assert.AreEqual(64,result.Segments);
            }
        }
        [Test] public void ConstantCenterLinearAndCapHaveExplicitOutcomes()
        {
            var positions=new float[65];var errors=new double[64];
            var constant=GradientSegmentSelector.Select(Color.red,Color.red,.05f,GradientCurve.Nonlinear,3,64,.00001f,positions,errors);
            Assert.AreEqual(3,constant.Segments);Assert.AreEqual(0,constant.EstimatedMaxError);Assert.False(constant.QualityLimited);
            var linear=GradientSegmentSelector.Select(Color.white,Color.black,.05f,GradientCurve.Linear,1,64,.00001f,positions,errors);
            Assert.AreEqual(1,linear.Segments);Assert.False(linear.QualityLimited);
            var center=GradientSegmentSelector.Select(Color.white,Color.black,.5f,GradientCurve.Nonlinear,1,64,.00001f,positions,errors);
            Assert.AreEqual(1,center.Segments);Assert.False(center.QualityLimited);
            var capped=GradientSegmentSelector.Select(Color.white,Color.black,.05f,GradientCurve.Nonlinear,1,4,.01f,positions,errors);
            Assert.AreEqual(4,capped.Segments);Assert.True(capped.QualityLimited);Assert.Greater(capped.EstimatedMaxError,.01);
        }
        [TestCase(.05f)] [TestCase(.5f)] [TestCase(.95f)]
        public void ActualMeshPreservesSharedTopologyAttributesAndQuantizedQuality(float bias)
        {
            effect.SubdivisionMode=GradientSubdivisionMode.Adaptive;effect.Bias=bias;
            foreach(var size in new[]{new Vector2(100,40),new Vector2(960,540)})
            foreach(GradientDirection direction in Enum.GetValues(typeof(GradientDirection)))
            using(var vh=Quad(size.x,size.y))
            {
                effect.Direction=direction;effect.ModifyMesh(vh);int segments=effect.SelectedSegments;
                Assert.AreEqual(GradientMeshMode.AdaptiveSegments,effect.LastMode);Assert.True(effect.HasGradientEstimate);Assert.True(effect.OutputQualityAssessed);
                Assert.False(effect.GradientQualityLimited);Assert.AreEqual(2*(segments+1),vh.currentVertCount);Assert.AreEqual(6*segments,vh.currentIndexCount);
                var vertices=new UIVertex[2*(segments+1)];
                for(int i=0;i<vertices.Length;i++)
                {
                    vh.PopulateUIVertex(ref vertices[i],i);var v=vertices[i];
                    Assert.That(v.uv1,Is.EqualTo(new Vector4(v.position.x,v.position.y,3,4)));
                    Assert.That(v.uv2,Is.EqualTo(2*v.uv1));Assert.That(v.uv3,Is.EqualTo(3*v.uv1));
                    float t=direction==GradientDirection.Horizontal?v.position.x/size.x:v.position.y/size.y;
                    Assert.AreEqual(GradientFunction.Quantize(effect.Evaluate(t)),v.color);
                }
                var triangles=new List<UIVertex>();vh.GetUIVertexStream(triangles);double area=0;
                for(int i=0;i<triangles.Count;i+=3)
                {
                    var a=triangles[i+1].position-triangles[i].position;var b=triangles[i+2].position-triangles[i].position;
                    double cross=a.x*b.y-a.y*b.x;Assert.Less(cross,0);area-=cross*.5;
                }
                Assert.That(area,Is.EqualTo(size.x*size.y).Within(.1));
                int section=0;double max=0;
                for(int i=0;i<=4096;i++)
                {
                    float t=i/4096f;
                    while(section<segments-1 && t>Coordinate(vertices[2*(section+1)],size,direction))section++;
                    float left=Coordinate(vertices[2*section],size,direction),right=Coordinate(vertices[2*(section+1)],size,direction);
                    Assert.Greater(right,left);
                    Color actual=Color.LerpUnclamped(vertices[2*section].color,vertices[2*(section+1)].color,(t-left)/(right-left));
                    Color exact=effect.Evaluate(t);
                    for(int c=0;c<4;c++)max=Math.Max(max,Math.Abs(actual[c]-exact[c]));
                }
                Assert.LessOrEqual(max,effect.EstimatedGradientError+.5/255+2e-6);
            }
        }
        private static float Coordinate(UIVertex v,Vector2 size,GradientDirection direction)=>direction==GradientDirection.Horizontal?v.position.x/size.x:v.position.y/size.y;
        [Test] public void CacheIncludesEverySelectionInputButReusesForGeometryAndDirection()
        {
            effect.SubdivisionMode=GradientSubdivisionMode.Adaptive;effect.Bias=.05f;Rebuild();Assert.AreEqual(1,effect.SelectionCount);
            Rebuild();effect.Direction=GradientDirection.Vertical;Rebuild(200,80);
            Assert.AreEqual(1,effect.SelectionCount);Assert.AreEqual(2,effect.SelectionCacheHits);
            Action[] changes={ ()=>effect.Bias=.1f,()=>effect.StartColor=Color.red,()=>effect.EndColor=Color.blue,
                ()=>effect.AdaptiveMinSegments=2,()=>effect.AdaptiveMaxSegments=32,()=>effect.AdaptiveTolerance=.001f };
            int count=1;foreach(var change in changes){change();Rebuild();Assert.AreEqual(++count,effect.SelectionCount);}
            effect.Curve=GradientCurve.Linear;Rebuild();Assert.AreEqual(GradientMeshMode.LinearVertices,effect.LastMode);Assert.False(effect.HasGradientEstimate);
            effect.Bias=.3f;effect.Curve=GradientCurve.Nonlinear;Rebuild();Assert.AreEqual(++count,effect.SelectionCount);
            effect.SubdivisionMode=GradientSubdivisionMode.Fixed;Rebuild();Assert.AreEqual(32,effect.SelectedSegments);Assert.False(effect.HasGradientEstimate);
            effect.SubdivisionMode=GradientSubdivisionMode.Adaptive;Rebuild();Assert.AreEqual(count,effect.SelectionCount);
        }
        [Test] public void FallbackAndVaryingBaseColorNeverClaimOutputQuality()
        {
            effect.SubdivisionMode=GradientSubdivisionMode.Adaptive;effect.Bias=.05f;
            using(var vh=Quad(varying:true)){effect.ModifyMesh(vh);Assert.True(effect.HasGradientEstimate);Assert.False(effect.OutputQualityAssessed);}
            root.GetComponent<Image>().type=Image.Type.Filled;
            Rebuild();Assert.AreEqual(GradientMeshMode.VertexFallback,effect.LastMode);Assert.False(effect.HasGradientEstimate);Assert.False(effect.OutputQualityAssessed);
            using(var vh=new VertexHelper()){effect.ModifyMesh(vh);Assert.AreEqual(GradientMeshMode.Empty,effect.LastMode);Assert.False(effect.HasGradientEstimate);}
            root.GetComponent<Image>().type=Image.Type.Simple;effect.enabled=false;Rebuild();Assert.AreEqual(GradientMeshMode.Disabled,effect.LastMode);Assert.False(effect.HasGradientEstimate);
        }
    }
}
