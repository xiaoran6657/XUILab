# 源码、实验、Profiler与归档导航

[学习入口](README.md) · [基础](FOUNDATIONS.md) · [列表](LIST_REFRESH.md) · [渐变](GRADIENT_SUBDIVISION.md) · [Profiler](PROFILER_GUIDE.md)

本篇是给读者与Agent的定位表。优先使用相对文件链接和函数/字段名，不依赖聊天记录。数值的权威来源仍是对应实验报告与原始文件；不要将本教学文件当作新的性能采样。

## 1. 先按问题找入口

| 疑问 | 教学入口 | 权威说明/代码 | 下一步读什么 |
| --- | --- | --- | --- |
| 为什么刷新一项却Bind九项？ | [列表](LIST_REFRESH.md) | [旧基线诊断](../Experiments/LIST_REFRESH_BASELINE.md) | [trace.json](../../Artifacts/list-refresh-trace-r1/trace.json)，找name=middle/backend=normal |
| 新策略如何确保离屏项不显示旧内容？ | [列表](LIST_REFRESH.md) | [ListView.cs](../../XUILab/Assets/XUILab/ListLab/Runtime/ListView.cs)，UpdateItem及pending相关分支 | [RefreshUpdateTests.cs](../../XUILab/Assets/XUILab/ListLab/Tests/PlayMode/RefreshUpdateTests.cs) |
| 改进到底有多大？ | [列表](LIST_REFRESH.md) | [列表结果](../Experiments/LIST_REFRESH_RESULTS.md) | [逐轮比较表](../../Artifacts/list-refresh-player-r4/report-r2/comparison-table.json)与[复算明细](../../Artifacts/list-refresh-player-r4/matrix-verification-r1.json) |
| 渐变函数是什么？ | [渐变](GRADIENT_SUBDIVISION.md) | [GradientFunction.cs](../../XUILab/Assets/XUILab/GradientLab/Runtime/GradientFunction.cs) | [渐变合同](../Experiments/GRADIENT_CONTRACT.md) |
| 截面如何变成网格？ | [渐变](GRADIENT_SUBDIVISION.md) | [GradientEffect.cs](../../XUILab/Assets/XUILab/GradientLab/Runtime/GradientEffect.cs) | [GradientMeshTests.cs](../../XUILab/Assets/XUILab/GradientLab/Tests/EditMode/GradientMeshTests.cs) |
| 自适应怎样选择、何时不能达标？ | [渐变](GRADIENT_SUBDIVISION.md) | [GradientSegmentSelector.cs](../../XUILab/Assets/XUILab/GradientLab/Runtime/GradientSegmentSelector.cs) | [GradientAdaptiveTests.cs](../../XUILab/Assets/XUILab/GradientLab/Tests/EditMode/GradientAdaptiveTests.cs) |
| 固定和自适应为什么结论不同？ | [渐变](GRADIENT_SUBDIVISION.md) | [固定段结果](../Experiments/GRADIENT_SUBDIVISION_RESULTS.md)、[自适应结果](../Experiments/GRADIENT_ADAPTIVE_RESULTS.md) | [自适应矩阵报告](../../Artifacts/gradient-adaptive-player-r1/matrix-report-r1.json) |
| CPU/GC为什么是unavailable？ | [Profiler](PROFILER_GUIDE.md) | [BenchmarkMeasurement.cs](../../XUILab/Assets/XUILab/Benchmarking/Runtime/BenchmarkMeasurement.cs)，UnityProfilerMetricProbeSet | 原始environment的metricCapabilities及samples可用性字段 |
| p95如何计算？ | [基础](FOUNDATIONS.md) | [BenchmarkMeasurement.cs](../../XUILab/Assets/XUILab/Benchmarking/Runtime/BenchmarkMeasurement.cs)，PercentileSorted | [统计测试](../../XUILab/Assets/XUILab/Benchmarking/Tests/EditMode/BenchmarkStatisticsAndArtifactsTests.cs) |
| 当前为什么仍保持旧默认？ | 两篇专题 | [综合决定](../Experiments/M3_OPTIMIZATION_DECISIONS.md) | 兼容、质量边界、生命周期代价，而不是只看最好的一组 |

