using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;
using UnityEngine.Experimental.Rendering;
using System.Security.Cryptography;
using UnityEngine.TestTools;
using UnityEngine.UI;

namespace XUILab.GradientLab.Tests
{
    public sealed class GradientQualityTests
    {
        private GameObject root,cameraObject;
        private Texture2D spriteTexture,readback;
        private Sprite sprite;
        private Material material;
        private RenderTexture target;
        private Camera camera;
        private RenderPipelineAsset previousPipeline;
        private UniversalRenderPipelineAsset diagnosticPipeline;
        private const int Width=256,Height=128;
        private string output;
        [OneTimeSetUp] public void BeginEvidenceSuite()
        {
            output=Path.GetFullPath(Path.Combine(Application.dataPath,"../../Artifacts/gradient-quality-runs",DateTime.UtcNow.ToString("yyyyMMddTHHmmssfffffffZ",CultureInfo.InvariantCulture)+"-"+Guid.NewGuid().ToString("N")));
            if(Directory.Exists(output))throw new IOException("Evidence directory already exists: "+output);
            Directory.CreateDirectory(output);
            WriteText(Path.Combine(output,"suite.json"),"{\"schema\":\"xuilab.gradient-quality-suite/v1\",\"startedUtc\":\""+DateTime.UtcNow.ToString("O",CultureInfo.InvariantCulture)+"\"}");
            TestContext.Progress.WriteLine("Gradient quality evidence: "+output);
        }
        private static void WriteBytes(string path,byte[] bytes)
        {using(var stream=new FileStream(path,FileMode.CreateNew,FileAccess.Write,FileShare.None))stream.Write(bytes,0,bytes.Length);}
        private static void WriteText(string path,string text){WriteBytes(path,new UTF8Encoding(false).GetBytes(text));}
        [UnitySetUp] public IEnumerator SetUp()
        {
            root=new GameObject("GradientQualityCanvas",typeof(Canvas));var canvas=root.GetComponent<Canvas>();canvas.renderMode=RenderMode.ScreenSpaceOverlay;
            canvas.additionalShaderChannels=AdditionalCanvasShaderChannels.TexCoord1|AdditionalCanvasShaderChannels.TexCoord2|AdditionalCanvasShaderChannels.TexCoord3|AdditionalCanvasShaderChannels.Normal|AdditionalCanvasShaderChannels.Tangent;
            spriteTexture=new Texture2D(16,16,TextureFormat.RGBA32,false);var pixels=new Color32[256];for(int i=0;i<256;i++)pixels[i]=new Color32(255,255,255,255);spriteTexture.SetPixels32(pixels);spriteTexture.Apply();sprite=GradientLabFactory.BorderSprite(spriteTexture);
            yield return null;
        }
        [UnityTearDown] public IEnumerator TearDown()
        {
            if(camera)camera.targetTexture=null;if(root)UnityEngine.Object.Destroy(root);if(cameraObject)UnityEngine.Object.Destroy(cameraObject);
            if(material)UnityEngine.Object.Destroy(material);if(sprite)UnityEngine.Object.Destroy(sprite);if(spriteTexture)UnityEngine.Object.Destroy(spriteTexture);if(readback)UnityEngine.Object.Destroy(readback);
            if(target){target.Release();UnityEngine.Object.Destroy(target);}
            if(diagnosticPipeline){QualitySettings.renderPipeline=previousPipeline;UnityEngine.Object.Destroy(diagnosticPipeline);}
            yield return null;
        }
        [UnityTest] public IEnumerator RealImageTypesKeepTheirOwnTopologyAndExposeFallback()
        {
            var rows=new StringBuilder("type,inputVertices,inputIndices,outputVertices,outputIndices,mode\n");
            foreach(Image.Type type in Enum.GetValues(typeof(Image.Type)))
            {
                var rect=GradientLabFactory.Rect(type.ToString(),root.transform,Vector2.zero,new Vector2(180,95));var image=rect.gameObject.AddComponent<Image>();image.sprite=sprite;image.type=type;image.fillMethod=Image.FillMethod.Radial360;image.fillAmount=.65f;
                Canvas.ForceUpdateCanvases();yield return null;var before=UnityEngine.Object.Instantiate(image.canvasRenderer.GetMesh());
                var effect=rect.gameObject.AddComponent<GradientEffect>();Canvas.ForceUpdateCanvases();yield return null;var after=UnityEngine.Object.Instantiate(image.canvasRenderer.GetMesh());
                try
                {
                    Assert.Greater(before.vertexCount,0);Assert.Greater(after.vertexCount,0);
                    if(type==Image.Type.Simple){Assert.AreEqual(GradientMeshMode.FixedSegments,effect.LastMode);Assert.AreEqual(66,after.vertexCount);}
                    else{Assert.AreEqual(GradientMeshMode.VertexFallback,effect.LastMode);Assert.AreEqual(before.vertexCount,after.vertexCount);CollectionAssert.AreEqual(before.triangles,after.triangles);}
                    rows.AppendFormat("{0},{1},{2},{3},{4},{5}\n",type,before.vertexCount,before.triangles.Length,after.vertexCount,after.triangles.Length,effect.LastMode);
                }
                finally{UnityEngine.Object.Destroy(before);UnityEngine.Object.Destroy(after);UnityEngine.Object.Destroy(rect.gameObject);}
                yield return null;
            }
            WriteText(Path.Combine(output,"image-types.csv"),rows.ToString());
        }
        [UnityTest] public IEnumerator PreserveAspectUsesActualDrawingRectangle()
        {
            var effect=GradientLabFactory.Image(root.transform,"Aspect",Vector2.zero,new Vector2(240,100));var image=effect.GetComponent<Image>();image.sprite=sprite;image.preserveAspect=true;
            Canvas.ForceUpdateCanvases();yield return null;var mesh=UnityEngine.Object.Instantiate(image.canvasRenderer.GetMesh());
            try{Assert.AreEqual(GradientMeshMode.FixedSegments,effect.LastMode);Assert.AreEqual(66,mesh.vertexCount);Assert.That(mesh.bounds.size.x,Is.EqualTo(100).Within(.01));Assert.That(mesh.bounds.size.y,Is.EqualTo(100).Within(.01));}
            finally{UnityEngine.Object.Destroy(mesh);}
        }
        private GradientEffect SetupRender(bool channels)
        {
            Assert.AreEqual(ColorSpace.Linear,QualitySettings.activeColorSpace);
#if UNITY_EDITOR
            previousPipeline=QualitySettings.renderPipeline;
            var source=UnityEditor.AssetDatabase.LoadAssetAtPath<UniversalRenderPipelineAsset>("Assets/Settings/URP-Performant.asset");Assert.IsNotNull(source);
            diagnosticPipeline=UnityEngine.Object.Instantiate(source);QualitySettings.renderPipeline=diagnosticPipeline;
#else
            Assert.Fail("Controlled editor quality fixture requires its explicitly selected pipeline asset.");
#endif
            root.layer=31;
            cameraObject=new GameObject("GradientQualityCamera",typeof(Camera));camera=cameraObject.GetComponent<Camera>();camera.clearFlags=CameraClearFlags.SolidColor;camera.backgroundColor=Color.magenta;camera.orthographic=true;camera.orthographicSize=Height*.5f;camera.nearClipPlane=.1f;camera.farClipPlane=100;camera.allowHDR=false;camera.allowMSAA=false;camera.cullingMask=1<<31;camera.allowDynamicResolution=false;camera.transform.position=new Vector3(0,0,-10);
            target=new RenderTexture(Width,Height,24,RenderTextureFormat.ARGB32,RenderTextureReadWrite.Linear);target.antiAliasing=1;target.useDynamicScale=false;target.Create();camera.targetTexture=target;
            Assert.AreEqual(GraphicsFormat.R8G8B8A8_UNorm,target.graphicsFormat);Assert.False(target.sRGB);Assert.AreEqual(1,target.antiAliasing);Assert.False(target.useDynamicScale);Assert.True(target.IsCreated());
            var cameraData=camera.GetUniversalAdditionalCameraData();cameraData.renderPostProcessing=false;cameraData.allowXRRendering=false;cameraData.antialiasing=AntialiasingMode.None;cameraData.renderType=CameraRenderType.Base;cameraData.cameraStack.Clear();
            var canvas=root.GetComponent<Canvas>();canvas.renderMode=RenderMode.ScreenSpaceCamera;canvas.worldCamera=camera;canvas.planeDistance=10;canvas.vertexColorAlwaysGammaSpace=true;Assert.True(canvas.vertexColorAlwaysGammaSpace);
            var shader=Resources.Load<Shader>("GradientDiagnostic");Assert.IsNotNull(shader);Assert.True(shader.isSupported);material=new Material(shader);material.SetFloat("_Channels",channels?1:0);
            var rect=GradientLabFactory.Rect("DiagnosticQuad",root.transform,Vector2.zero,new Vector2(Width,Height));rect.gameObject.layer=31;var graphic=rect.gameObject.AddComponent<GradientChannelGraphic>();graphic.material=material;
            Assert.IsNotNull(graphic.canvasRenderer);
            var effect=rect.gameObject.AddComponent<GradientEffect>();effect.StartColor=new Color(.04f,.75f,.95f,1);effect.EndColor=new Color(.95f,.15f,.4f,.6f);effect.Bias=.25f;
            readback=new Texture2D(Width,Height,TextureFormat.RGBA32,false,true);return effect;
        }
        private Color32[] Capture(string name)
        {
            Assert.AreSame(target,camera.targetTexture);Assert.AreEqual(Width,target.width);Assert.AreEqual(Height,target.height);
            var quad=root.GetComponentInChildren<GradientChannelGraphic>();var corners=new Vector3[4];quad.rectTransform.GetWorldCorners(corners);
            var low=camera.WorldToScreenPoint(corners[0]);var high=camera.WorldToScreenPoint(corners[2]);
            Assert.That(low.x,Is.EqualTo(0).Within(.01));Assert.That(low.y,Is.EqualTo(0).Within(.01));Assert.That(high.x,Is.EqualTo(Width).Within(.01));Assert.That(high.y,Is.EqualTo(Height).Within(.01));
            var prior=RenderTexture.active;
            try{RenderTexture.active=target;readback.ReadPixels(new Rect(0,0,Width,Height),0,0);readback.Apply();WriteBytes(Path.Combine(output,name+".png"),readback.EncodeToPNG());
                var pixels=readback.GetPixels32();var bytes=new byte[pixels.Length*4];for(int i=0;i<pixels.Length;i++){bytes[i*4]=pixels[i].r;bytes[i*4+1]=pixels[i].g;bytes[i*4+2]=pixels[i].b;bytes[i*4+3]=pixels[i].a;}WriteBytes(Path.Combine(output,name+".rgba"),bytes);
                string hash;using(var sha=SHA256.Create())hash=BitConverter.ToString(sha.ComputeHash(bytes)).Replace("-","").ToLowerInvariant();
                WriteText(Path.Combine(output,name+".json"),JsonUtility.ToJson(new CaptureIdentity { width=Width,height=Height,frameCount=Time.frameCount,graphicsFormat=target.graphicsFormat.ToString(),sRGB=target.sRGB,antiAliasing=target.antiAliasing,readbackLinear=true,vertexColorAlwaysGammaSpace=root.GetComponent<Canvas>().vertexColorAlwaysGammaSpace,shader=material.shader.name,colorSpace=QualitySettings.activeColorSpace.ToString(),rawSha256=hash,mode=quad.GetComponent<GradientEffect>().LastMode.ToString(),vertices=quad.GetComponent<GradientEffect>().LastVertexCount },true));
                return pixels;}
            finally{RenderTexture.active=prior;}
        }
        [Serializable] private sealed class CaptureIdentity
        {
            public int width,height,frameCount,antiAliasing,vertices;
            public bool sRGB,readbackLinear,vertexColorAlwaysGammaSpace;
            public string graphicsFormat,shader,colorSpace,rawSha256,mode;
        }
        private static double Weight(double t,double bias){double a=(1-bias)/bias;return t/(a+(1-a)*t);}
        private static Color Reference(double t,Color start,Color end,double bias)
        {double w=Weight(t,bias);return new Color((float)(start.r+(end.r-start.r)*w),(float)(start.g+(end.g-start.g)*w),(float)(start.b+(end.b-start.b)*w),(float)(start.a+(end.a-start.a)*w));}
        private static Color QuantizedReference(double t,Color start,Color end,double bias)
        {
            var c=Reference(t,start,end,bias);for(int i=0;i<4;i++)c[i]=(float)(Math.Floor(c[i]*255+.5)/255);return c;
        }
        private static Color Piecewise(double t,Color start,Color end,double bias,int segments)
        {
            int cell=Math.Min(segments-1,(int)(t*segments));double u=t*segments-cell;
            var a=QuantizedReference(cell/(double)segments,start,end,bias);var b=QuantizedReference((cell+1)/(double)segments,start,end,bias);
            return Color.LerpUnclamped(a,b,(float)u);
        }
        [UnityTest] public IEnumerator RenderedGradientMatchesQuantizedPiecewiseReference()
        {
            var effect=SetupRender(false);var report=new StringBuilder("direction,bias,maxPixelError,rmsPixelError,vertexCount,mode\n");
            foreach(int segments in new[]{8,16,32,64})foreach(GradientDirection direction in Enum.GetValues(typeof(GradientDirection)))foreach(float bias in new[]{.05f,.25f,.5f,.95f})
            {
                effect.FixedSegments=segments;effect.Direction=direction;effect.Bias=bias;Canvas.ForceUpdateCanvases();yield return null;yield return null;
                var pixels=Capture("gradient-s"+segments+"-"+direction+"-"+bias.ToString("0.00",CultureInfo.InvariantCulture));double max=0,squares=0;int n=0;
                for(int y=2;y<Height-2;y++)for(int x=2;x<Width-2;x++)
                {
                    double t=direction==GradientDirection.Horizontal?(x+.5)/Width:(y+.5)/Height;var expected=Piecewise(t,effect.StartColor,effect.EndColor,bias,segments);Color actual=pixels[y*Width+x];
                    for(int c=0;c<4;c++){double error=Math.Abs(expected[c]-actual[c]);max=Math.Max(max,error);squares+=error*error;n++;}
                }
                double rms=Math.Sqrt(squares/n);report.AppendFormat(CultureInfo.InvariantCulture,"{0},{1},{2:R},{3:R},{4},{5}\n",direction,bias,max,rms,effect.LastVertexCount,effect.LastMode);
                Assert.AreEqual(GradientMeshMode.FixedSegments,effect.LastMode);Assert.LessOrEqual(max,2.0/255,"Pixel max; inspect saved raw linear image.");Assert.LessOrEqual(rms,1.0/255);
            }
            WriteText(Path.Combine(output,"pixel-errors.csv"),report.ToString());
        }

