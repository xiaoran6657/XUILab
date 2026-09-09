using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

namespace XUILab.GradientLab
{
    [DisallowMultipleComponent, AddComponentMenu("UI/Effects/XUILab Gradient")]
    public sealed class GradientEffect : BaseMeshEffect
    {
        public const int BaselineSegments = 32;
        public const int MaximumSegments = 64;
        [SerializeField, Range(1, MaximumSegments)] private int fixedSegments = BaselineSegments;
        public int FixedSegments { get => fixedSegments; set { if(value<1 || value>MaximumSegments)throw new ArgumentOutOfRangeException(nameof(value)); if(value==fixedSegments)return;fixedSegments=value;Dirty(); } }
        [SerializeField] private GradientSubdivisionMode subdivisionMode;
        [SerializeField] private int adaptiveMinSegments=1, adaptiveMaxSegments=MaximumSegments;
        [SerializeField] private float adaptiveTolerance=.01f;
        public GradientSubdivisionMode SubdivisionMode
        {
            get=>subdivisionMode;
            set { if(value!=GradientSubdivisionMode.Fixed && value!=GradientSubdivisionMode.Adaptive)throw new ArgumentOutOfRangeException(nameof(value));if(value==subdivisionMode)return;subdivisionMode=value;Dirty(); }
        }
        public int AdaptiveMinSegments { get=>adaptiveMinSegments; set=>ConfigureAdaptive(value,adaptiveMaxSegments,adaptiveTolerance); }
        public int AdaptiveMaxSegments { get=>adaptiveMaxSegments; set=>ConfigureAdaptive(adaptiveMinSegments,value,adaptiveTolerance); }
        public float AdaptiveTolerance { get=>adaptiveTolerance; set=>ConfigureAdaptive(adaptiveMinSegments,adaptiveMaxSegments,value); }
        public void ConfigureAdaptive(int minimum,int maximum,float tolerance)
        {
            GradientSegmentSelector.Validate(minimum,maximum,tolerance);
            if(minimum==adaptiveMinSegments && maximum==adaptiveMaxSegments && tolerance==adaptiveTolerance)return;
            adaptiveMinSegments=minimum;adaptiveMaxSegments=maximum;adaptiveTolerance=tolerance;Dirty();
        }
        public int SelectionCount { get; private set; }
        public int SelectionCacheHits { get; private set; }
        public long SelectionTicks { get; private set; }
        public bool HasGradientEstimate { get; private set; }
        public double EstimatedGradientError { get; private set; }
        public bool GradientQualityLimited { get; private set; }
        /// <summary>Uniform base color permits an unquantized vertex-gradient bound; excludes Color32 and texture/shader/pixel errors.</summary>
        public bool OutputQualityAssessed { get; private set; }
        private float[] adaptivePositions;
        private double[] adaptiveErrors;
        private bool selectionCached;
        private Color cachedStart,cachedEnd;
        private float cachedBias,cachedTolerance;
        private int cachedMinimum,cachedMaximum;
        private GradientCurve cachedCurve;
        private GradientSelectionResult cachedSelection;
        [SerializeField] private Color startColor = Color.white;
        [SerializeField] private Color endColor = Color.black;
        [SerializeField, Range(.05f, .95f)] private float bias = .5f;
        [SerializeField] private GradientDirection direction;
        [SerializeField] private GradientCurve curve = GradientCurve.Nonlinear;
        public Color StartColor { get => startColor; set { value = GradientFunction.NormalizeColor(value); if (GradientFunction.Same(value,startColor)) return; startColor=value; Dirty(); } }
        public Color EndColor { get => endColor; set { value = GradientFunction.NormalizeColor(value); if (GradientFunction.Same(value,endColor)) return; endColor=value; Dirty(); } }
        public float Bias { get => bias; set { value=GradientFunction.NormalizeBias(value); if(value==bias)return; bias=value;Dirty(); } }
        public GradientDirection Direction { get => direction; set { if(value!=GradientDirection.Horizontal && value!=GradientDirection.Vertical)throw new ArgumentOutOfRangeException(nameof(value)); if(value==direction)return;direction=value;Dirty(); } }
        public GradientCurve Curve { get => curve; set { if(value!=GradientCurve.Linear && value!=GradientCurve.Nonlinear)throw new ArgumentOutOfRangeException(nameof(value));if(value==curve)return;curve=value;Dirty(); } }
        public GradientMeshMode LastMode { get; private set; }
        public int LastVertexCount { get; private set; }
        public int LastTriangleCount { get; private set; }
        public int SelectedSegments { get; private set; }
        public int DirtyCount { get; private set; }
        public int RebuildCount { get; private set; }
        private readonly UIVertex[] corners = new UIVertex[4]; // BL, TL, TR, BR
        private readonly List<UIVertex> stream = new List<UIVertex>(6);
        private readonly int[] triangleCorners = new int[6];
        private readonly int[] uses = new int[4];
        private bool clockwise;
        private float minX, minY, maxX, maxY;