## 2. 从一个报告数字追到原始帧

以列表“virtual-high-fps-1”组为例：

1. 在[结果报告](../Experiments/LIST_REFRESH_RESULTS.md)找到场景、Window/Target、五轮p95中位数。确认不是fps60组，也不是normal组。
2. 打开[计划](../../Artifacts/list-refresh-player-r4/matrix-r4.json)，定位同场景与轮次，取得真实run-id与配置；不要凭数字顺序猜目录。
3. 在[复算明细](../../Artifacts/list-refresh-player-r4/matrix-verification-r1.json)按runId定位，读frameP95、bindDelta、environment与指标能力；结合[比较表](../../Artifacts/list-refresh-player-r4/report-r2/comparison-table.json)确认汇总口径。
4. 在[运行根目录](../../Artifacts/list-refresh-player-r4/)定位该run-id下的config、identity、samples、summary、日志。字段结构以实际JSON/CSV为准，不能假定所有实验文件完全同schema。
5. 用[refresh_verify.py](../../Tools/ListLab/refresh_verify.py)了解单run校验，再用[refresh_report.py](../../Tools/ListLab/refresh_report.py)了解多轮比较；需要真正执行时先读[复现手册](../Agents/REPRODUCIBILITY_PLAYBOOK.md)，不要把程序导入或--help当成完整验证。

对自适应渐变，先读[最终报告](../../Artifacts/gradient-adaptive-player-r1/matrix-report-r1.json)的comparisons：baselineP95、variantP95、pairedDeltas、thresholdMs、result、scenario；再根据报告及[实验说明](../Experiments/GRADIENT_ADAPTIVE_RESULTS.md)定位matrix/matrix-recovery1/matrix-recovery2三个有效来源。五轮成对数据不可只取较快一轮。

复算代码入口：[adaptive_final_report.py](../../Tools/GradientLab/adaptive_final_report.py)、[adaptive_verify.py](../../Tools/GradientLab/adaptive_verify.py)。这些是离线分析，不是Profiler捕获工具。failed-attempt等排除记录同样是证据的一部分。

## 3. 从真实trace追到诊断代码

[trace.json](../../Artifacts/list-refresh-trace-r1/trace.json)的schema为xuilab.list.refresh-trace/v1，candidate为list-refresh-trace-r1。挑选traces中name=middle、backend=normal：target=14、totalBinds=9、targetBinds=1、scannedCells=1000。它观察旧M1 Runtime，通过反射替换内部数据后调用原RefreshItem；不能假装是当前UpdateItem公开API的运行。

[RefreshTraceTests.cs](../../XUILab/Assets/XUILab/ListLab/Tests/PlayMode/RefreshTraceTests.cs)是诊断入口；读mutation说明、snapshots.phase、累计计数与前后差值、事件index、清理断言。[trace复算结果](../../Artifacts/list-refresh-validation/trace-r1-verification.json)与[refresh_trace_verify.py](../../Tools/ListLab/refresh_trace_verify.py)说明如何核验。不要重新运行旧诊断来覆盖同名历史输出。

旧源码可从[冻结基线](../../Artifacts/baselines/list-refresh-trace-r1/)或下表历史归档读取；阅读时使用冻结副本，活动Unity工程仍只有仓库XUILab/，不在副本启动另一个Editor。当前源码用于理解新行为，冻结源码用于解释旧观测。

此trace的cpu、canvasRebuild、layoutRebuild标记unavailable。即使看见9次Mesh探针事件，也没有每次执行时间。真正CPU Timeline仍需另行独立采集；操作方法和记录模板见[Profiler篇](PROFILER_GUIDE.md)。

## 4. 证据身份与搬迁

本机Artifacts被Git忽略。只有源码新检出时，Markdown代码链接通常还在，但原始数据/图片/视频链接可能缺失。Agent应报告具体缺失路径并寻找以下归档，不应重新编造数字或自动启动数小时实验。