        [UnityTest] public IEnumerator DenseReferenceSeparatesCurveApproximationAndVertexQuantization()
        {
            var effect=GradientLabFactory.Image(root.transform,"DenseReference",Vector2.zero,new Vector2(900,450));
            effect.StartColor=new Color(.04f,.75f,.95f,1);effect.EndColor=new Color(.95f,.15f,.4f,.6f);
            var summary=new StringBuilder("width,height,segments,direction,bias,samples,vertices,indices,functionMax,approxMax,approxRms,quantMax,qualityStatus\n");
            foreach(var size in new[]{new Vector2(900,450),new Vector2(900f/14*.9f,480f/8*.9f)})
            foreach(int segments in new[]{8,16,32,64})foreach(GradientDirection direction in Enum.GetValues(typeof(GradientDirection)))foreach(float bias in new[]{.05f,.5f,.95f})
            {
                effect.GetComponent<RectTransform>().sizeDelta=size;effect.FixedSegments=segments;effect.Direction=direction;effect.Bias=bias;Canvas.ForceUpdateCanvases();yield return null;
                var mesh=UnityEngine.Object.Instantiate(effect.GetComponent<Image>().canvasRenderer.GetMesh());
                try
                {
                    Assert.AreEqual(2*(segments+1),mesh.vertexCount);Assert.AreEqual(6*segments,mesh.triangles.Length);Assert.AreEqual(segments,effect.SelectedSegments);
                    var colors=mesh.colors32;var positions=mesh.vertices;
                    double functionMax=0,approxMax=0,squares=0,quantMax=0;
                    var rows=new StringBuilder("t,referenceR,referenceG,referenceB,referenceA,runtimeR,runtimeG,runtimeB,runtimeA,piecewiseR,piecewiseG,piecewiseB,piecewiseA,meshR,meshG,meshB,meshA\n");
                    for(int n=0;n<=segments;n++)
                    {
                        double t=n/(double)segments;var pos=positions[2*n];
                        Assert.That(direction==GradientDirection.Horizontal?pos.x:pos.y,Is.EqualTo((t-.5)*(direction==GradientDirection.Horizontal?size.x:size.y)).Within(.001));
                        Assert.AreEqual(colors[2*n],colors[2*n+1]);
                    }
                    for(int i=0;i<=4096;i++)
                    {
                        double t=i/4096.0;int cell=Math.Min(segments-1,(int)(t*segments));double u=t*segments-cell;
                        double a=(1-(double)bias)/bias,w=t/(a+(1-a)*t);
                        var runtime=effect.Evaluate((float)t);var left=effect.Evaluate(cell/(float)segments);var right=effect.Evaluate((cell+1)/(float)segments);
                        Color ml=colors[2*cell],mr=colors[2*(cell+1)];var values=new double[16];
                        for(int c=0;c<4;c++)
                        {
                            double expected=effect.StartColor[c]+(effect.EndColor[c]-effect.StartColor[c])*w;
                            double piecewise=left[c]+(right[c]-left[c])*u,actual=ml[c]+(mr[c]-ml[c])*u;
                            values[c]=expected;values[4+c]=runtime[c];values[8+c]=piecewise;values[12+c]=actual;
                            functionMax=Math.Max(functionMax,Math.Abs(expected-runtime[c]));double e=Math.Abs(expected-piecewise);approxMax=Math.Max(approxMax,e);squares+=e*e;quantMax=Math.Max(quantMax,Math.Abs(piecewise-actual));
                        }
                        rows.Append(t.ToString("R",CultureInfo.InvariantCulture));foreach(double v in values)rows.Append(',').Append(v.ToString("R",CultureInfo.InvariantCulture));rows.Append('\n');
                    }
                    string name="dense-w"+size.x.ToString("0.000",CultureInfo.InvariantCulture)+"-s"+segments+"-"+direction+"-"+bias.ToString("0.00",CultureInfo.InvariantCulture);
                    WriteText(Path.Combine(output,name+".csv"),rows.ToString());
                    var raw=new StringBuilder("index,x,y,z,r,g,b,a\n");for(int i=0;i<positions.Length;i++)raw.AppendFormat(CultureInfo.InvariantCulture,"{0},{1:R},{2:R},{3:R},{4},{5},{6},{7}\n",i,positions[i].x,positions[i].y,positions[i].z,colors[i].r,colors[i].g,colors[i].b,colors[i].a);
                    WriteText(Path.Combine(output,name+"-mesh.csv"),raw.ToString());WriteText(Path.Combine(output,name+"-indices.csv"),string.Join(",",mesh.triangles));
                    summary.AppendFormat(CultureInfo.InvariantCulture,"{0:R},{1:R},{2},{3},{4:R},4097,{5},{6},{7:R},{8:R},{9:R},{10:R},{11}\n",size.x,size.y,segments,direction,bias,mesh.vertexCount,mesh.triangles.Length,functionMax,approxMax,Math.Sqrt(squares/(4097*4)),quantMax,approxMax<=.01?"pass":"quality_limited");
                    Assert.LessOrEqual(functionMax,1e-5);Assert.LessOrEqual(quantMax,.5/255+1e-6);
                }
                finally{UnityEngine.Object.Destroy(mesh);}
            }
            WriteText(Path.Combine(output,"dense-summary.csv"),summary.ToString());
        }

