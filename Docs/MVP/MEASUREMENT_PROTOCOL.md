# MVP 测量与证据协议

状态：M0-04 r7 已通过冻结后独立复审，M0 阶段出口为 `pass`。r7 将单轮编排与严格 verifier 统一为 case-sensitive exact contract；协议标识仍为 `xuilab.benchmark.protocol/v1`，r5 冻结实验数据保持原身份和可信性。本文定义跨阶段的最低合同；具体 Case 在 `Docs/Experiments/` 记录协议版本和参数。M0 的校准数据与边界见 [`M0_CALIBRATION.md`](../Experiments/M0_CALIBRATION.md)。

## 1. 三层结论

每次实验按顺序给出三个独立判断：

1. **correctness**：被测行为是否符合功能合同，结果为 pass／fail／not_run。
2. **measurement validity**：身份、环境、输入、采样和必要指标是否满足协议，结果为 valid／invalid／not_assessed。
3. **performance comparison**：A/B 差异为 improved／regressed／no_clear_difference／inconclusive。

正确性失败时不发布性能改善结论。测量无效时保留数据供诊断，但不能纳入正式比较。功能正确且性能退化仍是有效实验结果。

## 2. 运行层级

| 层级 | 主要用途 | 结论边界 |
| --- | --- | --- |
| 静态审查 | 合同、算法、程序集、所有权和潜在缺陷 | 不证明实际运行 |
| EditMode | 索引、池不变量、曲线、统计和序列化纯逻辑 | 不替代生命周期和渲染 |
| PlayMode | UGUI 生命周期、Mesh、场景集成和视觉行为 | 只作开发反馈和集成证据 |
| Windows Development Player | 带必要诊断能力的正式 A/B 数据 | 与 Release 和其他平台分开 |
| Windows Release Player | 展示包的功能、视觉和实际运行验收 | 不把 Development 计数器混入同一数据集 |
| 独立诊断／媒体运行 | Profiler、Frame Debugger、内存快照、截图和视频 | 不作为正式采样窗口 |

