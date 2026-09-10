# Agent Benchmark：让自动测试正确报告成功、失败和无效

本文介绍 XUILab 的配置驱动 Unity Benchmark Runner。重点是可重复的状态机、身份和错误识别，结果不是 Agent 数量、工具调用次数或无人值守时长。当前案例对应候选 `m4-final-b017672`，展示 smoke 与正式性能矩阵分开保存。

## 1. 背景与约束

自动化性能测试常见的一类问题是：脚本启动了程序，却没有确认场景已就绪、样本够不够、窗口是否失焦，最后把异常或半截数据当成成功。另一个问题是把“功能正确”“样本有效”和“策略更快”写成一个 PASS，导致失败原因无法恢复，也无法复查来源。

本项目把身份、状态、正确性和 measurement validity 分开。正式性能只要求 `Frame Interval`，缺失的可选 Main Thread、GC 和系统内存保留为 `unavailable`。展示中的 fail/invalid 是预设诊断案例；它们用于证明错误边界，不进入 List 或 Gradient 正式性能数字。

## 2. 我的工作边界

| 范围 | 本案例如何归属 |
| --- | --- |
| Unity 基础 | Unity Player 生命周期、UGUI 场景和系统指标接口属于第三方基础。 |
| XUILab 工程 | 配置合同、`BenchmarkRunner` 状态机、artifact writer、指标探针、命令行解析和 fault injector 是项目自动化实现。 |
| Agent 工作 | Agent 按授权准备候选、构建、启动、读取终态和聚合报告；它不能凭退出码或截图创造样本。 |
| 学习状态 | `Docs/Learn/FOUNDATIONS.md`、`PROFILER_GUIDE.md` 和 `EVIDENCE_NAVIGATION.md` 是教学材料；用户个人是否理解或独立完成实现未确认。 |

第三方依赖、项目贡献和分发限制见[来源说明](../SOURCES.md)。

## 3. 技术问题

一次可靠运行要有明确输入：`candidateId`、`buildId`、`sourceRevision`、`runId`、场景、预热帧、采样帧和输出根。还要有明确顺序：Prepare、Warmup、Measure、Validate、Export、Cleanup。本展示预设的无效配置应是 `Failed / NotRun / NotAssessed`；样本不足、必需指标缺失、失焦或暂停可以完成导出，但必须是 `Invalid`；只有完整样本、正确性通过、导出和清理都成功才是进程成功。

## 4. 设计与实现

`BenchmarkCommandLine.TryCreateRunConfig` 接受 `--xuilab-run`、case、run-id、输出根和 fault 参数，并由 `BenchmarkRunConfig.Validate` 拒绝未知协议、不安全路径和占位身份。`BenchmarkRunnerHost.Update` 把 `Time.unscaledDeltaTime` 转成毫秒交给 Runner；`OnApplicationFocus` 和 `OnApplicationPause` 在运行中记录外部无效。

`BenchmarkRunner` 固定推进 `Idle → Prepare → Warmup → Measure → Validate → Export → Cleanup`，`Validate` 依次检查 case correctness、样本数量、required metric 和外部状态。`BenchmarkFaultInjection.ConfigurableBenchmarkFaultInjector` 可确定性注入 prepare failure、ready timeout、sample shortage、case exception、export failure、focus loss 和 pause。`BenchmarkArtifacts.FileBenchmarkArtifactWriter` 保留 `config.json`、`environment.json`、`identity.json`、`samples.csv`、`summary.json`、`report.md` 和 `events.log`。源码入口见[BenchmarkRunContracts](../../../XUILab/Assets/XUILab/Benchmarking/Runtime/BenchmarkRunContracts.cs)、[BenchmarkRunner](../../../XUILab/Assets/XUILab/Benchmarking/Runtime/BenchmarkRunner.cs)、[BenchmarkRunnerHost](../../../XUILab/Assets/XUILab/Benchmarking/Runtime/BenchmarkRunnerHost.cs)、[BenchmarkFaultInjection](../../../XUILab/Assets/XUILab/Benchmarking/Runtime/BenchmarkFaultInjection.cs)和[BenchmarkArtifacts](../../../XUILab/Assets/XUILab/Benchmarking/Runtime/BenchmarkArtifacts.cs)。

## 5. 验证方法

Runner 的单元和完整程序集门禁覆盖状态转换、统计、身份、清理和故障终态；Release smoke 则在独立展示构建中用脚本动作检查三种终态。正式矩阵仍按各自主题的 300 帧预热、1800 帧采样和五轮成对协议运行，Agent 案例只引用已生成回执。

| 层次 | 证据 |
| --- | --- |
| Runner 门禁 | Core 32/32、Runner 8/8；其余主题回归按[验证记录（历史记录未公开）](../HISTORICAL_RECORDS.md)列出，数量有重叠，不相加冒充独立总数。 |
| 展示 smoke | `m4-final-media/smoke-r1-receipt.json`，32 checks、6 images、恢复 `pass`、整体 exit 0。 |
| 正式矩阵 | List 50 + Gradient 80，共 130 次有效 `pass / valid`。 |

## 6. 结果

| 预设案例 | Runner 终态 | correctness / validity | exit |
| --- | --- | --- | ---: |
| normal | `Completed` | `Pass / Valid` | 0 |
| fail | `Failed` | `NotRun / NotAssessed` | 1 |
| invalid | `Completed` | `Pass / Invalid` | 3 |

这张表来自[最终 smoke 回执（历史记录未公开）](../HISTORICAL_RECORDS.md)。整体 exit 0 表示展示验证正确识别了三个终态，不表示内部 fail 或 invalid 是性能成功。在形成正式 130 次有效样本的过程中，另有两次实际编排失败且没有 raw：列表第 15 次 180 秒 timeout，以及渐变第一次使用错误的默认 ListLab 入口而 exit2。两次失败的启动、日志和终态仍保留，未伪造 samples，也未删除失败目录；它们与 smoke 里的预设 fail case 是两类记录。

## 7. 学习与适用边界

可推广的原则是把“程序退出”“功能通过”“样本有效”“性能比较”拆成不同判据，并为每次运行保留可验证身份。配置驱动和确定性故障让复跑更容易发现回归。当前 Runner 记录的是帧间隔和可用能力，不是 Profiler CPU Timeline 或 GPU capture；因此不能据此宣称某个 Agent 更聪明、某函数更快或零 GC，也不能把展示 smoke 当成正式矩阵。

## 8. 复跑与证据

从[证据索引](../EvidenceIndex.md)查看 candidate、Development／Release build-id 和失败记录，再用[RUN_INDEX](../RUN_INDEX.md)定位 130 个 run-id；[结果报告](../RESULTS.md)给出两主题的统计边界。代码和术语可沿[基础学习篇](../../Learn/FOUNDATIONS.md)、[Profiler 边界](../../Learn/PROFILER_GUIDE.md)和[证据导航](../../Learn/EVIDENCE_NAVIGATION.md)追读。展示回执的原始根固定在 `Artifacts/m4-final-media/`，正式样本分别在 `Artifacts/m4-list-runs-r1/`、`Artifacts/m4-list-runs-recovery-r1/` 和 `Artifacts/m4-gradient-runs-r2/`；复跑必须传入新的 run-id，并保留 candidate、build-id、sourceRevision、config、raw、summary 和终态 receipt 的绑定。[媒体画廊](../MEDIA.md)提供实际视频和说明图。
