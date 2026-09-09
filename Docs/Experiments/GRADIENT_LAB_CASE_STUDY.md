# GradientLab 实现与学习案例

这是依据历史主题进行的个人复现，性能数字属于本仓库的Windows Development Player，不是实习原项目实测。结果与限制以[固定32基线报告](GRADIENT_BENCHMARK_RESULTS.md)为准。

## 为什么四个顶点不够

矩形只有两个颜色端点时，三角形光栅化沿轴做线性插值。一般非线性Schlick曲线在两个端点之间弯曲，因此需要内部采样点；固定32段用33个截面、66顶点和64三角形形成分段线性近似。bias改变的是[颜色函数](GRADIENT_CONTRACT.md)，不能通过移动颜色语义来制造所谓优化。合法Simple矩形才细分；Sliced/Tiled/Filled保留原有拓扑，仅按已有顶点着色并报告VertexFallback。

## 成本在哪里

静态Mesh建立后可以复用，同值setter先比较后退出。参数真的变化才触发Graphic的vertex dirty，组件重新计算采样颜色与顶点，并由UGUI提交；共享Canvas还可能有相关重建与批处理组织成本。实际统计的是组件dirty/rebuild次数，而不是整个Canvas rebuild次数。全量动态Grid的成本随更新元素数明显增长；要区分组件处理、Canvas组织和GPU，需要另行诊断，不能把总帧间隔相减冒充纯Mesh时间。

组件不克隆共享材质，白纹理也共享，这使其具备维持合批的条件，但材质/纹理/裁剪状态、Canvas边界和渲染次序都会影响批处理。更多顶点不必然增加DrawCalls，也不等于免费；缺少真实batch计数时仅作机制解释。RectMask2D可减少可见提交工作量，但仍有生成对象和裁剪管理，不能把生成1000行说成显示1000行。拆分Canvas可隔离一部分动态dirty传播，同时也可能增加Canvas和batch成本；本次小幅趋势不足以普遍推荐拆分。

## 为什么更多段数仍有色带

细分降低连续曲线的分段线性误差；Color32的8位颜色量化、显示/输出空间和像素覆盖是另一些误差来源。固定32在bias .25达到约0.00122的函数最大误差，在.05/.95却约0.03842。增加段数可能改善曲线近似，无法消除8位量化的台阶。报告分别列连续近似与量化，不把漂亮截图替代数值和受控像素测试。

## 第二组演示草稿

[20秒视频](../../Artifacts/gradient-media-r1/gradient-demo-r1.mp4)为Editor单独诊断采集，1920×1080、300帧、15fps编码；实际墙钟录制可慢于20秒，不是实时性能证明。大图Horizontal、fixed32、bias .05→.95→.05，Start=(.04,.75,.95,1)、End=(.95,.15,.4,.6)，范围比正式动态矩阵的.25–.75更宽，专门显示极端边界。网格包含两方向和.05/.5/.95，RectMask2D有12生成行并滚动offset0→440→0；Simple使用fixed32，Sliced/Tiled/Filled为3项VertexFallback。

性能关联plan为`gradient-matrix-r5`，代表run为`gradient-matrix-r5-gradient-grid-100-all-horizontal-25-r5`；演示布局与分辨率不同，不能将其画面诊断数字归入该run。参数逐帧记录、恢复、Console和完整解码结果见[媒体身份](../../Artifacts/gradient-media-r1/capture.json)、[验证](../../Artifacts/gradient-media-r1/media-validation.json)、[哈希](../../Artifacts/gradient-media-r1/ARTIFACTS.sha256)。无全黑帧，278个独特PNG，往返端点/颜色量化允许重复画面。

![起始bias .05及顶部裁剪](../../Artifacts/gradient-media-r1/frame-0000.png)

![终点bias .95及底部裁剪](../../Artifacts/gradient-media-r1/frame-0149.png)

## 可复述的学习闭环

观察：静态及同值setter成本接近，动态Grid随变化元素增加显著变慢，极端bias达不到固定32质量目标。假设：减少需要处理的元素/采样节点可能降低总成本，但Canvas及固定开销可能遮蔽收益。M2选择先固定语义、正确性和矩阵；M3再改变细分策略与单项刷新，做同条件复测。若质量不达标、成本无清晰差异或变慢，保留限制并维持原默认值，不预设优化百分比。

技术解释草稿已完成；用户学习复盘尚未安排，状态为not_run，与技术验收分开。
