# Task Status — <Task-ID>

> 模板；此文件为单个任务流程状态的唯一来源，由主 Agent 更新。

- pm_schema: xuilab.pm/v1
- task_id: <目录 Task-ID>
- task_type: <mvp 或 infra>
- state: proposed
- brief: [Brief](TASK_BRIEF.md)
- brief_revision: r1
- candidate: none
- dependencies: none
- blockers: none
- recovery: none
- next_action: <本次下一条具体动作>
- review: not_run
- verification: not_run
- review_independence: not_run
- execution_independence: not_run

固定键与枚举使用 [PM 合同](../PM_CONTRACT.md)，每键恰好一次；创建实际记录后，将此说明链接改为该记录到合同的相对路径或删除。候选哈希／未跟踪清单、分派身份、更新日期与原因写交接正文，不混入字段值。

## 验收状态

| ID | result | candidate | evidence |
| --- | --- | --- | --- |
| <与 Brief 对应的 ID> | not_run | none | none |

- measurement_validity：<valid / invalid / not_assessed；非性能任务说明不适用>
- performance_comparison：<improved / regressed / no_clear_difference / inconclusive；非性能任务说明不适用>
- 学习复盘：<未安排／待复盘／已完成／不适用；证据链接>

## 交接

- 当前可支持的结论：
- 尚未运行或未审查内容及原因：
- 候选文件／哈希、commit／dirty、未跟踪文件：
- 当前分派、请求配置／可观察配置：
- Unity 占用：<链接到全局唯一登记；未操作不能声称实时状态>
- 最新 Handoff：<R0 可将自检、候选和交接直接保存在本段>
- 状态变更记录：<时间、前后状态、依据；done 需覆盖全部 required 项>
