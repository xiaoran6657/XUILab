# XUILab 文档库

`Docs/` 是 XUILab 的唯一项目文档库。根目录 [`README.md`](../README.md) 和 [`AGENTS.md`](../AGENTS.md) 分别作为人类入口与 Agent 启动入口；需求分析、规划、工作流、项目状态、实验结论和参考资料的正文统一放在这里。

## 从哪里开始

| 读者／目的 | 阅读顺序 |
| --- | --- |
| 查询当前进度 | [项目状态](PM/PROJECT_STATUS.md) → [待处理动作](PM/Next_Actions.md) → 所指任务状态；核对请求涉及的实际文件 |
| 第一次了解目标 | [MVP 索引](MVP/README.md) → [路线图](MVP/ROADMAP.md)；需要立项背景时再读 [历史项目分析](PROJECT_ANALYSIS.md) |
| 执行 MVP 任务 | 当前 PM/任务 Brief → [MVP 索引](MVP/README.md)与相关阶段 → [Agent 工作流](Agents/README.md) → [PM 合同](Agents/PM_CONTRACT.md) |
| 基础设施维护 | 当前 PM/INFRA 任务 Brief → [工作流](Agents/WORKFLOW.md) → [PM 合同](Agents/PM_CONTRACT.md) → 实际维护的文档或工具；涉及 MVP 边界时再查路线图 |
| 审查候选 | 任务 Brief/状态 → 候选清单与实际文件 → 对应 Review/Verification；按风险补读相关 playbook |
| 操作 Unity | 上述文档 → [Unity MCP 操作手册](Agents/UNITY_MCP_PLAYBOOK.md) |
| 设计／审查性能实验 | 路线图 → [性能证据规范](Agents/PERFORMANCE_EVIDENCE.md) |
| 搬迁证据／离线验证／出图／恢复计划 | [统一证据入口](Experiments/EVIDENCE.md) → [复现工具手册](Agents/REPRODUCIBILITY_PLAYBOOK.md) |
| M2/M3 离线计划与质量工具 | [Gradient 工具合同](Agents/GRADIENT_BENCHMARK_TOOLING.md)；实际阶段仍按PM授权启动 |
| 一次性检查／CI与源码归档 | [离线调度](Agents/OFFLINE_AUTOMATION.md) → [源码归档](Agents/SOURCE_ARCHIVE.md) |
| 续接已有任务 | `PM/PROJECT_STATUS.md` → `PM/Next_Actions.md` → 当前任务记录；文件不存在时表示尚未初始化 |
| 查历史背景或参考源码 | 先读当前需求和项目文档，再按需进入 [`References/`](References/) |

## 目录职责

### `Agents/`：项目执行工作流

存放 Agent 的执行模型、角色、模型建议、Unity MCP、安全边界、性能取证规则、启动提示词和记录模板。这里回答“如何完成并证明任务”，不重复定义版本目标，也不保存每次任务的动态状态。

入口：[Agents/README.md](Agents/README.md)。模板位于 [`Agents/templates/`](Agents/templates/)，复制到对应 PM 任务目录后才成为实际记录。空模板不构成执行证据。

### `MVP/`：版本规划与版本目标

存放版本范围、技术基线、里程碑、任务依赖、阶段细化、测量协议、验收标准和扩展启动条件。入口为 [MVP/README.md](MVP/README.md)，总览为 [MVP/ROADMAP.md](MVP/ROADMAP.md)，M0–M4 各有独立阶段文档。

路线图描述“计划交付什么”，不承担每次运行结果或当前负责人等动态状态。固定决策变更时应说明依据和影响，不把失败的验收项事后从路线图删除来制造完成状态。

### `PM/`：项目管理

存放当前项目游标、按依赖排序的下一步、Task Brief、任务状态、实现交接、审查和验证报告。规范结构为：

```text
PM/
├─ PROJECT_STATUS.md
├─ Next_Actions.md
└─ Tasks/
   └─ <Task-ID>/
      ├─ TASK_BRIEF.md
      ├─ TASK_STATUS.md
      ├─ HANDOFF-r<N>.md
      ├─ REVIEW-r<N>.md
      └─ VERIFICATION-r<N>.md
```

