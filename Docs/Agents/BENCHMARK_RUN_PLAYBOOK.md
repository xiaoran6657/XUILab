# Benchmark 复跑手册

适用版本：`xuilab.benchmark.protocol/v1`。本手册用于 XUILab 的 Windows Development Player 稳态测量；不能把 Editor、Release、不同协议或不同 candidate 的数据合并。

## 1. 运行前

1. 确认唯一工程根为 `<repo>/XUILab`，Unity 为 `2022.3.45f1c1`，目标为 Windows x64。
2. 记录 `candidate-id`、Git commit／dirty、候选源文件 SHA-256、`build-id`、构建选项和输出路径。dirty 运行只作开发／校准证据。
3. 在 Unity MCP 每组操作前重新列出实例并按完整 project root 选择 XUILab；不要复用历史实例 id，也不要操作同时在线的其他工程。
4. 读取 editor/project state，确认非 Play、非 paused、无编译／导入／测试／构建、无 Prefab Stage、当前 scene 已保存。正式采样时停止其他 Unity 操作、重型任务、截图、录屏和 Profiler 捕获。
5. 通过 `XUILab/Benchmarking/Build Development Runner Player` 构建。等待 BuildReport 终态，并保存 `Artifacts/<build-id>/build-summary.json`、Player 路径、大小、launcher EXE 和 `XUILab.Benchmarking.Runtime.dll` 的 SHA-256；Unity launcher EXE 在不同脚本构建间可能相同，不能单独证明代码身份。菜单调用成功不等于构建成功。

## 2. 协议 v1 固定值

| 项目 | 值 |
| --- | --- |
| tier | Windows x64 Development Player／Mono |
| window | 960×540；VSync 0 |
| warmup / measure / capacity | 300 / 1800 / 1800 frames |
| repeat | 每配置 5 个新进程 |
| required metric | Frame Interval (ms) |
| optional metrics | Main Thread、GC Allocated In Frame、System Used Memory；不可用写 unavailable/null |
| percentile | 排序后 `(n - 1) × p` 线性插值 |
| aggregate | 每轮先统计，再算 median、min/max、MAD、IQR；不拼接 frame |
| target modes | 60 FPS 与 uncapped (`-1`) 分开 |
| known-load | CPU iterations 4,000,000／frame；allocation 32,768 bytes／frame |

主序列顺序固定为 `idle1, load1, load2, idle2, idle3, load3, load4, idle4, idle5, load5`；recorders on/off 开销序列使用同一 `ABBA, ABBA, AB` 结构。不得在看到结果后挑轮或换顺序。

## 3. 主序列与开销序列

在仓库根使用唯一 UTC stamp；脚本拒绝覆盖同名 run：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Tools\Benchmarking\Invoke-XUILabM0Calibration.ps1 `
  -Mode Main -RunStamp <yyyyMMddTHHmmssZ> `
  -PlayerPath .\Artifacts\<build-id>\build\XUILab-M0-Runner.exe `
  -CandidateId <candidate-id> -BuildId <build-id> -SourceRevision <revision> `
  -RunTimeoutSeconds 180

powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Tools\Benchmarking\Invoke-XUILabM0Calibration.ps1 `
  -Mode Overhead -RunStamp <yyyyMMddTHHmmssZ> `
  -PlayerPath .\Artifacts\<build-id>\build\XUILab-M0-Runner.exe `
  -CandidateId <candidate-id> -BuildId <build-id> -SourceRevision <revision> `
  -RunTimeoutSeconds 180
```

脚本以 Windows PowerShell 5.1 隐藏窗口串行启动新 Player。每个进程退出后，入口先以 ordinal/case-sensitive 规则要求 summary 的属性集合精确等于协议 v1 的 22 个字段：`schemaVersion`、`runId`、`state`、`failureCode`、`failureReason`、`correctness`、`measurementValidity`、`performanceComparison`、`processSuccess`、`exitCode`、`enteredMeasure`、`exportSucceeded`、`cleanupSucceeded`、`sampleCount`、`p50FrameIntervalMs`、`p95FrameIntervalMs`、`p99FrameIntervalMs`、`maxFrameIntervalMs`、`overBudgetRatio`、`meanMainThreadNanoseconds`、`totalGcAllocatedBytes`、`lastSystemUsedMemoryBytes`；缺字段、额外字段和仅大小写不同的字段都拒绝。随后核对原始 string／boolean／integer／number/null 类型与有限数值。成功轮还必须以大小写敏感规则满足 process exit 0、terminal completed、`failureCode=none`、空 `failureReason`、correctness pass、measurement validity valid、performance comparison `not_assessed`、processSuccess true、summary exit 0、进入测量、export/cleanup success、1800 samples，并具有非 null 的有限 p50/p95/p99/max/over-budget；三个 optional 统计只允许 null 或对应有限 number/integer。

每轮默认 wall-clock timeout 为 180 秒；超时只终止该轮脚本启动的已知 PID。任何一项不符即停止后续序列，并保留 Player log 及 `Artifacts/<run-id>-orchestration-failure.json`；sidecar 同样覆盖启动失败、无／坏 summary 和 export failure。

离线复核与聚合：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Tools\Benchmarking\Get-XUILabM0CalibrationSummary.ps1 `
  -MainStamp <main-stamp> -OverheadStamp <overhead-stamp> `
  -CandidateId <candidate-id> -BuildId <build-id> -SourceRevision <revision>
```