        private static double[] MeshNodes(Mesh mesh,GradientDirection direction)
        {
            int axis=direction==GradientDirection.Horizontal?0:1;
            var vertices=mesh.vertices;var nodes=new double[vertices.Length/2];
            double low=mesh.bounds.min[axis],width=mesh.bounds.size[axis];
            for(int i=0;i<nodes.Length;i++)nodes[i]=(vertices[2*i][axis]-low)/width;
            Assert.That(nodes[0],Is.EqualTo(0).Within(1e-6));Assert.That(nodes[nodes.Length-1],Is.EqualTo(1).Within(1e-6));
            nodes[0]=0;nodes[nodes.Length-1]=1;
            for(int i=1;i<nodes.Length;i++)Assert.Greater(nodes[i],nodes[i-1]);
            return nodes;
        }
        private static int Cell(double t,double[] nodes)
        {int cell=0;while(cell<nodes.Length-2 && t>nodes[cell+1])cell++;return cell;}
        [UnityTest] public IEnumerator AdaptiveDenseActualMeshSeparatesApproximationQuantizationAndCaps()
        {
            var effect=GradientLabFactory.Image(root.transform,"AdaptiveDense",Vector2.zero,new Vector2(900,450));
            effect.StartColor=new Color(.04f,.75f,.95f,1);effect.EndColor=new Color(.95f,.15f,.4f,.6f);effect.SubdivisionMode=GradientSubdivisionMode.Adaptive;
            var report=new StringBuilder("width,height,direction,bias,cap,tolerance,segments,estimatedError,qualityLimited,functionMax,approxMax,approxRms,quantMax\n");
            foreach(var size in new[]{new Vector2(900,450),new Vector2(900f/14*.9f,480f/8*.9f)})
            foreach(GradientDirection direction in Enum.GetValues(typeof(GradientDirection)))
            foreach(float bias in new[]{.05f,.5f,.95f})foreach(int setting in new[]{0,1,2})
            {
                int cap=setting==1?4:64;float tolerance=setting==2?.00001f:.01f;
                effect.ConfigureAdaptive(1,cap,tolerance);effect.Bias=bias;effect.Direction=direction;effect.GetComponent<RectTransform>().sizeDelta=size;
                Canvas.ForceUpdateCanvases();yield return null;
                var mesh=UnityEngine.Object.Instantiate(effect.GetComponent<CanvasRenderer>().GetMesh());
                try
                {
                    int segments=effect.SelectedSegments;Assert.AreEqual(2*(segments+1),mesh.vertexCount);Assert.AreEqual(6*segments,mesh.triangles.Length);
                    Assert.AreEqual(GradientMeshMode.AdaptiveSegments,effect.LastMode);Assert.True(effect.OutputQualityAssessed);
                    var nodes=MeshNodes(mesh,direction);var colors=mesh.colors32;
                    double functionMax=0,approxMax=0,quantMax=0,squares=0;
                    var rows=new StringBuilder("t,referenceR,referenceG,referenceB,referenceA,runtimeR,runtimeG,runtimeB,runtimeA,piecewiseR,piecewiseG,piecewiseB,piecewiseA,meshR,meshG,meshB,meshA\n");
                    for(int i=0;i<=4096;i++)
                    {
                        double t=i/4096.0;int cell=Cell(t,nodes);double u=(t-nodes[cell])/(nodes[cell+1]-nodes[cell]);
                        var runtime=effect.Evaluate((float)t);var left=effect.Evaluate((float)nodes[cell]);var right=effect.Evaluate((float)nodes[cell+1]);
                        Color ml=colors[2*cell],mr=colors[2*(cell+1)];double w=Weight(t,bias);var values=new double[16];
                        for(int c=0;c<4;c++)
                        {
                            double expected=effect.StartColor[c]+(effect.EndColor[c]-effect.StartColor[c])*w;
                            double piecewise=left[c]+(right[c]-left[c])*u,actual=ml[c]+(mr[c]-ml[c])*u;
                            values[c]=expected;values[4+c]=runtime[c];values[8+c]=piecewise;values[12+c]=actual;
                            functionMax=Math.Max(functionMax,Math.Abs(expected-runtime[c]));double e=Math.Abs(expected-piecewise);approxMax=Math.Max(approxMax,e);squares+=e*e;quantMax=Math.Max(quantMax,Math.Abs(piecewise-actual));
                        }
                        rows.Append(t.ToString("R",CultureInfo.InvariantCulture));foreach(double v in values)rows.Append(',').Append(v.ToString("R",CultureInfo.InvariantCulture));rows.Append('\n');
                    }
                    string name="adaptive-dense-w"+size.x.ToString("0.000",CultureInfo.InvariantCulture)+"-"+direction+"-b"+bias.ToString("0.00",CultureInfo.InvariantCulture)+"-setting"+setting;
                    WriteText(Path.Combine(output,name+".csv"),rows.ToString());
                    var raw=new StringBuilder("index,x,y,z,r,g,b,a\n");var vertices=mesh.vertices;
                    for(int i=0;i<vertices.Length;i++)raw.AppendFormat(CultureInfo.InvariantCulture,"{0},{1:R},{2:R},{3:R},{4},{5},{6},{7}\n",i,vertices[i].x,vertices[i].y,vertices[i].z,colors[i].r,colors[i].g,colors[i].b,colors[i].a);
                    WriteText(Path.Combine(output,name+"-mesh.csv"),raw.ToString());WriteText(Path.Combine(output,name+"-indices.csv"),string.Join(",",mesh.triangles));
                    report.AppendFormat(CultureInfo.InvariantCulture,"{0:R},{1:R},{2},{3:R},{4},{5:R},{6},{7:R},{8},{9:R},{10:R},{11:R},{12:R}\n",size.x,size.y,direction,bias,cap,tolerance,segments,effect.EstimatedGradientError,effect.GradientQualityLimited,functionMax,approxMax,Math.Sqrt(squares/(4097*4)),quantMax);
                    Assert.LessOrEqual(functionMax,1e-5);Assert.LessOrEqual(approxMax,effect.EstimatedGradientError+1e-6);Assert.LessOrEqual(quantMax,.5/255+2e-6);
                    Assert.AreEqual(effect.EstimatedGradientError>tolerance,effect.GradientQualityLimited);
                    if(setting==0){Assert.False(effect.GradientQualityLimited);Assert.LessOrEqual(approxMax,.01);}
                    if(setting==1 && bias!=.5f){Assert.True(effect.GradientQualityLimited);Assert.Greater(approxMax,.01);Assert.AreEqual(cap,segments);}
                }
                finally{UnityEngine.Object.Destroy(mesh);}
            }
            WriteText(Path.Combine(output,"adaptive-dense-summary.csv"),report.ToString());
        }
        [UnityTest] public IEnumerator AdaptivePixelsMatchActualNonuniformQuantizedReference()
        {
            var effect=SetupRender(false);effect.SubdivisionMode=GradientSubdivisionMode.Adaptive;
            var report=new StringBuilder("direction,bias,cap,tolerance,segments,qualityLimited,maxPixelError,rmsPixelError\n");
            foreach(GradientDirection direction in Enum.GetValues(typeof(GradientDirection)))foreach(float bias in new[]{.05f,.5f,.95f})foreach(int setting in new[]{0,1,2})
            {
                int cap=setting==1?4:64;float tolerance=setting==2?.00001f:.01f;
                effect.ConfigureAdaptive(1,cap,tolerance);effect.Direction=direction;effect.Bias=bias;Canvas.ForceUpdateCanvases();yield return null;yield return null;
                var mesh=UnityEngine.Object.Instantiate(effect.GetComponent<CanvasRenderer>().GetMesh());
                try
                {
                    var nodes=MeshNodes(mesh,direction);var pixels=Capture("adaptive-pixel-"+direction+"-b"+bias.ToString("0.00",CultureInfo.InvariantCulture)+"-setting"+setting);
                    double max=0,squares=0;int n=0;
                    for(int y=2;y<Height-2;y++)for(int x=2;x<Width-2;x++)
                    {
                        double t=direction==GradientDirection.Horizontal?(x+.5)/Width:(y+.5)/Height;int cell=Cell(t,nodes);double u=(t-nodes[cell])/(nodes[cell+1]-nodes[cell]);
                        var left=QuantizedReference(nodes[cell],effect.StartColor,effect.EndColor,bias);var right=QuantizedReference(nodes[cell+1],effect.StartColor,effect.EndColor,bias);
                        Color actual=pixels[y*Width+x];
                        for(int c=0;c<4;c++){double expected=left[c]+(right[c]-left[c])*u,error=Math.Abs(expected-actual[c]);max=Math.Max(max,error);squares+=error*error;n++;}
                    }
                    double rms=Math.Sqrt(squares/n);report.AppendFormat(CultureInfo.InvariantCulture,"{0},{1:R},{2},{3:R},{4},{5},{6:R},{7:R}\n",direction,bias,cap,tolerance,effect.SelectedSegments,effect.GradientQualityLimited,max,rms);
                    Assert.AreEqual(GradientMeshMode.AdaptiveSegments,effect.LastMode);Assert.LessOrEqual(max,2.0/255);Assert.LessOrEqual(rms,1.0/255);
                }
                finally{UnityEngine.Object.Destroy(mesh);}
            }
            WriteText(Path.Combine(output,"adaptive-pixel-errors.csv"),report.ToString());
        }

        [UnityTest] public IEnumerator ExtraChannelsSurviveCanvasAndGpuSubdivision()
        {
            var effect=SetupRender(true);effect.Curve=GradientCurve.Linear;Canvas.ForceUpdateCanvases();yield return null;yield return null;var before=Capture("channels-linear");
            effect.Curve=GradientCurve.Nonlinear;Canvas.ForceUpdateCanvases();yield return null;yield return null;var after=Capture("channels-fixed32");double max=0;
            for(int y=2;y<Height-2;y++)for(int x=2;x<Width-2;x++)
            {
                var expected=new Color((x+.5f)/Width,(y+.5f)/Height,.2f+.6f*(x+.5f)/Width,(y+.5f)/Height);Color a=before[y*Width+x],b=after[y*Width+x];
                for(int c=0;c<4;c++){max=Math.Max(max,Math.Abs(a[c]-b[c]));max=Math.Max(max,Math.Abs(expected[c]-b[c]));}
            }
            WriteText(Path.Combine(output,"channel-error.txt"),max.ToString("R",CultureInfo.InvariantCulture));Assert.LessOrEqual(max,2.0/255);
        }
    }
}
