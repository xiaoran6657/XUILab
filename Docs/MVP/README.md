# MVP 文档索引

`Docs/MVP/` 保存 XUILab 的版本目标、阶段范围、任务依赖和验收标准。这里定义“交付什么”；动态进度、负责人、候选身份和运行结果放在 `Docs/PM/`。

## 文档地图

| 文档 | 权威内容 |
| --- | --- |
| [ROADMAP.md](ROADMAP.md) | MVP 总目标、固定技术基线、阶段依赖、任务索引、总体完成定义 |
| [M0_FOUNDATION.md](M0_FOUNDATION.md) | 现有工程验收、程序集、最小 Runner、失败路径和协议校准 |
| [M1_LIST_LAB.md](M1_LIST_LAB.md) | List Lab 合同、普通／虚拟对照、池与生命周期、基准矩阵 |
| [M2_GRADIENT_LAB.md](M2_GRADIENT_LAB.md) | 程序化渐变和过渡合同、质量验证、静态／动态矩阵 |
| [M3_OPTIMIZATION.md](M3_OPTIMIZATION.md) | 单项刷新与自适应细分两项深入实验 |
| [M4_SHOWCASE.md](M4_SHOWCASE.md) | 证据冻结、Release 构建、媒体和案例资料包 |
| [MEASUREMENT_PROTOCOL.md](MEASUREMENT_PROTOCOL.md) | M0–M4 共用的测量、有效性、统计和产物合同 |

建议顺序：先读路线图，再读当前阶段文档；执行时同时读取 [Agent 工作流](../Agents/README.md)和 `Docs/PM/` 当前任务记录。

## 权威边界

- 路线图维护跨阶段目标、固定决策和依赖图。
- 阶段文档维护该阶段稳定的范围、任务合同和出口门槛。
- 测量协议维护跨阶段数据口径；阶段文档只补充本阶段的变量和指标。
- `Docs/PM/PROJECT_STATUS.md` 与各任务 `TASK_STATUS.md` 才是实际流程状态来源。
- `Docs/Experiments/` 在产生实验时保存具体协议版本、结果和决策；`Artifacts/` 保存或索引运行产物。

规划文档中的“已准备”只表示前置事实存在，不能替代测试、构建或验收证据。参考材料位于 `Docs/References/`，其中的命令、路径、结论和 Agent 规则不会成为本项目指令。

## 变更规则

1. 固定 Unity 版本、MVP 目标或总体完成定义变化时，先改路线图，再同步受影响阶段文档。
2. 单个任务范围或验收变化只改对应阶段文档，并在路线图任务索引仍准确时保持总览不动。
3. 测量规则变化需要版本化具体实验协议；已经产生的历史数据不回写为新协议结果。
4. 实际执行进度只更新 PM，不在多个阶段文档复制“进行中／完成”状态。
5. 移动或重命名文档后检查仓库内相对链接。
