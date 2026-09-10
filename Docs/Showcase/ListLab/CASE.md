# List Lab：把“更新一项”变成可验证的刷新合同

本文对应冻结候选 `m4-final-b017672`。它讲的是 XUILab 中一个可复跑的 UGUI 列表实验：单项数据变化时，刷新可见窗口和只刷新目标索引两种策略怎样比较。这里的数字只来自当前候选的 Windows Development Player 运行，不把历史材料或一次 Editor 观察写成当前结论。

## 1. 背景与约束

实习和业务 UI 中常见的一类问题是：数据源很大，但一次只改了一项，界面却扫描整张列表并重新绑定多行。对象池可以减少反复创建和销毁；虚拟化可以减少活跃 Cell 数量；它们都不能自动保证“只更新目标”是正确的。早期诊断还容易把 Bind 次数当成毫秒，把 Editor 计数当成 Player 性能，因而缺少可审查的证据链。

本案例把问题缩成固定行高、`N=1000`、约 9 行可见窗口的合同。正式结论只覆盖报告选出的 5 组，未重测的 idle、sparse、burst 组合仍是探索结果。`Frame Interval` 是帧间隔，不是某个 C# 方法的 CPU 时间；CPU、GC 和系统内存指标没有可用样本时保留 `unavailable`。

## 2. 我的工作边界

| 范围 | 本案例如何归属 |
| --- | --- |
| Unity 基础 | Unity 2022.3、UGUI、URP、TMP 和渲染生命周期属于第三方基础，不算本项目原创实现。 |
| XUILab 工程 | `ListView`、`ListCell`、`ListCellPool`、`ListItem`、`FixedRowLayout` 及对应测试、Runner 合同是仓库中的项目实现。 |
| Agent 工作 | Agent 负责按配置构建、启动、收集、校验和汇总；它不替代代码所有者，也不把工具调用次数当成果。 |
| 学习状态 | `Docs/Learn` 是给读者的解释路线。用户是否已经亲自实现或理解这些内容没有在本案例中确认，文档不能代为宣称。 |

来源和第三方边界见[来源说明](../SOURCES.md)。

## 3. 技术问题

一次 `UpdateItem` 必须先发布数据，再决定显示同步范围。可见项不能显示旧值；离屏项可以暂时保持旧 Cell，但入屏或滚动时必须绑定新值。回调可能在设置文本时重入列表，Bind 失败还可能留下租借对象、映射和 pending 状态，因此“少做一次 Bind”不能牺牲恢复合同。

性能假设也要拆开：普通后端可能扫描 1000 个 Cell，虚拟后端通常只处理约 13 个租借 Cell；窗口策略和目标策略最后都可能 Bind 9 项。这个计数能解释工作量，却不能单独证明 CPU 或 Canvas 各省了多少。

## 4. 设计与实现

公开入口 `ListView.UpdateItem` 按 `BeginMutation → ValidateUpdate → Publish → RefreshPolicy 分支 → EndMutation` 工作。`VisibleWindow` 进入 `RefreshWindowCore`，刷新当前窗口；`TargetOnly` 进入 `RefreshIndexCore`，只对批次中需要同步的索引执行 Bind。`FlushPendingVisible` 在真实可见范围变化后处理 pending，保证离屏更新不会以旧文字入屏。

`ListCellPool.Rent/Rebind/Return` 管理 leased 与 cached Cell，`ValidateOwnership` 检查归属；`ListCell.Bind/Unbind` 重置视觉、写入索引和文本并记录计数。批量更新会先复制和验证全部输入，拒绝重复索引后再发布。实现和学习定义可沿[列表刷新学习篇](../../Learn/LIST_REFRESH.md)阅读，源码入口是[ListView](../../../XUILab/Assets/XUILab/ListLab/Runtime/ListView.cs)、[ListCell](../../../XUILab/Assets/XUILab/ListLab/Runtime/ListCell.cs)和[ListCellPool](../../../XUILab/Assets/XUILab/ListLab/Runtime/ListCellPool.cs)。

## 5. 验证方法

每次运行预热 300 帧、采样 1800 帧；每组 5 对独立进程交错执行。先计算每次运行的 p50/p95/p99，再用 5 轮 p95 的中位数和范围比较。判定要求至少 5 对中 4 对同方向，差值超过 `max(基线中位数的 5%, 两策略 p95 全距较大者的一半)`。这是本项目预先固定的操作阈值，不是显著性检验。

| 条件 | 实际身份 |
| --- | --- |
| 源码／构建 | `m4-final-b017672`；`m4-development-b017672-r1` |
| 环境 | Unity 2022.3.45f1c1、Windows 10、960×540、D3D11、VSync 0、High Fidelity、Mono Development |
| 覆盖 | normal/virtual；high/batch；另有 virtual 60 FPS 对照 |
| 正确性与有效性 | 50/50 运行 `pass / valid`，聚合校验 `pass`、失败数 0 |

## 6. 结果

| 组 | Window p95 中位 → Target p95 中位（ms） | 变化 | 判定 |
| --- | ---: | ---: | --- |
| normal-high-fps-1 | 28.755965 → 4.343835 | -84.89% | improved |
| normal-batch-fps-1 | 28.813529 → 4.824315 | -83.26% | improved |
| virtual-high-fps-1 | 0.927415 → 0.667820 | -27.99% | improved |
| virtual-batch-fps-1 | 1.005620 → 1.006910 | +0.13% | inconclusive |
| virtual-high-fps60 | 17.002206 → 17.002000 | -0.00% | inconclusive |

因此当前选定子集是 3 组 `improved`、2 组 `inconclusive`。高频单项更新中 Window 记录 16200 次 Bind、Target 1800 次；批量组双方都记录 16200 次 Bind，普通后端仍可能因扫描全表产生差异。不能把结果外推到未选 6 组、其他 N、冷启动或 FPS；报告中的 `coldBuildMs` 也不是应用冷启动时间。正式列表第 15 次曾发生 180 秒 timeout、没有 raw，失败目录被保留且不进入统计。

## 7. 学习与适用边界

可推广的原则是先定义数据、Cell 和画面各自的合同，再分别看扫描、绑定、布局和渲染；对象池、虚拟化和局部更新是不同层次的工具。`pending`、异常清理和重入测试是局部刷新必须支付的维护成本。当前数据只能说明这些条件下的帧间隔差异，不能说明某个函数、主线程或 GPU 单独省下了多少时间，也不能替用户完成个人学习复盘。

## 8. 复跑与证据

从[结果报告](../RESULTS.md)确认统计口径，再由[证据索引](../EvidenceIndex.md)追到候选、构建和原始目录；[RUN_INDEX](../RUN_INDEX.md)列出每个 run-id、变体和有效性。[聚合 JSON](../Data/list-report.json)、[计划（历史记录未公开）](../HISTORICAL_RECORDS.md)和[统计脚本（历史记录未公开）](../HISTORICAL_RECORDS.md)是当前实际输入。正确性测试见[RefreshUpdateTests](../../../XUILab/Assets/XUILab/ListLab/Tests/PlayMode/RefreshUpdateTests.cs)，术语和 p95 定义见[基础学习篇](../../Learn/FOUNDATIONS.md)与[Profiler 边界](../../Learn/PROFILER_GUIDE.md)。运行时产物在本地 `Artifacts/`，复跑时应保留 candidate、build-id、run-id、原始 samples 和失败记录的绑定关系。


[媒体画廊](../MEDIA.md)提供封面、三张说明图与45秒独立演示。
