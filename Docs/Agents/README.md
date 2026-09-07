# XUILab Agent 工作流

适用范围：XUILab 的 MVP 实现、验证、性能实验，以及 `INFRA-NNN` 基础设施任务。当前执行游标见 [项目状态](../PM/PROJECT_STATUS.md)。

项目目标是把 ListView、程序化渐变与过渡、自动性能测试转化为可解释、可复现的展示材料，同时训练性能分析能力。Agent 负责工程推进；用户在目标决策、必要的编辑器操作和成果确认时参与。

## 已确定的边界

- 需求依据：[项目分析](../PROJECT_ANALYSIS.md)与[路线图](../MVP/ROADMAP.md)。路线图负责“做什么”，本目录负责“如何协作和证明完成”。
- 仓库根为 `<repo>`；唯一 Unity 工程根为 `<repo>/XUILab`，执行路线图时不再创建第二个工程目录。
- Unity 固定为 `2022.3.45f1c1`；依赖以工程 manifest/lock 为准。[环境快照](ENVIRONMENT_BASELINE.md)是带日期的历史观测，实际操作前重新核对相关状态。
- 当前 MCP 使用用户提供的 stdio 连接；一次只由一位明确的 Unity 操作者使用。需要多 Agent 时优先拆分源码审查、实验设计、离线数据分析。
- 工作流文档、模板和待办建议不授予执行权限，也不是运行或性能证据。

## 最小执行方式

默认一个主 Agent 兼任协调和实现角色，持续完成用户已授权的任务或阶段。小型文档工作可以自行检查；涉及组件生命周期、程序集、场景集成或正式性能结论时，安排独立复核。角色并不等于必须新建一个用户可见任务。

只有用户或适用的 `AGENTS.md`／技能明确要求子 Agent 时才委派。未获委派授权时，主 Agent 可以完成实现和自检，但不能把自检写成独立审查；需要的独立验收保留为待完成项。用户可以直接使用[启动提示词](START_PROMPTS.md)授权一次完整的任务闭环。

根目录已有 [AGENTS.md](../../AGENTS.md)，负责启动边界与阅读路由；本目录承载按需读取的工作流正文，不复制成另一份启动指令。[官方说明](https://learn.chatgpt.com/docs/agent-configuration/agents-md)

## 阅读入口

| 要做的事 | 必读文档 |
| --- | --- |
| 仅查询状态 | [项目状态](../PM/PROJECT_STATUS.md) → [下一步](../PM/Next_Actions.md) → 相关任务记录 |
| 开始／续接执行 | 上述状态与任务 Brief → [执行流程](WORKFLOW.md) → [PM 合同](PM_CONTRACT.md)；按 [文档路由](../README.md)补读相关范围 |
| 维护 PM／检查入口 | [PM 合同](PM_CONTRACT.md) → [离线结构检查](PM_CHECK_PLAYBOOK.md) |
| 离线验证／证据包／出图／恢复 | [统一证据入口](../Experiments/EVIDENCE.md) → [复现工具手册](REPRODUCIBILITY_PLAYBOOK.md) |
| 离线自动检查与 CI | [显式离线调度](OFFLINE_AUTOMATION.md) |
| M2/M3 离线工具准备 | [Gradient 工具合同](GRADIENT_BENCHMARK_TOOLING.md) |
| 源码与完整本地归档 | [归档手册](SOURCE_ARCHIVE.md) |
| 分配角色或选择模型 | [角色与模型](ROLES_AND_MODELS.md) |
| 操作编辑器、运行测试 | [Unity MCP 操作手册](UNITY_MCP_PLAYBOOK.md) → [操作追踪与恢复](UNITY_OPERATION_JOURNAL.md) |
| 跨阶段验收／任务续接 | [验收映射](../MVP/ACCEPTANCE_MAP.md)；[薄技能入口](../../.agents/skills/xuilab-task-resume/SKILL.md) |
| 建立或审查性能结论 | [性能证据规范](PERFORMANCE_EVIDENCE.md) |
| 复跑 Windows Benchmark | [Benchmark 复跑手册](BENCHMARK_RUN_PLAYBOOK.md) |
| 直接发起工作 | [启动提示词](START_PROMPTS.md) |
| 理解参考流程的取舍 | [设计依据](DESIGN_RATIONALE.md) |

## 如何确定本次起点

从用户授权与 PM 当前任务定位实际剩余工作，不从历史设计日期或最早阶段重新开始。基础设施任务只维护其 Brief 约定的规范与工具；MVP 前置条件已满足也不自动启动下一阶段。

当前仓库已存在初始提交；根目录已建立 Unity／IDE 生成内容的忽略规则和文本／二进制属性。实施 Agent 仍应在后续提交前核对实际跟踪范围，避免把生成文件或未经处理的实习参考材料纳入提交／公开成果。不要未经检查直接执行 `git add .`。

本目录提供规则和模板；实际任务记录在获得执行授权后按 [PM 合同](PM_CONTRACT.md)创建。不要把空模板当作已执行记录。
