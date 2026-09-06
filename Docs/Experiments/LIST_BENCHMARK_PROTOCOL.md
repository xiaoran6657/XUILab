# List Lab A/B 协议 v1

实现前冻结：2026-09-06。来源：[List 合同](LIST_CONTRACT.md)、[测量协议](../MVP/MEASUREMENT_PROTOCOL.md)。Runner 基础协议保持 `xuilab.benchmark.protocol/v1`；扩展记录单独使用 `xuilab.list.metrics/v1`，不改变 M0 的 22 字段 summary。

## 问题与冻结变量

比较普通 ScrollRect 与独立固定行高虚拟窗口，在同输入/视觉/动作下的帧间隔与实例数量。假设虚拟实例数量有界；帧时结果可以改善、退化、无清晰差异或 inconclusive，不设收益百分比。

同一 Windows x64 Development / Mono Player 与 ListLab 场景；960×540、Canvas pixel size 1、720×384 视口、48 px 行高、UGUI LegacyRuntime 字体18、同 Cell 工厂/Binder、单模板、seed 1337。动画/渐隐/动态诊断关闭。每个新进程只创建一个后端。配置 caseId 精确表达 `list-{normal|virtual}-{100|300|1000|10000}-{scroll|lifecycle}`；caseVersion=1，数据和动作由此唯一决定。

共同主矩阵：100、1000 × scroll/lifecycle × uncapped（-1）。60 FPS 体验补充：1000 × scroll。各配置 300 warmup / 1800 sample / 5 个新进程；A/B 顺序 `ABBA ABBA AB`，先100再1000，每个N先scroll再lifecycle，最后60 FPS补充。300/10000 在主矩阵有效后各做单轮 exploratory 压力检查，不进入5轮聚合；单进程预算180秒。冻结后用新的 candidate/build/run id；不覆盖失败轮。

## 动作时间线

所有动作在 C# TickMeasure(i) 中执行，由 M0 Runner 在下一帧采样。轨迹与帧率无关，两后端获得完全相同 offset。

- scroll：1800帧连续三角轨迹，周期600帧；从0到MaxOffset再返回0，终点保留。预热300帧执行同一轨迹，覆盖最大窗口；测量前记录 created/destroyed 基数。
- lifecycle：0–299 静置；300–1199 一个往返滚动周期；1200跳首；1260跳尾；1320保存45.25%位置；1380跳首后恢复保存位置；1440清空；1500重填相同快照并恢复保存位置；1560禁用；1620重开；其余保持。
- 冷开：Prepare 内从创建 ListLab Canvas 到初次 SetItems/Layout 的同步耗时，另记到下一帧 Canvas 已完成布局的首次可交互时间。均不包含进程启动/场景加载，不称为完整启动耗时。

## 记录与有效性

基础七文件保持原 schema；List Case 另外导出 `list-metrics.json` 与 `list-samples.csv`，仅在采样外写入。逐动作预分配结构记录 frame index、offset、visible、active、leased、cached、created/destroyed、Bind/Unbind；原始计数与 Frame Interval 按同一 action index 对齐。correctness 检查每个阶段的内容/实例/位置，稳态 scroll 预热后不得继续创建销毁；normal保有N实例，virtual <=13 leased、单模板 unique <=29（窗口+缓存），实际稳态预计<=13但以实测为准。

required 性能指标仍仅 Frame Interval；Main Thread/GC/System Memory 可用性沿用实际探测。UI rebuild/batches/vertices 未探测到则 unavailable，不从 Bind 推断；本轮可选缺失不影响基本帧间隔比较。JSON不可用指标为null及原因。

检查 config 精确字节SHA、candidate/build/source、运行集合/顺序/index、环境一致性、完整1800行、连续索引、summary重算、list样本计数/位置/功能终态。失焦/暂停/尺寸变化/超时/失败整轮invalid或failed，保留失败目录和进程旁证。高波动不删除帧；新run-id重跑同配置，排除依据必须是预设invalid规则。

逐轮p50/p95/p99/max/over-budget依协议插值，跨5轮报告median/range/MAD/IQR，不拼帧。p95两组范围不重叠且差值超过双方MAD之和时描述观察到的方向，否则inconclusive；帧间隔不是组件CPU耗时。冷开和生命周期阶段功能独立解释。未提交候选结果是探索性工程基线；M4公开数字需干净提交重建。

## 媒体与保留

截图及30–60秒视频草稿单独运行，媒体不并入采样。原始记录/构建/媒体在被忽略的 `Artifacts/`，PM索引文件集SHA与恢复入口。主 Agent采样期间不操作其他Unity实例；不能证明外部项目无负载时在环境限制中记录。
