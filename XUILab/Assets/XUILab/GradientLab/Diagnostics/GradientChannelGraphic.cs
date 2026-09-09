using UnityEngine;
using UnityEngine.UI;

namespace XUILab.GradientLab
{
    [RequireComponent(typeof(RectTransform), typeof(CanvasRenderer))]
    public sealed class GradientChannelGraphic : MaskableGraphic
    {
        public GradientChannelGraphic() { useLegacyMeshGeneration = false; }
        protected override void OnPopulateMesh(VertexHelper vh)
        {
            vh.Clear();var rect=GetPixelAdjustedRect();
            Add(vh,rect,0,0);Add(vh,rect,0,1);Add(vh,rect,1,1);Add(vh,rect,1,0);
            vh.AddTriangle(0,1,2);vh.AddTriangle(2,3,0);
        }
        private void Add(VertexHelper vh,Rect rect,float x,float y)
        {
            var v=UIVertex.simpleVert;v.position=new Vector3(Mathf.Lerp(rect.xMin,rect.xMax,x),Mathf.Lerp(rect.yMin,rect.yMax,y),0);v.color=color;
            v.uv0=new Vector4(x,y,.3f,.6f);v.uv1=new Vector4(x,.2f,.3f,.4f);v.uv2=new Vector4(.1f,y,.3f,.4f);v.uv3=new Vector4(.1f,.2f,.2f+.6f*x,.4f);
            v.normal=new Vector3(.1f+.2f*x,.2f+.3f*y,-1);v.tangent=new Vector4(x,y,.2f,-1+2*y);vh.AddVert(v);
        }
    }
}
