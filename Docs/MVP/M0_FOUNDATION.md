# M0：工程基线与最小测量闭环

阶段出口与实际证据见 [M0_STAGE_EXIT](../PM/M0_STAGE_EXIT.md)；当前执行位置见 [项目状态](../PM/PROJECT_STATUS.md)。本页定义稳定目标，不维护动态验收状态。

前置：[MVP 固定决策](ROADMAP.md)已确定；Unity 模板工程和初始提交已存在。

后继：[M1 List Lab](M1_LIST_LAB.md)与 [M2 独立 Gradient Lab](M2_GRADIENT_LAB.md)依赖 M0 出口；授权与实际启动状态见 [项目状态](../PM/PROJECT_STATUS.md)，依赖满足不代表获得执行授权。

## 1. 主题与目标

M0 先证明工程可重建、仪器能读到定义明确的数据、正常和失败运行都能留下可信结果。只使用简单 Image／空载 Case，不提前实现列表或复杂渐变。

现有工程是输入而不是待创建产物。M0-01 从当前 `XUILab/`、URP 模板 `SampleScene`、manifest／lock 和初始提交开始验收，不重新生成项目。

## 2. 阶段成果

- 经过核对的 Unity／包／Git／Windows 构建基线和可复建步骤。
- 与模板场景分离的最小 Benchmark Smoke 场景及清晰的 Runtime、Editor、Tests 边界。
- 配置驱动的 Case／Runner／Report 最小纵向切片。
- Editor 与 Windows Development Player 的一次正常运行和代表性失败／无效运行。
- 经实测校准的测量协议 v1、run-id 目录和复跑 playbook。
- 对采样开销、计数器能力和环境噪声的学习记录。

## 3. 任务拆分

| ID | 主题 | 前置 | 主要工作 | 阶段内输出 |
| --- | --- | --- | --- | --- |
| M0-01 | 验收现有工程与工具链 | 无 | 核对版本、依赖、Git 跟踪、工程真源和 Windows 构建模块；完成最小构建／启动检查 | 基线清单、构建日志、风险与剩余项 |
| M0-02 | 最小场景与程序集 | M0-01 | 建立 Smoke 场景、运行时／Editor／测试程序集和构建入口；验证 MCP 路由、编译、Play、测试、截图能力 | 场景、asmdef、能力矩阵、功能证据 |
| M0-03 | Runner 与数据合同 | M0-02 | 实现状态机、Case 接口、配置、计数器探测、内存采样缓冲、导出与报告 | 正常 run、原始序列、摘要和报告 |
| M0-04 | 失败路径与协议校准 | M0-03 | 超时／取消／异常收尾、缺失指标和已知负载故障注入；重复运行并评估波动 | 失败／invalid 样例、协议 v1、playbook |

## 4. M0-01：验收现有工程

### 输入事实

- 工程根：`XUILab/`；Editor：`2022.3.45f1c1`。
- 直接依赖包括 URP `14.0.11`、UGUI `1.0.0`、TMP `3.0.9`、Test Framework `1.1.33` 和 Git 引用的 MCP 包。
- 当前构建列表只有 `Assets/Scenes/SampleScene.unity`；Assets 仍主要是 URP 模板内容。
- 根 `.gitignore`／`.gitattributes` 和初始提交已存在；是否覆盖所需范围仍需通过实际清单验证。

### 必须完成

1. 从 `ProjectVersion.txt`、manifest 和 lock 生成实际依赖清单；记录 MCP Unity 包的解析 commit／hash 和本地 server 可观察版本，不能从 `#beta` 或 `>=` 推断精确版本。
2. 检查版本控制是否包含 `Assets/`、`Packages/`、`ProjectSettings/`、Docs 和必要 `.meta`，并排除 `Library/`、`Temp/`、`Obj/`、Logs、生成 solution 和本机设置。
3. 记录现有模板包，区分 MVP required、暂时保留和未来可清理；本任务不以“精简”为由批量卸载。
4. 在固定 Editor 中等待导入／编译终态，检查新增和既有 Console 问题。
5. 核实 Windows x64 Build Support，构建当前最小场景到专属输出目录并启动一次；记录 Development／Release、后端、场景和日志。
6. 写明从新检出到可打开工程的步骤和仍依赖本机的部分。

### 验收

- 工程可由固定 Editor 打开并完成编译，任何警告／错误都有分类和处理决定。
- Windows Player 构建及进程启动得到终态证据；缺少模块时明确 blocked 和安装项，不能只依据 Build Target 下拉框推断可构建。
- Git 清单不存在已跟踪 Unity 缓存或本机秘密；参考资料公开风险单独记录。
- 依赖信息来自实际文件，候选身份和工作区状态可复查。

