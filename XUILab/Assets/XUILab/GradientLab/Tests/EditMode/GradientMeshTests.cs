using System;
using System.Collections.Generic;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.UI;

namespace XUILab.GradientLab.Tests
{
    public sealed class GradientMeshTests
    {
        private GameObject root;
        private GradientEffect effect;
        [SetUp] public void SetUp(){root=new GameObject("GradientTest",typeof(RectTransform),typeof(CanvasRenderer),typeof(Image));effect=root.AddComponent<GradientEffect>();effect.StartColor=effect.EndColor=Color.white;}
        [TearDown] public void TearDown(){UnityEngine.Object.DestroyImmediate(root);}
        private static UIVertex Vertex(float x,float y)
        {
            var v=UIVertex.simpleVert;v.position=new Vector3(x,y,2);v.uv0=new Vector4(x/100,y/40,.3f,.6f);
            v.uv1=new Vector4(x,y,3,4);v.uv2=new Vector4(2*x,2*y,5,6);v.uv3=new Vector4(3*x,3*y,7,8);
            v.normal=new Vector3(x/100,.2f,-1);v.tangent=new Vector4(x/100,y/40,.2f,-1);v.color=new Color32(103,151,207,83);return v;
        }
        private static VertexHelper Quad(bool alternate=false,bool reverse=false,bool reorder=false)
        {
            var vh=new VertexHelper();var vertices=new[]{Vertex(0,0),Vertex(0,40),Vertex(100,40),Vertex(100,0)};
            var order=reorder?new[]{2,0,3,1}:new[]{0,1,2,3};var map=new int[4];
            for(int i=0;i<4;i++){vh.AddVert(vertices[order[i]]);map[order[i]]=i;}
            var indices=alternate?new[]{0,1,3,1,2,3}:new[]{0,1,2,2,3,0};
            for(int i=0;i<6;i+=3)vh.AddTriangle(map[indices[i]],map[indices[i+(reverse?2:1)]],map[indices[i+(reverse?1:2)]]);
            return vh;
        }
        [Test] public void FixedSegmentSettingIsBoundedAtomicAndDefaultsTo32()
        {
            Assert.AreEqual(32,effect.FixedSegments);int dirty=effect.DirtyCount;
            effect.FixedSegments=32;Assert.AreEqual(dirty,effect.DirtyCount);
            foreach(int invalid in new[]{int.MinValue,0,65,int.MaxValue})
            {Assert.Throws<ArgumentOutOfRangeException>(()=>effect.FixedSegments=invalid);Assert.AreEqual(32,effect.FixedSegments);Assert.AreEqual(dirty,effect.DirtyCount);}
            foreach(int count in new[]{1,8,16,32,64})foreach(GradientDirection direction in Enum.GetValues(typeof(GradientDirection)))
            using(var vh=Quad(true,true,true))
            {
                effect.FixedSegments=count;effect.Direction=direction;effect.ModifyMesh(vh);
                Assert.AreEqual(2*(count+1),vh.currentVertCount);Assert.AreEqual(6*count,vh.currentIndexCount);Assert.AreEqual(count,effect.SelectedSegments);
                var stream=new List<UIVertex>();vh.GetUIVertexStream(stream);double area=0;
                for(int i=0;i<stream.Count;i+=3){var a=stream[i+1].position-stream[i].position;var b=stream[i+2].position-stream[i].position;double cross=a.x*b.y-a.y*b.x;Assert.Greater(cross,0);area+=cross*.5;}
                Assert.That(area,Is.EqualTo(4000).Within(.02));
                UIVertex previous=default(UIVertex),v=default(UIVertex);vh.PopulateUIVertex(ref previous,0);
                for(int i=1;i<=count;i++){vh.PopulateUIVertex(ref v,2*i);Assert.Greater(direction==GradientDirection.Horizontal?v.position.x:v.position.y,direction==GradientDirection.Horizontal?previous.position.x:previous.position.y);previous=v;}
            }
        }
        [TestCase(.05f)] [TestCase(.25f)] [TestCase(.5f)] [TestCase(.75f)] [TestCase(.95f)]
        public void CurveHasFixedEndpointsCenterAndMonotonicity(float b)
        {
            Assert.AreEqual(0,GradientFunction.Weight(0,b,GradientCurve.Nonlinear));Assert.AreEqual(1,GradientFunction.Weight(1,b,GradientCurve.Nonlinear));
            Assert.That(GradientFunction.Weight(.5f,b,GradientCurve.Nonlinear),Is.EqualTo(b).Within(1e-6));
            float prior=0;for(int i=0;i<=4096;i++){float x=GradientFunction.Weight(i/4096f,b,GradientCurve.Nonlinear);Assert.That(x,Is.GreaterThanOrEqualTo(prior));prior=x;}
        }
        [Test] public void QuantizeRejectsEveryNonFiniteChannelAndClampsFiniteValues()
        {
            foreach(float invalid in new[]{float.NaN,float.PositiveInfinity,float.NegativeInfinity})
            for(int channel=0;channel<4;channel++)
            {
                var color=Color.white;color[channel]=invalid;
                Assert.Throws<ArgumentOutOfRangeException>(()=>GradientFunction.Quantize(color));
            }
            Assert.AreEqual(new Color32(0,255,128,0),GradientFunction.Quantize(new Color(-2,3,.5f,-1)));
        }
        [Test] public void NonFiniteParametersRejectWithoutChangingState()
        {
            var prior=effect.Bias;Assert.Throws<ArgumentOutOfRangeException>(()=>effect.Bias=float.NaN);Assert.AreEqual(prior,effect.Bias);
            Assert.Throws<ArgumentOutOfRangeException>(()=>effect.StartColor=new Color(float.PositiveInfinity,0,0));
            Assert.Throws<ArgumentOutOfRangeException>(()=>GradientFunction.Weight(float.NaN,.5f,GradientCurve.Linear));
        }
        [TestCase(false,false,false)] [TestCase(true,false,false)] [TestCase(false,true,false)] [TestCase(true,true,true)]
        public void FixedRectangleHasSharedSectionsChannelsAndOriginalWinding(bool alternate,bool reverse,bool reorder)
        {
            foreach(GradientDirection direction in Enum.GetValues(typeof(GradientDirection)))using(var vh=Quad(alternate,reverse,reorder))
            {
                effect.Direction=direction;effect.Bias=.2f;effect.ModifyMesh(vh);
                Assert.AreEqual(GradientMeshMode.FixedSegments,effect.LastMode);Assert.AreEqual(66,vh.currentVertCount);Assert.AreEqual(192,vh.currentIndexCount);
                var v=default(UIVertex);vh.PopulateUIVertex(ref v,32);
                Assert.That(v.position,Is.EqualTo(direction==GradientDirection.Horizontal?new Vector3(50,0,2):new Vector3(0,20,2)));
                Assert.That(v.uv1,Is.EqualTo(new Vector4(v.position.x,v.position.y,3,4)));
                Assert.That(v.uv2,Is.EqualTo(new Vector4(2*v.position.x,2*v.position.y,5,6)));
                Assert.That(v.uv3,Is.EqualTo(new Vector4(3*v.position.x,3*v.position.y,7,8)));
                Assert.That(v.uv0,Is.EqualTo(new Vector4(v.position.x/100,v.position.y/40,.3f,.6f)));
                Assert.That(v.tangent,Is.EqualTo(new Vector4(v.position.x/100,v.position.y/40,.2f,-1)));
                Assert.That(v.normal,Is.EqualTo(new Vector3(v.position.x/100,.2f,-1)));Assert.AreEqual(83,v.color.a);
                var triangles=new List<UIVertex>();vh.GetUIVertexStream(triangles);float area=0;
                for(int i=0;i<triangles.Count;i+=3){var ab=triangles[i+1].position-triangles[i].position;var ac=triangles[i+2].position-triangles[i].position;float cross=ab.x*ac.y-ab.y*ac.x;Assert.AreEqual(!reverse,cross<0);area+=Mathf.Abs(cross)*.5f;}
                Assert.That(area,Is.EqualTo(4000).Within(.01));
            }
        }
        [Test] public void LinearPreservesTopologyAndMultipliesInputAlphaOnce()
        {
            effect.Curve=GradientCurve.Linear;effect.StartColor=effect.EndColor=new Color(.5f,.5f,.5f,.5f);
            using(var vh=Quad()){effect.ModifyMesh(vh);Assert.AreEqual(4,vh.currentVertCount);Assert.AreEqual(6,vh.currentIndexCount);var v=default(UIVertex);vh.PopulateUIVertex(ref v,0);Assert.AreEqual(42,v.color.a);Assert.AreEqual(52,v.color.r);Assert.AreEqual(new Vector4(0,0,.3f,.6f),v.uv0);}
        }
        [TestCase(Image.Type.Sliced)] [TestCase(Image.Type.Tiled)] [TestCase(Image.Type.Filled)]
        public void UnsupportedImageTypesKeepTopology(Image.Type type)
        {
            root.GetComponent<Image>().type=type;using(var vh=Quad()){effect.ModifyMesh(vh);Assert.AreEqual(GradientMeshMode.VertexFallback,effect.LastMode);Assert.AreEqual(4,vh.currentVertCount);}
        }
        [Test] public void DuplicateTriangleAndNonAffineUvsFallBack()
        {
            using(var vh=Quad()){var vertices=new List<UIVertex>();vh.GetUIVertexStream(vertices);vh.Clear();for(int i=0;i<3;i++)vh.AddVert(vertices[i]);vh.AddVert(Vertex(100,0));vh.AddTriangle(0,1,2);vh.AddTriangle(0,1,2);effect.ModifyMesh(vh);Assert.AreEqual(GradientMeshMode.VertexFallback,effect.LastMode);}
            using(var vh=Quad()){var v=default(UIVertex);vh.PopulateUIVertex(ref v,2);v.uv0.x+=.1f;vh.SetUIVertex(v,2);effect.ModifyMesh(vh);Assert.AreEqual(GradientMeshMode.VertexFallback,effect.LastMode);}
        }
        [Test] public void ConstantUvIsLegalButSkewAndNonFiniteChannelsAreNotSubdivided()
        {
            using(var vh=Quad()){var v=default(UIVertex);for(int i=0;i<4;i++){vh.PopulateUIVertex(ref v,i);v.uv0=Vector4.zero;vh.SetUIVertex(v,i);}effect.ModifyMesh(vh);Assert.AreEqual(66,vh.currentVertCount);}
            using(var vh=Quad()){var v=default(UIVertex);vh.PopulateUIVertex(ref v,2);v.position.x-=1;vh.SetUIVertex(v,2);effect.ModifyMesh(vh);Assert.AreEqual(GradientMeshMode.VertexFallback,effect.LastMode);}
            using(var vh=Quad()){var v=default(UIVertex);vh.PopulateUIVertex(ref v,2);v.uv3.w=float.NaN;vh.SetUIVertex(v,2);effect.ModifyMesh(vh);Assert.AreEqual(GradientMeshMode.InvalidInput,effect.LastMode);Assert.AreEqual(4,vh.currentVertCount);}
        }
        [Test] public void EmptyDegenerateAndDisabledDoNotCreateGeometry()
        {
            using(var vh=new VertexHelper()){effect.ModifyMesh(vh);Assert.AreEqual(GradientMeshMode.Empty,effect.LastMode);}
            using(var vh=Quad()){var v=default(UIVertex);for(int i=0;i<4;i++){vh.PopulateUIVertex(ref v,i);v.position.x=0;vh.SetUIVertex(v,i);}effect.ModifyMesh(vh);Assert.AreEqual(GradientMeshMode.Degenerate,effect.LastMode);Assert.AreEqual(4,vh.currentVertCount);}
            using(var vh=Quad()){effect.enabled=false;effect.ModifyMesh(vh);Assert.AreEqual(GradientMeshMode.Disabled,effect.LastMode);Assert.AreEqual(4,vh.currentVertCount);}
        }
        [Test] public void SameNormalizedValuesNeverMarkVerticesDirty()
        {
            int dirty=0;root.GetComponent<Image>().RegisterDirtyVerticesCallback(()=>dirty++);
            for(int i=0;i<100;i++){effect.Bias=effect.Bias;effect.StartColor=effect.StartColor;effect.EndColor=effect.EndColor;effect.Curve=effect.Curve;effect.Direction=effect.Direction;}
            Assert.AreEqual(0,dirty);effect.Bias=100;Assert.AreEqual(1,dirty);effect.Bias=2;Assert.AreEqual(1,dirty);
        }
        [Test] public void SubdivisionQuantizesOnlyAfterInterpolationAndMultiplication()
        {
            effect.StartColor=effect.EndColor=new Color(.3f,1,1,1);
            using(var vh=Quad()){var v=default(UIVertex);for(int i=0;i<4;i++){vh.PopulateUIVertex(ref v,i);v.color=new Color32((byte)(v.position.x==0?0:3),0,0,255);vh.SetUIVertex(v,i);}effect.ModifyMesh(vh);vh.PopulateUIVertex(ref v,32);Assert.AreEqual(0,v.color.r);}
        }
    }
}