| 所需材料 | 入口 | 身份/说明 |
| --- | --- | --- |
| M3最终源码、干净Development构建与57项回归 | [最终包](../../Artifacts/m3-final-checkpoint-r1/index.json) | source399a4fc，clean源码；构建实际源019d668；不包含本次新Learn文档 |
| 可信包哈希与验收回执 | [最终归档回执](../../Artifacts/m3-final-checkpoint-receipt-r1.json) | 包索引SHA以回执为准，不根据可修改index自己宣称可信 |
| M2/M3历史实验、图与失败尝试 | [历史包](../../Artifacts/m3-final-source-archive-r1/index.json) | b40eac4+dirty历史身份，保留原始样本 |
| 更早M1/INFRA资料 | [旧归档](../../Artifacts/infra-d-final-archive/index.json) | 根据其index和[M1证据索引](../PM/Tasks/M1-04/EVIDENCE_INDEX-r3.md)读取 |
| 三个包的交接关系 | [M3本地检查点](../PM/M3_LOCAL_CHECKPOINT.md) | 最终包与历史包是配套交接，不能用短smoke替代正式历史矩阵 |

历史包内的extra根：list-trace、list-refresh、gradient-baseline、gradient-fixed、gradient-adaptive。其内通常保留XUILab/、Tools/、Docs/、Artifacts/等相对结构；先读索引找到具体成员，不能仅把原路径字符串机械替换。当前[冻结列表刷新](../../Artifacts/baselines/list-refresh-update-r3-r2/)、[固定段](../../Artifacts/baselines/gradient-subdivision-r2-r1/)、[自适应](../../Artifacts/baselines/gradient-adaptive-r1-r2/)也是可直接阅读入口。

完整归档检查见[source_archive.py](../../Tools/Archiving/source_archive.py)与[源码归档手册](../Agents/SOURCE_ARCHIVE.md)。本教学任务没有重打包或改写历史归档；因此新Learn文件要随当前工作区一并提供，不能声称已存在于399a4fc归档中。

## 5. 获取帮助时最小上下文

向Agent提供：本篇链接、专题标题、你不理解的一句、相关报告行/场景或run-id。Agent应先说明术语，再打开所链源码和数据，最后用“观察→解释→不能证明什么”回答。

- 只问为什么：读源码与现有证据即可，不需要Unity。
- 要核实某个统计数字：先定位run-id和samples，再使用对应版本离线验证器。
- 要确定CPU/GPU瓶颈：现有计数不够，先说明缺哪项诊断，再根据当次授权采集。
- 要修改实现/重跑正式实验：属于新的执行请求，遵守PM与Unity单操作者合同。

尚未读懂不影响文件正确性；材料通过链接检查也不证明用户已经掌握。当前动态安排见[Next Actions](../PM/Next_Actions.md)。

## 6. 可复制的只读定位示例

在仓库根运行以下PowerShell命令，只显示选中trace的关键字段，不把整个大型JSON打印出来：

```powershell
$traceData = Get-Content -Raw -LiteralPath 'Artifacts/list-refresh-trace-r1/trace.json' | ConvertFrom-Json
$traceData.traces | Where-Object { $_.name -eq 'middle' -and $_.backend -eq 'normal' } |
    Select-Object name, backend, target, targetBinds, totalBinds, scannedCells, cpu, canvasRebuild
```

应看到target14、targetBinds1、totalBinds9、scannedCells1000，cpu和canvasRebuild为unavailable。这里只读现有数据；不是重新运行诊断。

查当前实现符号可用：

```powershell
rg -n 'UpdateItem|pending|TargetOnly' XUILab/Assets/XUILab/ListLab/Runtime/ListView.cs
rg -n 'Select|quality|cache' XUILab/Assets/XUILab/GradientLab/Runtime/GradientSegmentSelector.cs
rg -n 'PercentileSorted|FrameInterval' XUILab/Assets/XUILab/Benchmarking/Runtime/BenchmarkMeasurement.cs
```

搜索只提供定位，不能代替读取调用上下文与测试；如果当前源码和本文方法名不同，先查Git身份，不把最新实现反套到旧数据。没有rg时可用编辑器文件内搜索。