`PROJECT_STATUS.md` 保存唯一全局游标和 Unity 占用记录；每个 `TASK_STATUS.md` 是该任务流程状态的唯一来源；`Next_Actions.md` 只保存尚待处理的动作与链接，不复制状态或已完成列表。MVP 任务沿用路线图 ID；基础设施采用 `INFRA-NNN`，共用上述目录与状态机。新记录使用 [PM 合同](Agents/PM_CONTRACT.md)的固定字段；历史记录的兼容范围与 [离线检查](Agents/PM_CHECK_PLAYBOOK.md)明确列出。

### `References/`：参考文件

存放简历与准备回答、实习任务记录、LUI 分析、参考源码、外部资料以及另一项目的 Agent 工作流。这些文件用于了解历史、来源、API 和风险，具有以下边界：

入口说明见 [`References/README.md`](References/README.md)。参考材料内部无法在本仓库解析的相对链接均标记为原项目路径或未随摘录分发的来源上下文，不属于 XUILab 当前文档导航。

- 不是 XUILab 的运行时代码，不应直接进入 Unity 编译。
- 不是 Agent 自动执行指令；其中的路径、模型、审批、渲染管线和命令必须按当前项目重新判断。
- 历史表述和数字不是新项目已验证结果。引用时区分实习记录、个人复现和后续改进。
- 对外公开前检查公司信息、个人隐私、第三方许可及可再分发性。

### 根级文档

- [PROJECT_ANALYSIS.md](PROJECT_ANALYSIS.md)：立项时的需求分析、可展示主题、风险和总体方案；其中工程/Git/工具状态属于当时观测，不作为续接起点。
- 本文件：文档导航和归档规则。

### `Experiments/`：已产生的实验与案例

- [List合同](Experiments/LIST_CONTRACT.md)与[Player A/B协议](Experiments/LIST_BENCHMARK_PROTOCOL.md)。
- [ListLab Player结果](Experiments/LIST_BENCHMARK_RESULTS.md)、[实现与学习案例](Experiments/LIST_LAB_CASE_STUDY.md)、[M1阶段出口](PM/M1_STAGE_EXIT.md)。

实验协议／报告与展示文案在首次产生时分别建立 `Experiments/`、`Showcase/`。不要预建空目录或空报告。大体积运行数据、构建和视频使用仓库根 `Artifacts/` 等产物目录，并由 PM／实验文档以 run-id 和哈希引用；它们不是另一套文档库。

## 文档放置规则

1. 先判断信息的唯一职责：目标进 MVP，动态状态进 PM，执行规范进 Agents，输入材料进 References。
2. 同一事实只维护一个权威位置，其他页面使用相对链接并写简短摘要。不要复制进度表、测试结果或性能数字。
3. 文件名优先使用稳定、可检索的英文大写入口和任务 ID；正文以中文为主，代码/API 名称保留原文。PM 机器字段使用合同规定的英文键，解释另写正文。
4. 路径使用仓库相对链接。移动文档后检查所有入站链接；引用本机或外部产物时同时记录可恢复位置和身份。
5. 文档声明结果时链接实际证据，明确 pass、fail、not_run、invalid、inconclusive 等边界。未来计划使用“待创建／计划”，不能写成当前事实。
6. 参考文件尽量保留来源语义。需要注释或整理时另写分析，不悄悄改写原始记录；必须脱敏时记录处理原因。

## 生命周期

- **规划**：项目分析和路线图确定问题、范围、依赖与验收。
- **执行**：PM 创建 Task Brief 和状态，Agent 按工作流实施与验证。
- **实验**：保存协议、原始数据索引、统计解释和无效／失败运行。
- **展示**：从已冻结证据提炼文案、图片和视频，不反向篡改技术记录。
- **归档**：保留决策、候选身份和限制；废弃文档标明替代入口，不让两个文件同时声称权威。