        private static bool SameColor32(Color32 a,Color32 b)=>a.r==b.r && a.g==b.g && a.b==b.b && a.a==b.a;
        private void Dirty() { DirtyCount++; if(graphic)graphic.SetVerticesDirty(); }
        public Color Evaluate(float t) => GradientFunction.Evaluate(t,startColor,endColor,bias,curve);
        public override void ModifyMesh(VertexHelper vh)
        {
            LastVertexCount=vh.currentVertCount;LastTriangleCount=vh.currentIndexCount/3;SelectedSegments=0;
            HasGradientEstimate=false;EstimatedGradientError=0;GradientQualityLimited=false;OutputQualityAssessed=false;
            if(!IsActive()){LastMode=GradientMeshMode.Disabled;return;}
            RebuildCount++;
            if(vh.currentVertCount==0){LastMode=GradientMeshMode.Empty;return;}
            minX=minY=float.PositiveInfinity; maxX=maxY=float.NegativeInfinity;
            UIVertex vertex=default(UIVertex);
            for(int i=0;i<vh.currentVertCount;i++)
            {
                vh.PopulateUIVertex(ref vertex,i);
                if(!Finite(vertex)){LastMode=GradientMeshMode.InvalidInput;return;}
                minX=Mathf.Min(minX,vertex.position.x);maxX=Mathf.Max(maxX,vertex.position.x);
                minY=Mathf.Min(minY,vertex.position.y);maxY=Mathf.Max(maxY,vertex.position.y);
            }
            if(maxX-minX<=.00001f || maxY-minY<=.00001f){LastMode=GradientMeshMode.Degenerate;return;}
            var image=graphic as Image;
            if(curve==GradientCurve.Nonlinear && (!image || image.type==Image.Type.Simple) && StrictRectangle(vh))
            {
                if(subdivisionMode==GradientSubdivisionMode.Adaptive)
                {
                    EnsureSelection();SelectedSegments=cachedSelection.Segments;
                    HasGradientEstimate=true;EstimatedGradientError=cachedSelection.EstimatedMaxError;GradientQualityLimited=cachedSelection.QualityLimited;
                    OutputQualityAssessed=SameColor32(corners[0].color,corners[1].color) && SameColor32(corners[0].color,corners[2].color) && SameColor32(corners[0].color,corners[3].color);
                    Subdivide(vh,SelectedSegments,adaptivePositions);LastMode=GradientMeshMode.AdaptiveSegments;
                }
                else { Subdivide(vh,fixedSegments,null);LastMode=GradientMeshMode.FixedSegments;SelectedSegments=fixedSegments; }
            }
            else
            {
                LastMode=curve==GradientCurve.Linear ? GradientMeshMode.LinearVertices : GradientMeshMode.VertexFallback;
                for(int i=0;i<vh.currentVertCount;i++)
                {
                    vh.PopulateUIVertex(ref vertex,i);float t=Coordinate(vertex.position);
                    vertex.color=GradientFunction.Quantize((Color)vertex.color*Evaluate(t));vh.SetUIVertex(vertex,i);
                }
            }
            LastVertexCount=vh.currentVertCount;LastTriangleCount=vh.currentIndexCount/3;
        }
        private float Coordinate(Vector3 position) => direction==GradientDirection.Horizontal ? (position.x-minX)/(maxX-minX) : (position.y-minY)/(maxY-minY);
        private static bool Finite(Vector4 v) => GradientFunction.Finite(v.x)&&GradientFunction.Finite(v.y)&&GradientFunction.Finite(v.z)&&GradientFunction.Finite(v.w);
        private static bool Finite(UIVertex v) => Finite(v.position)&&Finite(v.normal)&&Finite(v.tangent)&&Finite(v.uv0)&&Finite(v.uv1)&&Finite(v.uv2)&&Finite(v.uv3);
        private bool StrictRectangle(VertexHelper vh)
        {
            if(vh.currentVertCount!=4 || vh.currentIndexCount!=6)return false;
            float epsilon=Mathf.Max(.00001f,Mathf.Min(maxX-minX,maxY-minY)*.00001f);
            int seen=0;UIVertex v=default(UIVertex);float z=0;
            for(int i=0;i<4;i++)
            {
                vh.PopulateUIVertex(ref v,i);if(i==0)z=v.position.z;
                if(Mathf.Abs(v.position.z-z)>epsilon)return false;
                bool left=Mathf.Abs(v.position.x-minX)<=epsilon,right=Mathf.Abs(v.position.x-maxX)<=epsilon;
                bool bottom=Mathf.Abs(v.position.y-minY)<=epsilon,top=Mathf.Abs(v.position.y-maxY)<=epsilon;
                if(left==right || bottom==top)return false;
                int c=left ? (bottom ? 0 : 1) : (top ? 2 : 3);
                if((seen&(1<<c))!=0)return false;seen|=1<<c;corners[c]=v;
            }
            if(seen!=15 || (corners[0].uv0+corners[2].uv0-corners[1].uv0-corners[3].uv0).sqrMagnitude>1e-10f)return false;
            stream.Clear();vh.GetUIVertexStream(stream);if(stream.Count!=6)return false;
            Array.Clear(uses,0,uses.Length);
            for(int i=0;i<6;i++)
            {
                int c=-1;for(int j=0;j<4;j++)if((stream[i].position-corners[j].position).sqrMagnitude<=epsilon*epsilon){c=j;break;}
                if(c<0)return false;triangleCorners[i]=c;uses[c]++;
            }
            float first=0;
            for(int i=0;i<6;i+=3)
            {
                int a=triangleCorners[i],b=triangleCorners[i+1],c=triangleCorners[i+2];
                if(a==b || b==c || a==c)return false;
                Vector3 ab=corners[b].position-corners[a].position,ac=corners[c].position-corners[a].position;
                float cross=ab.x*ac.y-ab.y*ac.x;
                if(cross==0 || !GradientFunction.Finite(cross))return false;
                if(i==0)first=cross;else if((cross<0)!=(first<0))return false;
            }
            int sharedA=-1,sharedB=-1;
            for(int i=0;i<4;i++)
            {
                if(uses[i]==2){if(sharedA<0)sharedA=i;else if(sharedB<0)sharedB=i;else return false;}
                else if(uses[i]!=1)return false;
            }
            if(sharedA<0 || sharedB<0 || (sharedA+2)%4!=sharedB)return false;
            clockwise=first<0;return true;
        }
        private static UIVertex Lerp(UIVertex a,UIVertex b,float t, out Color baseColor)
        {
            baseColor=Color.LerpUnclamped(a.color,b.color,t);
            if(t==0)return a;if(t==1)return b;
            return new UIVertex { position=Vector3.LerpUnclamped(a.position,b.position,t),normal=Vector3.LerpUnclamped(a.normal,b.normal,t),
                tangent=Vector4.LerpUnclamped(a.tangent,b.tangent,t),color=(Color32)Color.LerpUnclamped(a.color,b.color,t),
                uv0=Vector4.LerpUnclamped(a.uv0,b.uv0,t),uv1=Vector4.LerpUnclamped(a.uv1,b.uv1,t),
                uv2=Vector4.LerpUnclamped(a.uv2,b.uv2,t),uv3=Vector4.LerpUnclamped(a.uv3,b.uv3,t) };
        }
        private void Triangle(VertexHelper vh,int a,int b,int c) { if(clockwise)vh.AddTriangle(a,b,c);else vh.AddTriangle(a,c,b); }
        private void EnsureSelection()
        {
            long started=System.Diagnostics.Stopwatch.GetTimestamp();
            if(selectionCached && GradientFunction.Same(cachedStart,startColor) && GradientFunction.Same(cachedEnd,endColor) && cachedBias==bias && cachedCurve==curve && cachedMinimum==adaptiveMinSegments && cachedMaximum==adaptiveMaxSegments && cachedTolerance==adaptiveTolerance)
                SelectionCacheHits++;
            else
            {
                if(adaptivePositions==null){adaptivePositions=new float[MaximumSegments+1];adaptiveErrors=new double[MaximumSegments];}
                cachedSelection=GradientSegmentSelector.Select(startColor,endColor,bias,curve,adaptiveMinSegments,adaptiveMaxSegments,adaptiveTolerance,adaptivePositions,adaptiveErrors);
                cachedStart=startColor;cachedEnd=endColor;cachedBias=bias;cachedCurve=curve;cachedMinimum=adaptiveMinSegments;cachedMaximum=adaptiveMaxSegments;cachedTolerance=adaptiveTolerance;selectionCached=true;SelectionCount++;
            }
            SelectionTicks+=System.Diagnostics.Stopwatch.GetTimestamp()-started;
        }
        private void Subdivide(VertexHelper vh,int segments,float[] positions)
        {
            vh.Clear();
            for(int i=0;i<=segments;i++)
            {
                float t=positions==null?i/(float)segments:positions[i];UIVertex a,b;Color ca,cb;
                if(direction==GradientDirection.Horizontal){a=Lerp(corners[0],corners[3],t,out ca);b=Lerp(corners[1],corners[2],t,out cb);}
                else{a=Lerp(corners[0],corners[1],t,out ca);b=Lerp(corners[3],corners[2],t,out cb);}
                Color gradient=Evaluate(t);a.color=GradientFunction.Quantize(ca*gradient);b.color=GradientFunction.Quantize(cb*gradient);
                vh.AddVert(a);vh.AddVert(b);
                if(i==0)continue;int n=2*(i-1);
                if(direction==GradientDirection.Horizontal){Triangle(vh,n,n+1,n+3);Triangle(vh,n+3,n+2,n);}
                else{Triangle(vh,n,n+2,n+3);Triangle(vh,n+3,n+1,n);}
            }
        }
#if UNITY_EDITOR
        protected override void OnValidate()
        {
            fixedSegments=Mathf.Clamp(fixedSegments,1,MaximumSegments);
            if(subdivisionMode!=GradientSubdivisionMode.Fixed && subdivisionMode!=GradientSubdivisionMode.Adaptive)subdivisionMode=GradientSubdivisionMode.Fixed;
            adaptiveMaxSegments=Mathf.Clamp(adaptiveMaxSegments,1,MaximumSegments);
            adaptiveMinSegments=Mathf.Clamp(adaptiveMinSegments,1,adaptiveMaxSegments);
            adaptiveTolerance=GradientFunction.Finite(adaptiveTolerance)?Mathf.Clamp(adaptiveTolerance,GradientSegmentSelector.MinimumTolerance,1):.01f;
            bias=GradientFunction.Finite(bias)?Mathf.Clamp(bias,.05f,.95f):.5f;
            if(direction!=GradientDirection.Horizontal && direction!=GradientDirection.Vertical)direction=GradientDirection.Horizontal;
            if(curve!=GradientCurve.Linear && curve!=GradientCurve.Nonlinear)curve=GradientCurve.Linear;
            startColor=SafeColor(startColor);endColor=SafeColor(endColor);base.OnValidate();
        }
        private static Color SafeColor(Color c) => new Color(Safe(c.r),Safe(c.g),Safe(c.b),Safe(c.a));
        private static float Safe(float x) => GradientFunction.Finite(x)?Mathf.Clamp01(x):0;
#endif
    }
}
