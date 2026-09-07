# 跨阶段验收映射

唯一机器索引为 [acceptance-map.json](../Agents/acceptance-map.json)，覆盖路线图 21 个任务和 51 个 required 条款（21 个任务交付条款、30 个阶段出口／学习条款）。正文目标仍以[路线图](ROADMAP.md)及对应阶段为准；索引保存原文用于漂移检查，不替代阶段详细合同。

`<Task-ID>-DELIVERY` 表示路线图该任务的交付要求；`M<N>-EXIT-<NN>` 是稳定的阶段出口 ID。阶段最后一个任务负责汇总出口证据，不代表此前任务的实现都交给最后任务。ID 发布后不重排／复用；修改源条款须明确更新映射和受影响 Brief，不能事后删除 required 来掩盖失败。

每个任务声明 source、dependsOn、acceptanceIds 和 evidenceKinds。evidenceKinds 是应准备的证据种类，具体测试、环境、数量、成功判据仍由 Brief 和阶段详文确定。工具不会把“有文件”解释为“已经验收”。M0/M1 的历史任务不迁移、不重新验收；后续新建 v1 MVP Brief 必须按下文绑定。

M2-03 的列表集成通过 conditionalDependsOn 条件 `list-integration` 引用 M1-04；独立 Gradient 路径只依赖 M2-02。启用该场景时主 Agent将条件依赖落实到任务合同，不能省略实际前置条件。M3-L 从 M1-04 开始、M3-G 从 M2-04 开始，M3-05 汇合；M4-01 汇集 M1/M2/M3 的最终输入。图检查覆盖已声明依赖及条件边，不推断场景选择。

## 新任务 Brief 的绑定

在新建 v1 MVP Brief 增加如下两列表。每个该任务 acceptanceIds 必须绑定到验收矩阵中的 required ID；多个来源可共同绑定到一个具体检查，但判据必须覆盖全部语义。基础设施任务不强行套用 MVP ID。

| acceptance_id | brief_id |
| --- | --- |
| M2-01-DELIVERY | A1 |

阶段最后任务还要绑定本阶段所有 EXIT ID。必要的详细测试仍可使用本任务 A2、A3 等 ID；静态映射是覆盖下限，不允许替换或缩减阶段详文。

运行 `python -B Tools/ProjectManagement/check_acceptance.py`，或统一入口 `python -B Tools/check_offline.py`。检查范围：任务集合、唯一 ID、源引用、原文漂移、阶段出口覆盖、依赖存在性／循环、静态字段、required 约束、新 MVP Brief 的绑定、技能路径引用。不会证明依赖语义足够、作者独立、实际运行结果或授权；这些由 Reviewer核对。

验收链为：静态 ID → 本任务 Brief required ID → Task Status 对应行 → 当前候选 Verification／Review／原始证据。流程状态、candidate和结果只在 [PM 合同](../Agents/PM_CONTRACT.md)规定的位置维护；静态索引不包含第二份状态表。新 Agent按[薄技能](../../.agents/skills/xuilab-task-resume/SKILL.md)从持久游标续接。
