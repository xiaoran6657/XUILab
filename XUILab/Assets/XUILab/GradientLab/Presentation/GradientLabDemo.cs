using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

namespace XUILab.GradientLab
{
    public sealed class GradientLabDemo : MonoBehaviour
    {
        public bool MeasurementMode { get; set; }
        public IReadOnlyList<GradientEffect> Effects => effects;
        private readonly List<GradientEffect> effects=new List<GradientEffect>();
        private GameObject root;
        private Texture2D texture;
        private Sprite sprite;
        private Text diagnostic;
        private float next;
        private GradientTransitionController transition;
        private void Start(){if(!MeasurementMode)Build();}
        public void Build()
        {
            if(root)return;
            root=GradientLabFactory.CanvasRoot("GradientLabCanvas");
            root.GetComponent<CanvasScaler>().referenceResolution=new Vector2(1280,800);
            root.GetComponent<CanvasScaler>().screenMatchMode=CanvasScaler.ScreenMatchMode.Expand;
            GradientLabFactory.Label(root.transform,"GRADIENT LAB  /  SUBDIVISION & QUALITY",new Vector2(-30,326),new Vector2(1140,36),27);
            ButtonAt("Fixed / Adaptive",-475,ToggleSubdivision);
            ButtonAt("Segments",-285,CycleSegments);
            ButtonAt("Bias",-95,CycleBias);
            ButtonAt("Direction",95,ToggleDirection);
            ButtonAt("Transition",285,PlayTransition);
            ButtonAt("Stop",475,StopTransition);
            GradientLabFactory.Label(root.transform,"Encoded RGB | Linear project | Personal reproduction",new Vector2(-30,290),new Vector2(1140,24),16);
            var large=Add(root.transform,"Large",new Vector2(-280,165),new Vector2(590,190),.25f);
            transition=large.gameObject.AddComponent<GradientTransitionController>();transition.Automatic=false;
            GradientLabFactory.Label(root.transform,"Large / adjustable curve and subdivision",new Vector2(-280,54),new Vector2(590,24),16);
            for(int i=0;i<12;i++){var e=Add(root.transform,"Grid"+i,new Vector2(-525+(i%4)*165,-35-(i/4)*73),new Vector2(150,57),i%3==0?.05f:i%3==1?.5f:.95f);e.Direction=i%2==0?GradientDirection.Horizontal:GradientDirection.Vertical;}
            var viewport=GradientLabFactory.Rect("ClippedViewport",root.transform,new Vector2(390,90),new Vector2(330,360));viewport.gameObject.AddComponent<Image>().color=new Color(.07f,.10f,.15f);viewport.gameObject.AddComponent<RectMask2D>();
            var content=GradientLabFactory.Rect("Content",viewport,Vector2.zero,new Vector2(310,800));content.anchorMin=content.anchorMax=content.pivot=new Vector2(.5f,1);content.anchoredPosition=Vector2.zero;
            var scroll=viewport.gameObject.AddComponent<ScrollRect>();scroll.viewport=viewport;scroll.content=content;scroll.horizontal=false;scroll.movementType=ScrollRect.MovementType.Clamped;
            for(int i=0;i<12;i++)Add(content,"ClippedRow"+i,new Vector2(0,-35-i*66),new Vector2(302,58),.25f).GetComponent<RectTransform>().anchorMin=content.GetChild(i).GetComponent<RectTransform>().anchorMax=new Vector2(.5f,1);
            GradientLabFactory.Label(root.transform,"RectMask2D / 12 generated rows / scroll",new Vector2(390,286),new Vector2(360,26),15);
            texture=new Texture2D(16,16,TextureFormat.RGBA32,false);var pixels=new Color32[256];for(int i=0;i<pixels.Length;i++)pixels[i]=new Color32(255,255,255,255);texture.SetPixels32(pixels);texture.Apply();sprite=GradientLabFactory.BorderSprite(texture);
            var types=new[]{Image.Type.Simple,Image.Type.Sliced,Image.Type.Tiled,Image.Type.Filled};
            for(int i=0;i<4;i++)
            {
                var e=Add(root.transform,types[i].ToString(),new Vector2(-450+i*300,-278),new Vector2(210,78),.25f);var im=e.GetComponent<Image>();im.sprite=sprite;im.type=types[i];im.fillMethod=Image.FillMethod.Radial360;im.fillAmount=.65f;
                GradientLabFactory.Label(root.transform,types[i]+(i==0?" / subdivided":" / vertex fallback"),new Vector2(-450+i*300,-331),new Vector2(270,24),15);
            }
            diagnostic=GradientLabFactory.Label(root.transform,"",new Vector2(0,-224),new Vector2(1150,26),15);UpdateDiagnostic();
        }
        private GradientEffect Add(Transform parent,string name,Vector2 position,Vector2 size,float bias)
        {var effect=GradientLabFactory.Image(parent,name,position,size,bias);effects.Add(effect);return effect;}
        public void SetTransitionProgress(float progress)
        {if(!transition)return;transition.StartTransition(.05f,.95f,1);transition.SetProgress(progress);}
        public void ToggleSubdivision()
        {
            if(effects.Count==0)return;
            var mode=effects[0].SubdivisionMode==GradientSubdivisionMode.Fixed?GradientSubdivisionMode.Adaptive:GradientSubdivisionMode.Fixed;
            foreach(var effect in effects)effect.SubdivisionMode=mode;
        }
        public void CycleSegments()
        {
            if(effects.Count==0)return;
            int current=effects[0].FixedSegments;
            int value=current==8?16:current==16?32:current==32?64:8;
            foreach(var effect in effects)effect.FixedSegments=value;
        }
        public void CycleBias()
        {
            StopTransition();
            if(effects.Count==0)return;
            float value=effects[0].Bias<.5f?.5f:effects[0].Bias<.95f?.95f:.05f;
            foreach(var effect in effects)effect.Bias=value;
        }
        public void ToggleDirection()
        {
            foreach(var effect in effects)effect.Direction=effect.Direction==GradientDirection.Horizontal?GradientDirection.Vertical:GradientDirection.Horizontal;
        }
        public void PlayTransition()
        {if(transition){transition.Automatic=true;transition.StartTransition(.05f,.95f,4);}}
        public void StopTransition()
        {if(transition){transition.Cancel();transition.Automatic=false;}}
        private void ButtonAt(string value,float x,UnityEngine.Events.UnityAction action)
        {
            var rect=GradientLabFactory.Rect(value,root.transform,new Vector2(x,-370),new Vector2(180,26));
            rect.gameObject.AddComponent<Image>().color=new Color(.16f,.29f,.40f);
            rect.gameObject.AddComponent<Button>().onClick.AddListener(action);
            var label=GradientLabFactory.Label(rect,value,Vector2.zero,new Vector2(180,26),15);
            label.alignment=TextAnchor.MiddleCenter;
        }
        private void Update(){if(!MeasurementMode&&root&&Time.unscaledTime>=next){next=Time.unscaledTime+.2f;UpdateDiagnostic();}}
        private void UpdateDiagnostic()
        {
            int vertices=0,fallback=0;foreach(var effect in effects){vertices+=effect.LastVertexCount;if(effect.LastMode==GradientMeshMode.VertexFallback)fallback++;}
            if(diagnostic && effects.Count>0)diagnostic.text=effects[0].SubdivisionMode+" / fixed setting "+effects[0].FixedSegments+" / large bias "+effects[0].Bias.ToString("F2")+" / selected "+effects[0].SelectedSegments+" / vertices "+vertices+" / fallback "+fallback+" / diagnostic only";
        }
        private void OnDestroy(){if(root)Destroy(root);if(sprite)Destroy(sprite);if(texture)Destroy(texture);}
    }
}
