Shader "XUILab/GradientDiagnostic"
{
    Properties { _MainTex("Texture",2D)="white"{} _Channels("Channel output",Float)=0 }
    SubShader
    {
        Tags { "Queue"="Transparent" "RenderType"="Transparent" "IgnoreProjector"="True" }
        Cull Off ZWrite Off ZTest Always Blend Off
        Pass
        {
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "UnityCG.cginc"
            float _Channels;
            struct input { float4 vertex:POSITION; float4 color:COLOR; float4 uv1:TEXCOORD1; float4 uv2:TEXCOORD2; float4 uv3:TEXCOORD3; float4 tangent:TANGENT; };
            struct output { float4 vertex:SV_POSITION; float4 value:TEXCOORD0; };
            output vert(input v)
            {
                output o;o.vertex=UnityObjectToClipPos(v.vertex);
                o.value=_Channels>.5?float4(v.uv1.x,v.uv2.y,v.uv3.z,v.tangent.w*.5+.5):v.color;
                return o;
            }
            float4 frag(output i):SV_Target{return i.value;}
            ENDHLSL
        }
    }
}
