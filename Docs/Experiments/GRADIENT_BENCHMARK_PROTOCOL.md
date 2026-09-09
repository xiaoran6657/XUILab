# Gradient Player 成本矩阵 v1

- experiment_id: gradient-baseline-v1
- protocol_version: xuilab.benchmark.protocol/v1
- contract_id: gradient-schlick-v1
- stage: M2-04
- status: 执行前设计；正式plan/build身份在首轮前冻结

## 问题与边界

测量固定32段渐变在静态、重复setter与持续过渡中的工作量及帧时，观察规模、裁剪和Canvas划分的影响。连续颜色函数、Start/End、数据布局和确定性动作均冻结；不预设非线性或分Canvas一定更快。Image-only与disabled是一组视觉等价基础成本对照；static与same-value相同画面且参数不变；shared few与split few相同颜色/位置/动作，仅Canvas划分不同。Linear与Nonlinear具有不同曲线质量，跨状态成本展示不称为无损优化。静态/动态画面随动作区别明确标记，不能相减后命名为独占Mesh耗时。

## 固定环境与窗口

2022.3.45f1c1，Windows x64 Development/Mono，D3D11，960×540，项目Linear，原URP-HighFidelity，VSync0，targetFrameRate=-1不限帧。60FPS体验不与本矩阵混合。300帧预热、1800帧采样、容量1800、每组5个新Player进程，预算16.6666667ms。每进程wall-clock上限180秒；总上限覆盖全部计划timeout。按组清单正序/逆序/正序/逆序/正序执行五轮，任意两组相对顺序为ABBAABBAAB。保留失败/失焦/暂停/超时，按v1invalid规则处理，不能删除大帧或挑选最好一轮。

正式采样期间无截图、视频、MCP轮询、文件输出或同机其他Unity构建/测试。启动/结束仅操作本次创建PID。运行参数、候选输入/build、计划完整SHA及所有run-id在启动前绑定；无源码提交的本阶段数据标为受控开发基线，不当作M4公开发布数据。

## 代表矩阵（26组、130次预定运行）

| 布局 | N | 状态 |
| --- | --- | --- |
| Grid | 100 | image, disabled, linear, static, same, few, all |
| Grid参数补充 | 100 | Vertical static bias .25；Horizontal static bias .05/.95 |
| Grid | 500 | static, all |
| Grid | 1000 | static, all, few |
| Split Canvas Grid | 1000 | few |
| RectMask2D列表 | 1000 | static, all, few |
| 单张大图 | 1 | linear, static, all |
| Grid压力 | 2000、5000 | static, all |

流程pilot成功后再运行压力组；压力失败保留完整原因与共同规模，不降画质。Grid全部图元排列在固定边界内，矩形布局按N确定；裁剪列表固定行高24、viewport450、offset0，N是生成数，真实可见/被裁剪数单列，不能将N=1000称为同时渲染1000。few只改变实际可见集合前ceil(visible/10)个元素；all改变全部可见元素。Split把同一few集合放入独立Canvas，其余位置/材质/颜色不变。

Start=(.04,.75,.95,1)，End=(.95,.15,.4,.6)；默认Horizontal、bias=.25。表内三组参数补充实际覆盖Vertical及极端bias；除这三组外保持Horizontal/bias .25。极端组质量可为quality_limited，不混入quality-pass改进对照。动态按Runner帧序号、600帧周期三角波推进bias .25→.75→.25，Controller.Automatic=false；每帧显示由同一progress决定。same对同一值重复赋值。image无Effect，disabled拥有关闭Effect；其他使用同一共享UGUI材质与白纹理，不复制材质。

## 采样与验证

动作在帧N Update，完整帧间隔在N+1对应sample。专用gradient-samples保存action_frame与settled_frame，上一动作的dirty/rebuild增量、选中segment、最后提交vertex/triangle与实际可见/culled数；最后动作必须在EndMeasure收集，不能丢尾。所有数组预分配，采样期只写内存。sum计数是组件工作观测，RebuildCount不命名为Canvas全量重建或GPU成本。额外指标（DrawCalls/Batches/UI marker/GC/GPU）先探测，不可用明确unavailable，不能写零。

稳态static/same组件dirty/rebuild增量应为0；动态被选中元素在参数变化时dirty，实际Mesh模式应固定32/66/64。Image/disabled保持原4顶点路径；fallback不伪装成完整曲线。运行结束先验证实际组件/数量/最后状态，再导出CSV与质量；清理对象并验证终态。

质量与同一合同绑定，4097点RGBA等权。持续过渡 .25–.75 的最坏质量参考按区间端点和确定性动作采样评估，公开误差不只挑最后帧；输出continuous/fixed与Color32分离。极端bias .05/.95固定32不能达0.01，后续M3保留quality_limited状态。

复核器必须读取计划、core配置/环境/身份、samples.csv、gradient-samples/metrics、quality和完整artifact hash，重算每轮分位数、数量、索引、RGBA误差，并检查candidate/build/source/dirty/分辨率/配置相同；只通过JSON结构的Tools/GradientLab analysis不作为Player证据。每轮分位数按(n-1)p线性插值；跨轮报告median、range、MAD/IQR，禁止拼接帧。改进阈值据基线MAD/实际波动判断，不能事后固定漂亮百分比。

## 展示

第二组说明图及短视频另跑，记录参数、fallback和正式run-id；截图/视频中实时统计为诊断，不能替代以上数据。报告分正确性、测量有效性、性能比较三层；可得结论包括no_clear_difference或inconclusive。解释细分顶点、重建、材质/纹理/裁剪与合批关系；缺DrawCalls等原始观测时只解释机制、不声称实测批次不变。

## 冻结动作与几何细节

除image/disabled/linear外均为Nonlinear固定32段。same每个动作帧对全部N个Effect各赋Start/End/Direction/Curve/Bias同值一次；few/all仅对冻结索引集合调用Controller.SetProgress，Automatic=false、Linear easing，单方向半周期300帧，0..299对应progress0..1；每半周期重新StartTransition并反向，形成600帧往返。warmup也执行同一动作；BeginMeasure恢复起始bias并ForceUpdate，采样前完成。

Canvas使用ConstantPixelSize、scaleFactor1，Screen固定960×540；无Raycaster/文字。Grid边界宽900高480、中心(0,0)，cols=ceil(sqrt(N*900/480))，rows=ceil(N/cols)，行优先索引；cellWidth=900/cols、cellHeight=480/rows，矩形为cell尺寸*0.9，中心从(-450+cellWidth/2,240-cellHeight/2)递推。所有N位于边界。Split采用相同几何，前ceil(N/10)索引放入单独子Canvas（overrideSorting=false、无额外材质），其余属根Canvas。

单图宽900高450中心0。裁剪viewport宽900高450中心0，所有行宽880高24、顶端起始0、中心y=225-12-24*i；前19行与viewport相交（第18行部分可见），其余culled。冻结visible索引为0..18，few为0..1，all为0..18。Grid few为0..ceil(N/10)-1，all为0..N-1。运行中逐帧核对CanvasRenderer.cull，漂移则correctness fail，不临时改变目标集合。

M2-02数学/拓扑/通道/生命周期与M2-03真实类型/Shader/像素证据是构建前语义gate；冻结新Runner候选后比较这些源码哈希，发生相关变化必须重验。控制器仅在半周期边界启动一次，不能每帧重复StartTransition人为增加额外dirty。
