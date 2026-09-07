# 证据统一入口

工具、依赖、搬迁与恢复操作：[离线复现手册](../Agents/REPRODUCIBILITY_PLAYBOOK.md)。项目游标仍以 [PROJECT_STATUS](../PM/PROJECT_STATUS.md)为准，本页不维护任务状态。

| 证据 | 身份／内容 | 权威入口 |
| --- | --- | --- |
| List r3 原始历史证据 | candidate list-r3-8756E9288BE4；build list-dev-20260906T071112Z；dirty 采样 | [M1-04 索引](../PM/Tasks/M1-04/EVIDENCE_INDEX-r3.md) |
| List core 可搬迁目录包 | 正式原始运行／receipt／失败／日志、完整 Player、原协议及固定清单；不含媒体和源码 | [机器可读 catalog](LIST_EVIDENCE_CATALOG.json) |
| List 结果解释 | 主矩阵五轮进程聚合，压力失败保留 | [结果报告](LIST_BENCHMARK_RESULTS.md) · [案例](LIST_LAB_CASE_STUDY.md) |
| M0 校准 | 独立 M0 协议；不与 List 数字混用 | [M0 阶段出口](../PM/M0_STAGE_EXIT.md) · [复跑手册](../Agents/BENCHMARK_RUN_PLAYBOOK.md) |
| 真实操作日志与完整本地归档 | 独立保存本轮源码、Unity/Player检查及历史core/media的身份 | [INFRA-004](../PM/Tasks/INFRA-004/TASK_STATUS.md) · [归档手册](../Agents/SOURCE_ARCHIVE.md) |
| B 工具交付验证 | 目录包哈希、隔离检出覆盖层、自检／独立审查 | [INFRA-002](../PM/Tasks/INFRA-002/TASK_STATUS.md) |

历史 raw、build、媒体在被忽略的 Artifacts；单纯 Git 检出不包含这些文件。接收者需要可信交接的目录包和 bundle.json SHA-256 才能验证数据。缺包就是 evidence not_run，不能用旧文档或生成空样本替代。需要完整历史归档时沿原索引另外交接媒体／诊断，不能把 core 包称为全部证据。
