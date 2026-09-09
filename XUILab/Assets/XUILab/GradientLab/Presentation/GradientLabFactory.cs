using UnityEngine;
using UnityEngine.UI;

namespace XUILab.GradientLab
{
    public static class GradientLabFactory
    {
        public static RectTransform Rect(string name,Transform parent,Vector2 position,Vector2 size)
        {
            var rect=new GameObject(name,typeof(RectTransform)).GetComponent<RectTransform>();
            rect.SetParent(parent,false);rect.anchoredPosition=position;rect.sizeDelta=size;return rect;
        }
        public static GameObject CanvasRoot(string name)
        {
            var root=new GameObject(name,typeof(Canvas),typeof(CanvasScaler),typeof(GraphicRaycaster));
            root.GetComponent<Canvas>().renderMode=RenderMode.ScreenSpaceOverlay;
            var scaler=root.GetComponent<CanvasScaler>();scaler.uiScaleMode=CanvasScaler.ScaleMode.ScaleWithScreenSize;scaler.referenceResolution=new Vector2(1280,720);
            return root;
        }
        public static GradientEffect Image(Transform parent,string name,Vector2 position,Vector2 size,float bias=.25f)
        {
            var rect=Rect(name,parent,position,size);var image=rect.gameObject.AddComponent<Image>();image.raycastTarget=false;
            var effect=rect.gameObject.AddComponent<GradientEffect>();effect.StartColor=new Color(.04f,.75f,.95f,1);effect.EndColor=new Color(.95f,.15f,.4f,.6f);effect.Bias=bias;return effect;
        }
        public static Text Label(Transform parent,string value,Vector2 position,Vector2 size,int fontSize=18)
        {
            var rect=Rect("Label",parent,position,size);var text=rect.gameObject.AddComponent<Text>();text.font=Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            text.text=value;text.fontSize=fontSize;text.color=Color.white;text.alignment=TextAnchor.MiddleLeft;text.raycastTarget=false;return text;
        }
        public static Sprite BorderSprite(Texture2D texture)
        {
            return Sprite.Create(texture,new Rect(0,0,texture.width,texture.height),new Vector2(.5f,.5f),100,0,SpriteMeshType.FullRect,new Vector4(4,4,4,4));
        }
    }
}
