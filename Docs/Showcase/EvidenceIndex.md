# 最终证据索引

本页描述已产生证据及边界；任务是否接受仍由[M4-01状态](../PM/Tasks/M4-01/TASK_STATUS.md)决定。个人学习复盘单独记录，文档存在不等于用户已完成理解。

## 身份与构建

- 源码提交 b0176724d58c7cda86b472340845d239714888d0，候选m4-final-b017672；[391输入清单](../../Artifacts/m4-final-validation/source-manifest-r1.json)。冻结时源码干净，后续PM/Showcase记录不改变这些输入；当前工作树含未提交文档。
- 列表Development：[构建清单](../../Artifacts/m4-list-build-manifest-r1.json)，buildId m4-development-b017672-r1。
- 渐变Development：[构建清单](../../Artifacts/m4-gradient-build-manifest-r2.json)，buildId m4-gradient-development-b017672-r2；[首场景修订](../PM/Tasks/M4-01/MATRIX-r2.md)。
- Release展示：[构建原始终态](../../Artifacts/m4-final-validation/release-terminal-r1.json)、[Player目录](../../Artifacts/m4-final-release-r1/)。它不提供上述Development矩阵的性能样本。
- 测试、门禁、journal、源码恢复：[验证记录](../PM/Tasks/M4-01/VERIFICATION-r1.md)。代表回归与完整程序集检查有重叠，不相加冒充不同测试总数。

## 从结论追到原始数据

[结果与统计边界](RESULTS.md) → [130-run索引](RUN_INDEX.md) → 每次config/environment/samples/summary/binding → 下表计划/构建。完整p50/p95/p99、最大帧时、超预算比例、质量与算法计数保留在报告，图表只能引用这些固定输入。

| 主题 | 固定计划/门禁 | 完整报告 | 启动与恢复 |
| --- | --- | --- | --- |
| List 50 | [plan](../../Artifacts/m4-final-validation/list-matrix-plan-r1.json)、[gate](../../Artifacts/m4-final-validation/list-preflight-r1.json) | [JSON](../../Artifacts/m4-final-validation/list-report-r1/list-refresh-subset-report.json)、[CSV](../../Artifacts/m4-final-validation/list-report-r1/list-refresh-subset-chart-data.csv) | [聚合来源](../../Artifacts/m4-final-validation/list-merge-verification-r1.json)、[恢复policy](../../Artifacts/m4-final-validation/list-recovery-policy-r1.json)、[独立恢复审查](../PM/Tasks/M4-01/RECOVERY_REVIEW-r1.md) |
| Gradient 80 | [plan](../../Artifacts/m4-final-validation/gradient-matrix-plan-r2.json)、[gate](../../Artifacts/m4-final-validation/gradient-preflight-r1.json) | [完整JSON](../../Artifacts/m4-final-validation/gradient-report-r2.json) | [policy](../../Artifacts/m4-final-validation/gradient-policy-r2.json)、[构建入口修订与原失败](../../Artifacts/m4-final-validation/gradient-campaign-prepared-r2.json) |

列表聚合目录为逐字节副本；原启动receipt仍指向真实原root，不重写启动路径。前14次与后36次分别在原目录核对receipt/raw，再按650项来源清单聚合。统一报告中的dirty:false是被测源码身份，不代表生成文档后的整个仓库无未提交文件。

## 保留的失败与诊断

| 记录 | 实际终态 | 用途 |
| --- | --- | --- |
| [List初始attempt目录](../../Artifacts/m4-list-runs-r1/) | 第15次wall-clock timeout；无raw；前14次有效 | 原目录185文件由恢复policy固定，不删除失败或原成功证据 |
| [Gradient错误入口attempt](../../Artifacts/m4-gradient-runs-r1/) | 首次exit2、无raw | 全部3文件由r2准备记录固定，改用正确首场景构建 |
| [Release smoke-r1](../../Artifacts/m4-final-media/smoke-r1-receipt.json) | 32检查、6图片、正常退出与恢复pass | normal=Completed/Pass/Valid/exit0；fail=Failed/NotRun/NotAssessed/exit1；invalid=Completed/Pass/Invalid/exit3，均是诊断 |

诊断中的fail/invalid是预设反例；进程exit0只表示整个展示验证正确识别了这些反例，不把内部fail/invalid算作正式样本成功。

## 来源与学习

[来源、许可、个人贡献边界](SOURCES.md)，[两主题学习文档](../Learn/README.md)，[Profiler解读](../Learn/PROFILER_GUIDE.md)。当前个人学习复盘待用户完成，技术证据已生成的事实与个人理解分开。

大文件在被忽略的Artifacts目录。完整保存与恢复见[归档说明](ARCHIVE.md)，可运行包见[RUNNING](RUNNING.md)，图片与视频见[MEDIA](MEDIA.md)。仅Git checkout不包含原始运行数据；没有公开发布或推送。
