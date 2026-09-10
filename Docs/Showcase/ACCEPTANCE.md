# MVP验收记录

候选m4-final-b017672，源码b0176724d58c7cda86b472340845d239714888d0。任务动态状态以[M4-04](../PM/Tasks/M4-04/TASK_STATUS.md)为准。技术交付已完成，并通过归档、分项验证和最终独立审查；用户个人学习复盘仍not_run，不能声明整个MVP已全部验收。

| 阶段出口 | 结果 | 证据 |
| --- | --- | --- |
| 固定版本与可重建Release | pass | [M4-01验证](../PM/Tasks/M4-01/VERIFICATION-r1.md)、[Release验证](../PM/Tasks/M4-02/VERIFICATION-r1.md) |
| List/Gradient回归与两项优化决策 | pass | [独立证据审查](../PM/Tasks/M4-01/REVIEW-r2.md)，改善/不明确均按预定判据保留 |
| 每条性能结论能定位有效原始run | pass | [结果](RESULTS.md)、[130-run索引](RUN_INDEX.md)、[证据](EvidenceIndex.md) |
| Runner normal/fail/invalid边界 | pass | 三次smoke与[Agent案例](AgentBenchmark/CASE.md)，失败不假通过 |
| 三主题媒体、说明、链接和哈希 | pass | [媒体](MEDIA.md)、[M4-03](../PM/Tasks/M4-03/TASK_STATUS.md)，[独立视觉审查](../PM/Tasks/M4-03/REVIEW-r1.md)已接受 |
| 来源/许可/贡献与结果边界 | pass | [SOURCES](SOURCES.md)、M4-01独立审查；本地原始归档不公开 |
| 用户两项核心实验解释复盘 | not_run | 用户选择先技术交付后自学；[学习入口](../Learn/README.md) |
| 本地完整归档与最终文档审查 | pass | [归档](ARCHIVE.md)、[最终独立审查](../PM/Tasks/M4-04/REVIEW-r1.md) |

## 个人复盘的最小完成条件

用户能用自己的话，结合本仓库源码和一次实际结果，解释：

1. 列表为什么同时需要池、虚拟化和局部刷新；何时TargetOnly有收益，为什么batch/60FPS不能同样推广；如何证明离屏更新、重入与异常后仍正确。
2. 渐变颜色函数、截面、网格和量化的区别；为什么Fixed32会quality-limited；自适应的误差、实际段数、选择成本与fallback如何共同约束结论。

无需先完成个人主页，也不要求再跑130次矩阵。可以先按学习材料自学，再提交问题或解释，由后续任务记录实际复盘结果；不能用Agent代答来标pass。

## 保留的限制

只验证本机Windows、固定版本和协议。性能是帧间隔，CPU/GPU/GC/内存分项unavailable；列表未选六组、其他N和应用冷启动性能未测；渐变Fixed32并非所有场景等质量基线。三视频是脚本按帧驱动的演示，非实时性能录像。源码后续变化需重评受影响证据，公开发布/推送不在本次授权内。