验证器要求显式传入冻结的 candidate/build/source；精确匹配 20 个 run 与每组 index 1..5，使用 `-Force` 拒绝隐藏或普通额外 artifact，核对 JSON 原始类型与有限数值、配置／身份／环境 schema、optional capability `status/reason`、`config.json` 实际文件哈希、硬件环境指纹、CSV 1800 行／连续索引／累计时间，并从 CSV 重算 summary 后才聚合。recorders on/off 的范围重叠或差异小于轮间波动时写 `inconclusive`，不能写“零开销”。

在冻结候选上运行 verifier 的一项有效副本与十四项负向篡改测试：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Tools\Benchmarking\Test-XUILabM0CalibrationEvidence.ps1 `
  -ArtifactRoot .\Artifacts -MainStamp <main-stamp> -OverheadStamp <overhead-stamp> `
  -CandidateId <candidate-id> -BuildId <build-id> -SourceRevision <revision>
```

该测试必须接受未篡改副本，并拒绝 CSV／summary 损坏、summary `NaN`／布尔字符串类型混淆、summary 属性名大小写变异、config 整数字符串、identity hash 不匹配、重复或缺失 run index、环境不匹配、optional capability 状态不一致，以及普通／隐藏 extra artifact。

完整 summary 编排合同回归：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Tools\Benchmarking\Test-XUILabM0CalibrationOrchestration.ps1
```

该测试固定由 Windows PowerShell 5.1 执行，在系统临时目录中用一次性 fake Player 覆盖一个完整合法 22 字段 summary 的 10-run 正向矩阵，以及 21 个负向场景：审查指出的 8 个遗漏字段、额外字段、属性名大小写变异、非有限／错误类型统计、success 语义不一致和枚举值大小写变异。正向矩阵必须 10/10 接受且没有 sidecar；每个负向场景必须非零退出，只在 artifact root 生成一个身份匹配、reason 可定位的 sidecar，run 目录内不得出现重复 sidecar。测试结束后只清理本次创建、路径位于系统临时目录分隔符边界内且不是 reparse point 的目录。

## 4. 单轮 CLI 与故障诊断

Runner 的基础参数如下；`<case>` 为 `idle` 或 `known-load`：

```powershell
& .\Artifacts\<build-id>\build\XUILab-M0-Runner.exe `
  -screen-fullscreen 0 -screen-width 960 -screen-height 540 `
  --xuilab-run --xuilab-quit --xuilab-output-root .\Artifacts `
  --xuilab-run-id <unique-run-id> --xuilab-series-id <series-id> --xuilab-run-index 1 --xuilab-repeat-count 5 `
  --xuilab-protocol-version xuilab.benchmark.protocol/v1 --xuilab-case <case> `
  --xuilab-warmup-frames 300 --xuilab-measure-frames 1800 --xuilab-sample-capacity 1800 `
  --xuilab-target-frame-rate 60 --xuilab-vsync-count 0 --xuilab-frame-budget-ms 16.6666667 `
  --xuilab-candidate-id <candidate-id> --xuilab-build-id <build-id> --xuilab-source-revision <revision>
```

known-load 另加 `--xuilab-cpu-iterations 4000000 --xuilab-allocation-bytes 32768`；uncapped 使用 `--xuilab-target-frame-rate -1`；关闭可选 recorder 使用 `--xuilab-disable-profiler-recorders`。

故障只允许在 Development／Editor build 通过 `--xuilab-fault` 显式启用：`prepare_failure`、`ready_timeout`、`required_metric_unavailable`、`sample_shortage`、`cancel`、`case_exception`、`export_failure`、`cleanup_failure`、`focus_loss`、`pause`。需要时加 `--xuilab-fault-trigger-frame <n>`；该值是 Measure action 的零基索引，命中 action 后在下一 Unity 帧捕获同索引 sample。sample shortage 加 `--xuilab-fault-sample-count <n>`，该值是最终允许保留的样本数，不是 action 索引。Release build 必须拒绝 fault plan。

预期进程码：成功 0；failed 1；cancelled 2；已导出但 invalid／correctness fail 3。采样前 failed/cancelled 不应生成 `samples.csv`；进入 Measure 后的 invalid/fail 保留已采样行。export failure 可能只留下 partial；用校准脚本的 `-DiagnosticFault export_failure` 触发时，即使 run 目录不存在，外层编排也必须生成 failure sidecar 和 Player log，不能因目录不完整改报 success。使用唯一 stamp，预期脚本以非零退出并在第一轮停止。

## 5. 终态、恢复与归档

- 正常 run 应含 `config.json`、`environment.json`、`identity.json`、`samples.csv`、`summary.json`、`report.md`、`events.log`；CSV 为 1801 行（header + 1800 frames）。缺失 optional 值为空／null，不是 0。
- `identity.configSha256` 必须等于落盘 `config.json` 精确字节的 SHA-256；run-id 在 config／identity／summary 和目录名中一致；环境、候选、build 与协议必须匹配显式传给 verifier 的预冻结合同。
- focus loss、pause、required metric 缺失、样本不足或身份违约按预设规则整轮 invalid；保留原目录，使用新 run-id 重跑，不删除大帧。
- 结束后确认所有 Player 退出；Unity 非 Play、无测试／编译／构建，恢复原 scene、Prefab Stage、VSync/target-frame-rate 和工具导致的 ProjectSettings 重序列化，再释放 Unity 占用。
- 根 `.gitignore` 对整个 `Artifacts/` 生效；compact run evidence、Player logs、build、Profiler capture 和媒体均保持本机未跟踪。PM／实验文档只保存 run-id、集合哈希、build/hash、保留策略和恢复位置。本机归档迁移前重新核对哈希；未获授权时不 commit/push。
