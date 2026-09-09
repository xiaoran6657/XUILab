# Profiler 与实际 trace 解读

[学习入口](README.md) · [基础](FOUNDATIONS.md) · [列表刷新](LIST_REFRESH.md) · [渐变与自适应细分](GRADIENT_SUBDIVISION.md) · [证据导航](EVIDENCE_NAVIGATION.md)

这篇文章回答一个很具体的问题：已经有列表刷新诊断数据时，怎样继续走到 CPU/GPU 耗时诊断。先记住边界：仓库里的 `list-refresh-trace-r1` 是 **Unity Editor 中的计数和事件诊断**，不是 CPU Usage Profiler 的 Timeline 捕获。它能说明一次刷新扫描了多少 Cell、绑定发生了几次、哪些 UI 失效事件被观察到；它不能说明某个 C# 方法花了多少毫秒，也不能替代 Player 上的 CPU/GPU capture。

## 1. 先读证据身份

打开 [原始 trace](../../Artifacts/list-refresh-trace-r1/trace.json)，先看顶层字段，而不是先看某个好看的数字：

```json
{
  "schema": "xuilab.list.refresh-trace/v1",
  "candidate": "list-refresh-trace-r1",
  "unity": "2022.3.45f1c1",
  "measurement": "Editor diagnostic only; probes and snapshots are not performance-neutral",
  "boundaries": "Immediate pool deltas isolate dispatch; following frame includes natural scroll/render. Canvas event is not a rebuild count. Mesh calls are no-op observer invocations."
}
```

`measurement` 已经明确写出这是 Editor 诊断；`boundaries` 又说明了阶段和探针边界。对应的[离线复算](../../Artifacts/list-refresh-validation/trace-r1-verification.json)给出 `correctness: pass_for_diagnostic_contract`、`performance: not_assessed`，并核对了 trace 的 SHA-256。这里的 pass 只表示诊断合同和字段映射能复算，不能改写成“性能通过”。[M3-L1 验证记录](../PM/Tasks/M3-L1/VERIFICATION-r1.md)也明确记录没有执行 Player 性能测量。

本次 trace 没有可用的 MainThread CPU 时间、GC Alloc、UGUI 实际重建耗时或 GPU 时间。各 case 的 `cpu`、`layoutRebuild`、`canvasRebuild` 都是 `"unavailable"`；这和测到 0 不一样。不要用 `totalBinds`、`vertexDirty` 或一次 `Canvas` 事件去填这些空白，也不要把 Editor 诊断数字写成 Player 帧时。

## 2. Timeline 和 Hierarchy 是两种不同的提问方式