## 5. M0-02：场景与程序集边界

### 建议结构

```text
Assets/XUILab/
├─ Benchmarking/Runtime/
├─ Benchmarking/Editor/
├─ ListLab/                 # M1 创建
├─ GradientLab/             # M2 创建
├─ Tests/EditMode/
├─ Tests/PlayMode/
└─ Scenes/
```

目录以领域命名，阶段号不进入 Runtime 类型或 asmdef。M0 可只创建实际需要的目录，避免空结构。运行时代码不引用 `UnityEditor`；测试 asmdef 直接引用被测 Runtime asmdef。

Smoke 场景包含 Camera、Canvas、CanvasScaler、GraphicRaycaster、唯一 EventSystem、简单 Image 和 Runner 宿主。是否需要 EventSystem 由场景实际交互决定；不能照搬另一个项目“禁止创建 EventSystem”的规则。场景应可独立运行，不依赖模板 Readme 或外部业务 bootstrap。

MCP 能力矩阵至少记录：选择正确实例、project/editor state、资源刷新与编译、Console、场景打开／保存、Play、EditMode／PlayMode 测试、Game／Scene 截图和 Windows 构建。只记录实际验证的能力；结构化调用成功不自动代表异步任务终态。

## 6. M0-03：最小 Runner

Runner 状态固定为：

`Idle → Prepare → Warmup → Measure → Validate → Export → Cleanup → Completed/Failed/Cancelled`

最低合同：

- Case 只负责建立负载、按确定性时间线执行和提供功能断言；不直接决定报告通过。
- Runner 检查配置、构建环境和指标能力，使用预分配缓冲收集原始样本。
- Measure 窗口不打印逐帧日志或写文件；Validate 后统一导出。
- Cleanup 必须幂等，正常、超时、取消和异常都关闭 Recorder、事件和运行对象。
- 报告区分 correctness、measurement validity、performance comparison；M0 单 Case 不强行生成 A/B 收益。

最小 Case 包含空载状态和可控分配／CPU 负载。已知负载用于证明 Recorder 和统计能发现变化，不作为 UI 优化结论。

## 7. M0-04：失败路径与校准

至少覆盖：Prepare 失败、就绪超时、required 指标不可用、样本不足、主动取消、Case 异常、导出失败和重复 Cleanup。故障注入必须是配置化测试路径，不靠临时破坏生产代码。

按[测量协议](MEASUREMENT_PROTOCOL.md)的起始参数运行空载和已知负载，检查采样自身开销、运行间波动、失焦／暂停和目标帧率影响。校准决定 required 指标、预热、窗口、重复数、A/B 顺序和 invalid 规则，并写入协议 v1；不得仅因耗时长而降低到不能回答问题。

## 8. 验证矩阵

| 层级 | M0 required 检查 |
| --- | --- |
| 静态 | asmdef 引用、Editor API 隔离、配置 schema、导出路径、依赖身份 |
| EditMode | 状态迁移、取消／异常、分位数、缺失值、文件 schema、幂等 Cleanup |
| PlayMode | 场景生命周期、Case 准备／清理、采样起止、截图功能 |
| Development Player | 正常运行、已知负载、失败或 invalid 样例、产物完整性、重复运行 |
| 诊断 | 证明可关联 Profiler／截图，不混入正式采样 |

## 9. 出口门槛

- M0-01 至 M0-04 的 required 项均有实际证据；未运行项目没有被标记通过。
- 同一配置可复跑并产生结构一致的 run 目录，报告能反向定位环境、候选和原始数据。
- 正常、fail、invalid 三类路径至少各有一个可解释样例，失败不会变成 success。
- Editor 和 Development Player 数据明确分开；此阶段不发布优化收益。
- 协议 v1 和复跑步骤足够让下一 Agent 无需重写 Runner 即可增加 List Case。

学习检查：能够解释帧间隔、CPU 工作时间、UI marker、分配字节、GC 回收和存活内存的区别，并指出采样代码如何干扰被测对象。

## 10. 风险与停止条件

- Windows Build Support 不可用：完成其余静态／Editor 基线，记录精确模块和恢复步骤；M0 不能完成。
- MCP 不稳定：Runner 和 CLI 复跑入口仍应推进，MCP 能力标 blocked；不要启动第二个未知服务或误选其他工程。
- Performance Testing 包兼容性不明：先用现有 Test Framework 与自有 Runner 完成最小闭环，评估包后再锁定；不让可选包阻塞核心。
- 模板包较多：记录而非顺手删除；只有能证明无用并有相应任务授权时再清理。
