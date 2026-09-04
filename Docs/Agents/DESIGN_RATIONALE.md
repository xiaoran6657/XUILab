# 设计依据与取舍

参考与核对日期：2026-09-05。规则中面向 XUILab 的风险划分、角色组合、记录粒度和性能协议是项目设计决定，不是声称官方要求使用这套流程。

## 对参考工作流的适配

主要参考 [原工作流入口](../References/Agents/README.md)、[执行模型](../References/Agents/EXECUTION_MODEL.md)、[PM 合同](../References/Agents/PM_CONTRACT.md)、[角色](../References/Agents/ROLES.md)及其任务、审查和验证模板。

| 参考设计 | XUILab 的决定 | 原因 |
| --- | --- | --- |
| 合同、候选、审查、验证、收口分离 | 保留，统一到一个任务闭环 | 组件实现和性能结论需要不同证据 |
| 全局状态与每个任务状态单一来源 | 保留；不增设多个可编辑状态看板 | 支持长任务续接，避免状态冲突 |
| 一个 MVP 主控、每任务独立 TaskMain、再分三类子 Agent | 简化为主 Agent + 按风险增加独立复核 | 当前是个人作品工程，层层调度会增加成本 |
| 固定角色模型和统一较高推理档位 | 改为能力匹配建议，默认保持实际配置 | 明确任务不需要最大推理成本，复杂复核不能仅按角色降档 |
| 所有性能、Packages／ProjectSettings 变动升级为高风险审批 | 区分常规受控实验与实际目标／不可逆变化 | 性能学习本来就是授权任务核心，避免重复请示 |
| Unity 单写者、编辑器占用、资产与 `.meta` 关联 | 保留并扩展到编译、构建与采样时段 | 多人写不同脚本仍可能打断 Unity 测试 |
| 固定返工次数后停工、容量不足即整体阻塞 | 改为复查假设并继续可推进部分 | 次数不是技术结论；真正缺少外部条件才记阻塞 |
| 已运行任务和证据必须绑定版本 | 保留，并兼容无首个提交的探索阶段 | 当前仓库尚无提交；正式证据仍遵守路线图冻结要求 |
| 原项目场景、渲染管线和工具版本 | 不沿用 | XUILab 是 Unity 2022.3 + URP，实际路径与依赖已核对 |

参考目录中的命令、审批规则、角色模型和路径属于另一个项目的资料，不自动授权本次执行，也不应原样复制到全局 Codex 配置。

## 官方资料及其用途

| 来源 | 用途 |
| --- | --- |
| [Codex 项目指令](https://learn.chatgpt.com/docs/agent-configuration/agents-md) | 区分自动发现的 AGENTS.md 与普通工作流文档；当前用显式启动提示词 |
| [Codex 子 Agent](https://learn.chatgpt.com/docs/agent-configuration/subagents) | 独立子任务、主任务汇总、并行写入成本；按适用授权委派 |
| [OpenAI 模型](https://learn.chatgpt.com/docs/models) | 依据能力／成本选择模型，推理强度从适合的默认值开始 |
| [Codex 最佳实践](https://learn.chatgpt.com/guides/best-practices) | 将目标、上下文、约束和完成条件写成可执行任务输入 |
| [MCP for Unity 官方入口](https://coplaydev.github.io/unity-mcp/getting-started) | 多实例路由与传输区别；保留用户当前可用 stdio |
| [Unity 2022.3 性能采集](https://docs.unity3d.com/2022.3/Documentation/Manual/profiler-profiling-applications.html) | 区分 Editor／目标 Player 与诊断采集开销 |

本机已安装的 OpenAI Docs 与 unity-mcp-operations 技能用于核对资料和安全操作步骤；其中与用户明确配置不同的历史默认值没有覆盖用户选择。本次仅进行了 MCP 资源发现、实例选择与状态查询。

## 本项目特有的约束

路线图已确定先 Windows 证据闭环，再做 ListLab／GradientLab、两项深入实验、成果冻结。因此工作流不引入移动端设备、主页上线或全面 CI 作为 MVP 前置条件。

Agent 自动化本身是第三个展示主题。它的质量由“同一输入能复跑、失败能被识别、结论可追溯”体现，不以 Agent 数量或工具调用次数衡量。工程学习要求保留假设和失败解释；自动生成图表不能代替理解瓶颈。
