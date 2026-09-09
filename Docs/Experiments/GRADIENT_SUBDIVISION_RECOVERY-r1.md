# G1 矩阵恢复 r1

冻结计划、候选和协议保持 gradient-subdivision-r2 / g1-matrix-r2。原目录 matrix 已完成前52次，第53次 grid-static-95-s64-r2 在 Warmup 失焦，correctness=pass、measurementValidity=invalid、exitCode=3，1800样本与全部产物保留。PID59640已由启动器 wait 确认退出，当前无目标Player和锁。失败不因帧时大小被选择或替换。

只允许一次明确恢复：新 matrix-recovery1 目录执行原计划第53..160的连续后缀，共108次；原第53次保留为失效attempt，新目录中同runId表示另一个显式attempt，绝不覆盖原目录。原前52次仍来自原目录，不重跑。运行参数、顺序、300/1800帧、场景和Player不变；这次若再失败则立即停下，再单独分析，不自动循环重试。

恢复policy绑定完整原目录文件树及每文件SHA、原计划/构建/gate和恢复工具SHA；原树任何变化、选择跳号、不同输出根、未决intent/failure均拒绝。恢复启动器沿用v2的未知PID状态保留锁和意图，正常wait终态才写收据。新旧启动器源码字节分别保留；新报告按来源校验对应launcher，汇总原52+新108，并明确列出被排除的原失效attempt和policySHA。

这是操作失败恢复附录，不修改原实验阈值、比较规则或质量目标。合并证据须完整通过专用 report 的原始数据/v2收据/环境/精确目录检查并独立复核。不得把原invalid改成valid，不把108次恢复单独称为完整五轮。
