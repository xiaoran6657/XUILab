# Gradient 质量与集成协议 v2

- protocol_id: gradient-quality-v2
- contract_id: gradient-schlick-v1
- task: M2-03
- status: r1/r2失败保留；受控颜色与渲染配置补齐后，在r3截图前冻结

## 固定输入与判据

工程保持2022.3.45f1c1、Linear、现有URP与UGUI。数值空间为encoded-rgb，alphaMode=straight-rgba-equal-weight；数学参考采用独立double公式，4097个t点，RGBA等权max/RMS。固定32段允许报告超出0.01的曲线误差；0.01是M3质量目标，不能把M2极端bias的近似写成精确或事后放宽目标。Color32输出量化误差单列，半步容差0.5/255加float误差。

像素诊断采用256×128、RGBA32、单采样、线性RenderTexture与线性读取Texture2D；在URP渲染完成后读取，输出PNG同时标注其原始线性像素含义。受控Shader将输入颜色直接输出，不执行RGB转换、不启用Blend，alpha原样输出。输入图元避开边界各2px，按像素中心归一化；参考分别计算连续曲线和实际32段量化顶点线性插值。真实像素对后者max容差2/255、RMS容差1/255（覆盖8bit目标/顶点量化及栅格浮点误差），不以连续曲线偏差冒充渲染错误。连续曲线误差独立报告。

附加通道Shader单独诊断：读取uv1.x、uv2.y、uv3.z组成RGB、tangent.w映射为alpha，使用四角已知仿射通道；比较线性四角与固定32段实际像素，两者及解析值max差<=2/255。numeric测试同时检查normal/tangent全分量与uv0–uv3，Shader单次打包未读取的分量只宣称数值验证。诊断材质仅供该验证，不代表第三方Shader兼容。

另外截图实际UGUI默认材质显示：不透明和透明输入在已知背景上合成，固定1280×720；该图用于布局、裁剪和用户视觉诊断，不与原始线性RenderTexture混合统计。实测记录活动颜色空间、分辨率、Shader名称/是否supported、实际模式和顶点数。测试/截图/文件导出与正式性能采样分开。

## 必需集成

生成GradientLab单一场景：大图、可见Grid、RectMask2D滚动裁剪内容，真实Simple（含preserveAspect）、Sliced、Tiled、Filled Radial图像。用于降级的sprite具有非零border，径向fillAmount为0.65，避免空白或无Sprite使类型路径退化。记录实际模式；非Simple必须VertexFallback并保持原Image拓扑。

受控附加通道输入由独立Graphic生成标准四角，组件沿边插值；Canvas显式开启TexCoord1–3、Normal、Tangent。渲染与附加通道相同材质下进行前后对照，禁止仅看shader源码声明通过。

场景创建拒绝覆盖已有场景，保存后恢复原SceneManagerSetup；测试与诊断结束恢复原场景、Play、临时设置并核查Console。开始前冻结完整Unity输入，测试遵守operation journal；任何失败保留原始输出并以新候选重验。

## v2 受控渲染前置（阈值保持不变）

r2附加通道像素max误差0.00232077已达原阈值；RGB因Canvas默认转换未保持encoded-rgb，原结果失败保留。受控raw诊断必须显式canvas.vertexColorAlwaysGammaSpace=true并断言，既不修改Gradient Runtime也不把默认Canvas转换误差当Mesh错误。

诊断临时使用现有URP-Performant管线的内存副本（Renderer无Feature），禁用HDR/MSAA/后处理/XR/stack/动态分辨率，目标R8G8B8A8_UNorm线性256×128单采样。保存并恢复原QualitySettings.renderPipeline引用，不改原管线资产。专用layer31隔离其他物体；相机viewport与图元四角实际投影均验证落在目标边界。每张PNG同时保存raw RGBA字节、哈希和JSON环境/帧号/Shader/Canvas开关，以数据判据作为验收。该无Feature配置只用于颜色/通道诊断；默认UGUI演示和后续正式Player仍用原项目配置。
