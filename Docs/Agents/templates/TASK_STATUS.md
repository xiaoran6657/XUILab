# Task Status — <Task-ID>

> 模板；此文件为单个任务流程状态的唯一来源，由主 Agent 更新。

- 更新日期／负责人：
- Brief 修订／链接：
- state：<proposed / ready / running / frozen / verifying / rework / blocked / done / cancelled>
- 当前候选：<candidate-id 或尚未冻结>
- commit／dirty／源文件清单与哈希：
- 当前分派：<角色、Agent ID、尝试号；无则 none>
- Unity 占用：<指向 PROJECT_STATUS.md 的唯一活动记录>

## 验收状态

| Brief 验收项 | 检查结果 | 证据与对应候选 | 未满足原因 |
| --- | --- | --- | --- |
| <ID> | <pass/fail/not_run/not_applicable> | <真实文件> | <原因> |

- review_independence：<independent / self-check / not_run / not_applicable>
- execution_independence：<independent / shared-operator / self-check / not_run / not_applicable>
- measurement_validity：<valid / invalid / not_assessed；非性能任务说明不适用>
- performance_comparison：<improved / regressed / no_clear_difference / inconclusive；非性能任务说明不适用>
- 学习复盘：<未安排／待复盘／已完成／不适用；证据链接>

## 收口或阻塞

- 当前可支持的结论：
- 首个未解决问题／外部条件：
- 尚未运行或未审查内容：
- 恢复条件及第一步动作：
- 最新 Handoff／Review／Verification：
- 状态变更记录：<时间、前后状态、依据；done 需覆盖全部 required 项>
