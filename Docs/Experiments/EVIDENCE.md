# 证据统一入口

工具、依赖、搬迁与恢复操作：[离线复现手册](../Agents/REPRODUCIBILITY_PLAYBOOK.md)。项目游标仍以 [PROJECT_STATUS](../PM/PROJECT_STATUS.md)为准，本页不维护任务状态。

| 证据 | 身份／内容 | 权威入口 |
| --- | --- | --- |
| List r3 原始历史证据 | candidate list-r3-8756E9288BE4；build list-dev-20260906T071112Z；dirty 采样 | [M1-04 索引（历史记录未公开）](../Showcase/HISTORICAL_RECORDS.md) |
| List core 可搬迁目录包 | 正式原始运行／receipt／失败／日志、完整 Player、原协议及固定清单；不含媒体和源码 | [机器可读 catalog](LIST_EVIDENCE_CATALOG.json) |
| List 结果解释 | 主矩阵五轮进程聚合，压力失败保留 | [结果报告](LIST_BENCHMARK_RESULTS.md) · [案例](LIST_LAB_CASE_STUDY.md) |
| M0 校准 | 独立 M0 协议；不与 List 数字混用 | [M0 阶段出口（历史记录未公开）](../Showcase/HISTORICAL_RECORDS.md) · [复跑手册](../Agents/BENCHMARK_RUN_PLAYBOOK.md) |
| 真实操作日志与完整本地归档 | 独立保存本轮源码、Unity/Player检查及历史core/media的身份 | [INFRA-004（历史记录未公开）](../Showcase/HISTORICAL_RECORDS.md) · [归档手册](../Agents/SOURCE_ARCHIVE.md) |
| B 工具交付验证 | 目录包哈希、隔离检出覆盖层、自检／独立审查 | [INFRA-002（历史记录未公开）](../Showcase/HISTORICAL_RECORDS.md) |

历史 raw、build、媒体在被忽略的 Artifacts；单纯 Git 检出不包含这些文件。接收者需要可信交接的目录包和 bundle.json SHA-256 才能验证数据。缺包就是 evidence not_run，不能用旧文档或生成空样本替代。需要完整历史归档时沿原索引另外交接媒体／诊断，不能把 core 包称为全部证据。

Gradient r5 历史partial矩阵、完整构建/272源输入/质量/媒体与可搬迁归档见[M2证据索引（历史记录未公开）](../Showcase/HISTORICAL_RECORDS.md)。[结果](GRADIENT_BENCHMARK_RESULTS.md)及[案例](GRADIENT_LAB_CASE_STUDY.md)保留限制；历史复算不代表新Player执行。

M3列表/固定段/自适应实验与历史包入口：[列表](LIST_REFRESH_RESULTS.md)、[固定段](GRADIENT_SUBDIVISION_RESULTS.md)、[自适应](GRADIENT_ADAPTIVE_RESULTS.md)。综合默认、代表回归与学习边界见[M3决定](M3_OPTIMIZATION_DECISIONS.md)。