Unity 官方说明 Editor Play Mode 会受到 Editor 进程影响，目标平台 Player 更适合正式性能判断；Deep Profiling 也会引入额外开销。[Unity 2022.3 Profiler 文档](https://docs.unity3d.com/2022.3/Documentation/Manual/profiler-profiling-applications.html)

## 3. 实验前冻结

每个可比较实验必须在运行前记录：

- 问题、假设、A/B 定义和预期观察；不预设一定改善。
- candidate-id、commit／dirty 状态、源码／依赖／配置哈希和 build-id。
- 数据、随机种子、资源、分辨率、Canvas、颜色空间、图形 API、质量、VSync／目标帧率、脚本后端和构建类型。
- 动作时间线、冷开或稳态起止点、预热、测量窗口、重复次数和 A/B 顺序。
- 指标名称、单位、采样源、required／optional 及不可用处理。
- 有效性规则、异常事件、比较统计和判断阈值的来源。

一次主要改变一个因素。普通列表基线采用合理实现；不能每帧创建销毁来夸大虚拟化收益。渐变比较保持相同颜色函数、可见内容和 Canvas 条件；段数变化不能同时改变目标画质。

## 4. 稳态协议 v1

M0-04 已实测并冻结以下起始协议：

- 预热 300 帧；
- 测量 1800 帧并覆盖完整动作，采样缓冲容量至少为 1800；
- 每个配置 5 次独立运行；
- 每轮使用新的 Player 进程，A/B 使用运行前冻结的 ABBA 交错顺序；
- 保存每轮统计和轮间波动，不挑选最好一轮。

逐帧动作与样本使用两阶段合同：在帧 `N` 的 Update 中先调度 action `i`，在下一帧 `N+1` 才捕获 sample `i`。`sample i` 的 Frame Interval 因而覆盖 action `i` 发生后的完整帧间隔；最后一个 action 只在其后继帧样本落盘后结束，不执行无样本对应的额外 action。该顺序必须由真实 PlayMode 交替轻／重动作测试验证，不能仅以 mock delta 证明。

Windows 主测 tier 为 x64 Development Player／Mono；固定窗口 960×540、VSync 0。60 FPS 体验模式使用 `Application.targetFrameRate=60`，未限帧吞吐模式使用 `-1`，两类结果分开报告。帧预算固定为 16.6666667 ms，只有严格大于预算的帧计入 over-budget。

M0 known-load 固定为每帧 4,000,000 次确定性 CPU 迭代和 32,768 bytes 分配，仅用于证明测量链能区分负载及暴露环境波动，不是 UI 实现或优化基线。短 smoke／pilot 可以帮助开发，但标记为 exploratory，不进入正式作品集数字。

后续若修改预热、窗口、重复数、聚合算法、required 指标或 invalid 规则，必须生成新的 protocol version；旧数据不与新协议合并计算改善比例。

冷开另行定义起止点，并与场景加载、进程启动、资源首次导入区分。预热后的首帧不能称作冷开。

## 5. 指标与统计

v1 的 required 指标数组必须且只能包含 `Frame Interval`，单位 ms，来源为相邻 Player 帧的实时差；null、空数组、改名或追加其他 required 指标都属于配置无效。它不是主线程 CPU 时间。当前机器上的 `Main Thread`、`GC Allocated In Frame` 和 `System Used Memory` ProfilerRecorder 没有产生可用样本，因此保持 optional，并在 environment 中写 `unavailable + reason`、CSV 留空、summary 写 null。不得用 0 或其他指标替代。

后续 Case 可增加下列指标，但必须先探测名称、单位和样本能力，再决定 required／optional：

- 帧间隔原始序列和 p50／p95／p99、最大值、超预算帧比例；
- CPU／UI 相关标记，名称和单位按当前构建实际探测；
- GC 分配字节和 GC 事件；
- 创建／销毁、Bind／Unbind、dirty／重建和唯一实例计数；
- 顶点、三角形、Draw Calls／Batches 与支持时的 GPU 数据；
- 质量误差、位置误差或场景特有功能指标。

帧间隔不能命名为主线程 CPU 时间；两个场景的 p95 相减不能直接宣称为组件独占耗时。无 GC 回收不等于零分配，内存不增长也不单独证明无泄漏。

逐轮 p50／p95／p99 使用排序后位置 `(n - 1) × p` 的线性插值。跨五轮先计算每轮统计，再报告 median、min/max、MAD 与 IQR；不得把五轮逐帧样本拼成一条序列。吞吐模式和 60 FPS 体验模式分开。相对阈值应来自基线波动和实际用途，不能先规定“必须优化 30%”。

## 6. 有效性与采样隔离

- 采样前探测计数器是否有效、单位是否符合、是否产生足够样本。required 指标缺失则判 invalid；optional 缺失标 unavailable。
- 记录失焦、暂停、超时、分辨率变化、编译、资源导入和进程异常。按预设规则整轮重跑，不在看到数据后删除大帧。
- 采样缓冲预分配；窗口内不截图、录屏、逐帧日志、逐帧 MCP 查询或文件写入，结束后统一导出。
- Deep Profiling、Frame Debugger、Memory Snapshot 和可视 Profiler 捕获另跑并标注诊断用途。
- 正式性能运行期间暂停同机其他 Unity 构建、测试和重型任务。

v1 invalid／terminal 规则为：身份不匹配、required 指标不可用、实际样本少于计划、采样期 focus loss／pause 或测量期异常使 measurement validity 为 `invalid`；进入 Measure 前失败或取消为 `not_assessed`。高波动本身不使 run invalid。单 Case 可以 terminal `completed` 但 correctness fail 或 measurement invalid；只有 `completed + correctness pass + validity valid + export/cleanup success` 才是 process success／exit 0。`failed` 为 exit 1，`cancelled` 为 exit 2，已完整导出但 invalid/correctness fail 为 exit 3。

若某轮因预先定义的外部干扰而 invalid，保留原目录并用新 run-id 重跑整轮；不删除异常帧、不覆盖目录、不在看到结果后缩短窗口。聚合只纳入相同 candidate、build、protocol、tier、配置且 valid 的预定轮次。

## 7. 运行产物

每次运行使用稳定 `run-id`，最低产物为：

```text
Artifacts/<run-id>/
├─ config.json
├─ environment.json
├─ identity.json
├─ samples.csv
├─ summary.json
├─ report.md
└─ events.log
```

`samples.csv` 只在实际进入采样后生成。失败运行仍保存可得配置、环境、失败阶段和错误，不伪造样本。`summary.json` 以 null／状态加原因表达缺失值，不用 0 代替不可用。

协议 v1 的成功／失败 summary 共用精确的 22 字段集合：8 个 string 状态／原因字段，4 个 boolean 生命周期字段，2 个 integer 退出／计数字段，5 个 nullable number 帧统计字段、1 个 nullable number 主线程字段，以及 2 个 nullable integer 内存／分配字段。字段名以 ordinal/case-sensitive 规则匹配；缺字段、额外字段和仅大小写不同的字段都属于合同失败。JSON 原始类型必须在转换前检查，所有非 null 数值必须有限。成功轮的 schema、run-id 和枚举／状态字符串也以大小写敏感规则匹配；`failureCode` 必须为 `none`、`failureReason` 必须为空、`performanceComparison` 必须为 `not_assessed`，且 p50/p95/p99/max/over-budget 必须为非 null 的有限数值。失败或无效轮允许统计为 null，但不能省略字段或用字符串占位。

`identity.configSha256` 是落盘 `config.json` 的**精确文件字节** SHA-256：Unity `JsonUtility` pretty JSON、Windows `CRLF`（由 `Environment.NewLine` 生成）、UTF-8 无 BOM。Artifact Writer 必须先生成将要写入的同一字节串，再设置 identity hash 并写入 config/identity；不能依赖 Case `Prepare` 前的可变 config 快照。验证器直接对 artifact 文件计算，不对解析对象或另一种 compact JSON 规范化。

正式矩阵验证必须使用 `-Force` 枚举并拒绝隐藏或普通额外文件／目录，按大小写敏感规则核对精确属性集、run-id/index 1..5、候选／build／source、完整配置／环境合同、CSV 行与连续索引，并从 CSV 重算 summary 的分位数、max 和 over-budget 比例。JSON 字段在转换前检查原始 string/integer/number/boolean/array/object 类型；所有数字必须有限，optional metric 的 `status/reason` 必须与 CSV 可用性一致。

Player 编排为每个新进程设置 wall-clock timeout，只能终止该次编排实际启动并记录的 PID。进程超时、启动失败、无 summary、summary 无法解析、可解析但字段缺失／类型错误，或终态合同失败时，在 run 目录外保留不可覆盖的 `*-orchestration-failure.json` 与 Player log；即使 Runner 初始 artifact writer 失败，也必须有 run-id、进程、退出码／timeout 和失败原因旁证。

正式报告可从 run-id 定位源码候选、依赖锁、构建、配置、原始数据、统计方法和硬件。探索性 dirty 运行可用于调试；M4 的公开数字来自干净、可重建的冻结候选。

根 `.gitignore` 忽略整个 `Artifacts/`：compact run evidence、Player log、构建、Profiler 捕获和视频都保持本地未跟踪或移入受控外部归档。PM／实验文档需要记录 run-id／路径、哈希、保留策略和恢复方式；不得通过例外规则提交其中的 compact 产物。

## 8. Agent 与 Runner 分工

Agent 负责配置、构建、启动、等待、有效性检查、分析、图表和报告；C# Runner 负责 Prepare → Warmup → Measure → Validate → Export → Cleanup 的确定性状态机。Agent 或 MCP 响应时间不能成为每帧动作的一部分。

详细的错误处理、角色和证据审查执行方式见 [Agent 性能证据规范](../Agents/PERFORMANCE_EVIDENCE.md)；实际命令、终态检查与恢复步骤见 [Benchmark 复跑手册](../Agents/BENCHMARK_RUN_PLAYBOOK.md)。