Unity 2022.3 的 CPU Usage Profiler 详情窗有 Timeline、Hierarchy 和 Raw Hierarchy 三种视图，见 [Unity 2022.3 CPU Usage Profiler](https://docs.unity3d.com/2022.3/Documentation/Manual/ProfilerCPU.html)。

Timeline 把不同线程放在同一条时间轴上。它回答“这一帧的工作在什么时候发生、哪些线程同时工作、哪里在等待”。因此可以把主线程安排工作、Render Thread 处理命令、Job Worker 执行任务和它们之间的等待对齐起来。Hierarchy 按调用层级聚合样本，通常一次看一个线程；Raw Hierarchy 逐次展示样本调用，不把同一路径的多次调用聚合成一行。Timeline 才适合观察并行关系，Hierarchy 才适合先按累计成本排序一个线程上的样本。

```mermaid
flowchart LR
  CPU[Main Thread: 脚本/布局/提交] --> R[Render Thread: 处理命令]
  R --> G[GPU: 绘制与着色]
  CPU -. 等待依赖 .-> R
  R -. 等待 Present/VSync .-> G
```

这张图表示可能的重叠和依赖，不表示三个时间段可以相加。CPU 与 GPU 可以并行；主线程还可能等待 Render Thread，Render Thread 也可能等待 GPU 或 VSync。CPU Timeline 和 GPU Usage 需要在同一帧、同一构建上下文中分别查看。[GPU Usage Profiler](https://docs.unity3d.com/2022.3/Documentation/Manual/ProfilerGPU.html)只能用于 Play Mode 或 Player，不能用来分析 Unity Editor 本身。

### Hierarchy 中几列到底是什么

在 CPU Hierarchy 中，Unity 2022.3 的列含义如下：

| 列 | 初学者读法 | 需要避免的误读 |
| --- | --- | --- |
| `Time ms` | 该样本在当前选中线程上的总耗时，包含它调用的子样本 | 不是整帧 CPU 时间；换线程后数值含义也变 |
| `Self ms` | 该样本自己消耗的时间，不含子样本 | 不是“另一个独立总耗时” |
| `Calls` | 这一帧该聚合样本出现的调用次数 | Raw Hierarchy 不合并调用时通常显示 1 |
| `GC Alloc` | 当前帧脚本托管堆分配的字节数 | 不是 GC 回收次数、存活内存或 GPU 内存 |
| `Total` / `Self` | 相应的总时间/自身时间百分比 | 百分比也受当前选中线程和视图影响 |

例如父样本 `A` 的 `Time ms` 是 5 ms，其中子样本 `B` 是 3 ms，那么 3 ms 已经包含在 A 的 5 ms 里；在 B 是唯一子样本且没有其他嵌套成本的这个简化例子里，`A Self ms` 约为 2 ms，不能把 A 和 B 加成 8 ms。跨线程的样本更不能用这种方式相加。官方对列的定义见 [CPU Profiler 的 Hierarchy 字段](https://docs.unity3d.com/2022.3/Documentation/Manual/ProfilerCPU.html#hierarchy)。

`GC Alloc=0` 只表示该帧报告的脚本堆分配为零；本次数据是 `unavailable` 时，正确的写法是“没有可用 GC 数据”。[GC Alloc 与调用栈说明](https://docs.unity3d.com/2022.3/Documentation/Manual/ProfilerCPU.html#call-stacks)还说明，打开 Call Stacks 可以帮助定位 `GC.Alloc`，不需要为了看一次分配就打开 Deep Profile。

### Wait marker 不是瓶颈结论

`WaitForTargetFPS` 可能只是等待目标帧率；它出现在 `Gfx.WaitForPresentOnGfxThread` 下时，还需要区分 GPU 完成与显示同步造成的等待，不能仅凭该结构认定 GPU 计算过慢。`Gfx.WaitForCommands` 可能提示 Render Thread 在等主线程命令。要判断 GPU-bound，必须看父子关系、线程、Render Thread 的同时段和 GPU Usage；看到一个名字里有 `Wait` 的 marker 就断言“GPU 慢”是不成立的。参见 [Unity 2022.3 Common Profiler Markers](https://docs.unity3d.com/2022.3/Documentation/Manual/profiler-markers.html)。

## 3. 本项目 Runner 怎样记录帧，以及它没有记录什么

下面这些源码链接是当前工程的实际符号位置。行号帮助第一次定位；源码演进后仍应先确认 symbol 名称。

| 代码入口 | 做的事 | 与 Profiler capture 的关系 |
| --- | --- | --- |
| [`BenchmarkRunnerHost.Update`](../../XUILab/Assets/XUILab/Benchmarking/Runtime/BenchmarkRunnerHost.cs#L51) | 每帧读取 `Time.unscaledDeltaTime`，乘 1000 后传给 `runner.Tick`，并传入 `Time.frameCount` | 得到帧间隔和帧号，不会自动生成 CPU Timeline |
| [`BenchmarkRunner.TickMeasure`](../../XUILab/Assets/XUILab/Benchmarking/Runtime/BenchmarkRunner.cs#L245) | 创建 `BenchmarkFrameSample`，填 `SampleIndex`、`UnityFrame`、`ElapsedMs`、`FrameIntervalMs`，再调用指标探针 | 是确定性样本序列，不是 Profiler Window 的线程时间轴 |
| [`UnityProfilerMetricProbeSet.Prepare`](../../XUILab/Assets/XUILab/Benchmarking/Runtime/BenchmarkMeasurement.cs#L83) | 尝试启动 `Main Thread`、`GC Allocated In Frame`、`System Used Memory` 三个 `ProfilerRecorder` | 仅当目标构建/平台实际提供 recorder 且配置要求时才有这些指标 |
| [`UnityProfilerMetricProbeSet.Capture`](../../XUILab/Assets/XUILab/Benchmarking/Runtime/BenchmarkMeasurement.cs#L139) | 把 recorder 的 `LastValue` 写入当前 `BenchmarkFrameSample`，并设置 `*Available` | `Available=false` 是缺数据标记，不应替换成 0 |
| [`UpdateObservedCapability`](../../XUILab/Assets/XUILab/Benchmarking/Runtime/BenchmarkMeasurement.cs#L235) | 如果整个测量窗口没有可用样本，把能力改成 `unavailable` | “recorder 可启动”不等于“窗口内观察到有效样本” |
| [`BenchmarkStatistics.Calculate`](../../XUILab/Assets/XUILab/Benchmarking/Runtime/BenchmarkMeasurement.cs#L327) | 根据帧间隔算 p50/p95/p99、最大值、超预算比例；有数据时才汇总 Main Thread/GC/内存 | 统计样本，不提供父子调用耗时或 GPU 时间 |
| [`BenchmarkRunner.Validate`](../../XUILab/Assets/XUILab/Benchmarking/Runtime/BenchmarkRunner.cs#L320) | 依次判断 case correctness、样本数量、required metrics、失焦/暂停，生成 validity | `valid` 不是“更快”；正确性、测量有效性、性能比较分开 |
| [`BenchmarkRunnerHost.OnApplicationFocus`](../../XUILab/Assets/XUILab/Benchmarking/Runtime/BenchmarkRunnerHost.cs#L73) | 运行期间失焦或暂停时标记外部无效 | 记录失效原因，不替换原始帧数据 |

因此，当前 `list-refresh-trace-r1` 的 `traces[]` 字段（如 `targetBinds`、`scannedCells`）属于列表诊断 schema；它们不等于 `BenchmarkFrameSample.FrameIntervalMs`，也没有 `Time ms`/`Self ms`/`Calls` 列。未来即使 Runner 的 `ProfilerRecorder` 可用，也要把它和独立 Profiler capture 的身份、动作和帧范围分开保存。

## 4. 用一个真实 trace 逐字段走一遍

选择 `traces[]` 中 `name="middle"`、`backend="normal"` 的记录。原始字段如下：

```json
{
  "name": "middle",
  "backend": "normal",
  "target": 14,
  "targetBinds": 1,
  "totalBinds": 9,
  "scannedCells": 1000,
  "dataMutationOperations": 1,
  "targetVisible": true,
  "targetRetained": true,
  "reentryStale": false,
  "layoutRebuild": "unavailable",
  "canvasRebuild": "unavailable",
  "cpu": "unavailable"
}
```

这组数据应这样读：目标数据索引是 14；诊断观察到目标只产生 1 次 Bind，但原 `RefreshItem` 的总 Bind 是 9 次；普通后端仍扫描 1000 个 Cell。它说明“目标更新”和“实际重绑窗口”不是同一个量，不能从 `1/9` 推出 9 倍 CPU 或帧率改善。

再看同一条记录的 `snapshots[]`。`before` 的累计 `binds=1000`；`immediate_after_dispatch` 变为 `binds=1009`、`unbinds=9`，所以本次派发增量是 9。该阶段 `graphics` 子项聚合为 `vertexDirty=18`、`layoutDirty=9`、`meshCalls=0`。`after_natural_frame` 到 frame 14 时 `canvasEvents=1`、`meshCalls=9`；显式 flush 后 `canvasEvents=2`，Mesh 调用仍为 9。

这里的 `canvasEvents=2` 是 `willRenderCanvases` 类事件观察次数，不是两次 Canvas 重建；`meshCalls=9` 是无副作用探针调用，不包含每次调用的 CPU 时间。原始顶层 `boundaries` 已经写明这两个限制。

为了感受 `scannedCells` 与窗口大小的区别，可对照复算文件中的几行：

| case | backend | target | targetBinds | totalBinds | scannedCells | 该行能支持的结论 |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `middle` | `normal` | 14 | 1 | 9 | 1000 | 普通后端扫描全表，仍重绑 9 个可见 Cell |
| `middle` | `virtual` | 14 | 1 | 9 | 13 | 虚拟后端扫描窗口，刷新计数仍是 9 |
| `off_far` | `normal` | 700 | 0 | 9 | 1000 | 离屏目标没有目标 Bind，但原刷新仍重绑窗口 |
| `off_far` | `virtual` | 700 | 0 | 9 | 13 | 虚拟后端扫描更小窗口；仍不能由计数推出毫秒收益 |

复算文件还保留了 `vertexDirty`、`layoutDirty`、`meshProbeCalls` 和 `reentryStale` 等聚合结果。它们用于检查诊断合同和失效行为；`performance` 仍是 `not_assessed`。该诊断使用 `reflection-only internal data replacement, then original RefreshItem`，因此不能把它描述成当前公开 `UpdateItem` API 的正式性能运行。

## 5. marker、C# 方法和 Deep Profile

Profiler 中看到的样本首先是 ProfilerMarker 产生的 sample stack。Unity 文档明确说明：sample stack 不等于方法调用栈，Profiler 不会把每个 sample 绑定到一个方法，也不会记录每一次调用。默认 marker 能告诉你 Unity 在哪些生命周期或系统区域花时间；它不保证每个自定义 C# 方法都单独出现。

要增加可读性，可以在 Profiler Window 中开启完整脚本方法名和适用的 Call Stacks，先定位 `GC.Alloc`、Job 完成或已有 marker 的调用来源。只有需要把每个 C# 方法都插入采样时才考虑 Deep Profiling。Deep Profile 会给 C# 方法调用增加插桩与额外检查，可能显著改变执行成本；它适合一次性的定位，不适合作为和普通运行同口径的性能数字。[Profiling applications](https://docs.unity3d.com/2022.3/Documentation/Manual/profiler-profiling-applications.html)说明了 Development Build、Call Stacks 和 Deep Profiling 的取舍；[EnableDeepProfilingSupport](https://docs.unity3d.com/2022.3/Documentation/ScriptReference/BuildOptions.EnableDeepProfilingSupport.html)说明了插桩开销。

## 6. 未来怎样采集独立的 Development Player 诊断

下面是后续工作方法，**当前未执行（`not_run`）**。本篇没有打开 Unity、构建 Player、连接 Profiler 或生成新的 capture。

1. 先冻结身份：记录 candidate、commit/dirty、受影响源码与配置哈希、Unity `2022.3.45f1c1`、Packages lock、Windows x64 构建设置、build-id、run-id、场景、分辨率、质量、VSync/targetFrameRate、图形 API、CPU/GPU/驱动。诊断 capture 必须能回指这组身份。
2. 用同一候选构建 **Development Player**，单独放在该 run 的输出目录。Profiler 连接 Player，而不是把 Editor Play Mode 的数据冒充目标 Player。Unity 官方也建议在目标平台上取得准确时序；Editor Play Mode 只适合快速定位。[Profile your application](https://docs.unity3d.com/2022.3/Documentation/Manual/profiler-profiling-applications.html#profiling-target-platform)
3. 先用普通 Profiling（不打开 Deep Profile）跑一次与列表动作合同一致的独立诊断。记录 `actionId`、动作开始/结束 frame、选中的 `selectedFrame`、warmup/steady 状态、Player 是否失焦/暂停；动作由现有确定性 Runner 驱动，不用手工点击节奏代替。
4. 在目标帧保存 CPU Timeline/Hierarchy 所需的原始 Profiler capture；若图形 API 和平台支持，再保存 GPU Usage capture。只启用此次问题需要的模块，避免 Live repaint、截图、逐帧 MCP 查询或窗口写盘污染采样窗口。capture 文件格式和导出位置以 Unity 2022.3 实际 UI 为准，不能凭空给一个不存在的扩展名。
5. 运行结束后另存机器可读的 `identity.json`、`config.json`、`environment.json`、`events.log`、`summary.json` 和原始 capture，并在 `report.md` 写清 `actionId → frame range → capture` 的映射。把 CPU、GPU、GC、UI 重建逐项写成 `available` 或 `unavailable` 及原因；缺失值不能填 0。
6. 分析时先确认 capture 的 Player、候选、构建和动作身份完全匹配，再在 Timeline 对齐 Main Thread、Render Thread、Worker 和等待，最后用 Hierarchy 排序 `Time ms`/`Self ms`/`Calls`/`GC Alloc`。GPU 结论必须来自 GPU 数据和对应的 CPU/Render Thread 上下文；只有 wait marker 时写 `inconclusive` 或 `not_assessed`。

这次计划的最低产物可沿用[性能证据规范](../Agents/PERFORMANCE_EVIDENCE.md)的 `config.json`、`environment.json`、`identity.json`、`samples.csv`、`summary.json`、`report.md`、`events.log`，再加上未修改的 Profiler 原始 capture。Development 诊断和正式帧时基准要有不同 run-id；不要把 Development 的 capture、Release 的帧时和 Editor 的计数拼成一条结果。

### 窗口入口与阅读动作（教程，未实际操作）

Unity 2022.3中使用 `Window > Analysis > Profiler`（Windows快捷键Ctrl+7）打开窗口。先看顶部目标连接选项，确认连接的是预期Player；选择CPU Usage模块，停止录制后选中一个目标帧，在详情区切换Timeline或Hierarchy。先读同一线程上的父子关系，再检查相邻正常帧，而不是只看最高尖峰。保存和加载入口位于Profiler工具栏；保存原始捕获后再截图做讲解，截图本身不能恢复完整调用数据。窗口按钮和目标列表以实际版本与连接状态为准，见[Unity 2022.3 Profiler窗口手册](https://docs.unity3d.com/2022.3/Documentation/Manual/ProfilerWindow.html)。

若准备让Agent实际执行，先读[Unity操作手册](../Agents/UNITY_MCP_PLAYBOOK.md)，检查唯一工程、未保存场景、测试/编译状态与占用；本教程没有完成这些实时检查。

## 7. 一张检查清单

- 当前文件说的是哪个身份：Editor 诊断、Development Player 诊断，还是正式性能运行？
- 这个数字是次数、字节、毫秒、百分比、线程时间，还是 GPU 时间？单位是否来自原始字段？
- 父样本的 `Time ms` 是否已经包含子样本？有没有把父子或 CPU/GPU 相加？
- `GC Alloc` 是否真的 available？没有数据时是否保留 `unavailable`？
- wait marker 是否检查了父样本、线程、Render Thread 和 GPU capture？
- 自定义 C# 方法是否有 marker/Call Stack？没有就不要声称“这个方法就是瓶颈”；Deep Profile 的开销是否单独注明？
- 每个结论能否从 `actionId`、frame、candidate、build-id、run-id 回到原始 JSON/capture？

读完本篇后，下一步应回到[列表刷新](LIST_REFRESH.md)或[渐变与自适应细分](GRADIENT_SUBDIVISION.md)理解业务工作量，再用[证据导航](EVIDENCE_NAVIGATION.md)追到真实文件。当前 trace 能教你如何建立字段和边界；它尚不能给出某次刷新在 Player 上花了多少 CPU 或 GPU 毫秒。
