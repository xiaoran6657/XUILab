# 列表刷新 Player A/B 协议 r1

在首轮Player执行前冻结。问题是同数据发布与可见内容下，TargetOnly减少窗口Bind是否改善帧时；不预设更快。

## 不变量与组

Windows x64 Development Mono，Unity2022.3.45f1c1、D3D11、960×540、现有ListLab场景和相同字体/UGUI/质量/颜色空间。N1000、双模板、48px行高、384px viewport、offset492、可见10–18九行、无动画/fade/用户输入、无滚动。两后端normal/virtual分别比较VisibleWindow/TargetOnly，不能跨后端把差异归因于刷新策略。

五种确定性动作：idle无更新作为测量与持续渲染对照；sparse每60帧1项；burst每60帧连续3次UpdateItem；high每帧1项；batch每帧以UpdateItems发布全部9项。目标序列10+(actionFrame+slot)%9；每个item在预建两套等长Label之间交替，数据对象及动作缓冲在准备期预分配。burst与batch属于不同调用合同，不能混算。

每个后端×动作×策略5个独立进程，策略顺序W,T,T,W,W,T,T,W,W,T；每组同策略轮号1–5。主矩阵不限帧target-1/VSync0（100runs），补充virtual/high的60FPS体验模式10runs；不将60与不限帧混合。先运行virtual/high与normal/batch各策略1次pilot，pilot不并入5轮统计。

## Runner 与指标

预热300帧，同动作；BeginMeasure保留确定性预热终态，仅登记起始计数/九项状态位，不进行SetItems/Canvas flush；避免初始化成本落入第一条帧间隔，采样1800帧/容量1800，readyTimeout300帧、wallclock180秒。动作在TickMeasure发生，核心Frame Interval采样在下一帧，必须逐行满足sample unityFrame=actionFrame+1。禁止采样期文件写入、截图/视频、MCP逐帧查询或重Profiler。

核心samples.csv保留frame interval、可用CPU/GC/memory；refresh-samples.csv保留动作/采样对齐、逐帧更新数、目标位掩码、累计Bind/Unbind、创建销毁/leased/cached/pending、可见Label状态校验和。每帧检查9个可见项最新ID/模板/Label及前一帧几何，结束另校验完整Pool/mapping并清理unique0。正式不安装dirty/Mesh探针；这两项证据使用独立PlayMode诊断，不污染Player测量。

required仅Frame Interval。CPU/GC/memory recorder缺失写unavailable，UI/Canvas/mesh marker未经验证也写unavailable。一次构建/初始化成本另列coldBuildMs，不把预热后数据叫冷开。

## 有效性、身份与停止规则

候选全源码/包/设置、构建完整文件、实际build operation和当前候选功能/Core/Runner门禁绑定。计划先落盘并SHA固定；Player校验收到的计划/构建清单/门禁SHA、运行ID唯一及实际执行exe。原始文件hash、config/identity/binding、真实进程exit、startFocus和采样期间失焦/暂停/分辨率漂移必须通过；正确性失败、缺required指标、超时或不完整样本不发布性能改善。

每run启动前先记录意图，结束保留receipt/log；同名已有成功run先复核，未决意图或失败不重发。任一失败停止计划，保留首因，先离线判断；不得删日志、改计划或反复重派。只有原输入确实不变时可按已验证未执行项续接，失败项另走明确恢复记录。

## 统计与判据

逐run使用线性插值分位数(p*(n-1))算p50/p95/p99/max/超过16.6666667ms比例，并展示五轮p95、跨轮中位数和波动，不合并进程样本。主比较配对同轮p95变化；若5对至少4对同方向、两组中位数差超过max(5%基线中位数, 两组p95全距的一半)才标improved/regressed；否则inconclusive。这个保守阈值事先冻结，不将显著性检验或普适硬件收益强加给5轮样本。

正确性与有效性先于速度。Bind减少不是Canvas或CPU同幅减少；batch两策略都应9Bind/帧，可能仅扫描开销不同，或无清晰差异。最终默认由M3-05结合收益/复杂度/维护决定；本任务先保留VisibleWindow默认。
