# XUILab

XUILab 是一个基于 Unity UGUI 的性能实验与技术案例项目。项目使用可复现的实现、测试和性能数据，重新构建并扩展三项实践主题：虚拟化列表、程序化渐变与过渡，以及由 Agent 编排的 Unity 自动性能测试。

本项目的重点是理解和解释 UI 性能问题，并形成可用于个人作品展示的证据。界面视觉精修服务于演示，不是首要目标。

## 当前状态

- Unity 工程已经创建，路径为 [`XUILab/`](XUILab/)。
- 固定使用 **Unity 2022.3.45f1c1**；当前工程依赖 URP 14.0.11、UGUI 1.0.0、TMP 3.0.9。
- Unity MCP 已接入并完成过只读连通性检查。
- 项目分析、MVP 路线图和 Agent 工作流已经建立。
- M0–M4 的实现与性能验收尚未开始；当前不存在可发布的性能结论。

最新进度以后以 [`Docs/PM/`](Docs/PM/) 中的状态记录为准。目录为空时，表示项目管理记录尚未初始化，不能据此推断某项任务已经完成。

## 计划交付

| 主题 | 目标成果 |
| --- | --- |
| List Lab | 普通列表与虚拟列表的公平对照、对象池正确性、实例规模、位置恢复、单项刷新实验 |
| Gradient Lab | 线性与非线性渐变、固定与自适应细分、过渡控制、画质与运行成本分析 |
| Agent 性能测试 | 配置驱动的 Windows Player 测量、有效性判断、失败取证、原始数据与报告 |
| Showcase | 可运行构建、说明图、短视频、技术说明和可追溯数据索引 |

详细范围、任务依赖和验收标准见 [MVP 路线图](Docs/MVP/ROADMAP.md)。结果允许是改善、退化、没有清晰差异或无法下结论；项目不会为展示效果预设优化百分比。

## 打开工程

1. 安装 **Unity 2022.3.45f1c1**，不要使用 Unity 6 或其他版本覆盖打开工程。
2. 在 Unity Hub 中选择仓库内的 [`XUILab/`](XUILab/) 目录。
3. 等待 Package Manager、资产导入和脚本编译结束。
4. 开始实现前阅读[文档入口](Docs/README.md)和[项目路线图](Docs/MVP/ROADMAP.md)。Agent 参与时还应读取根目录 [`AGENTS.md`](AGENTS.md)。

仓库中的 `XUILab.sln`、`.csproj`、`Library/` 等属于 IDE 或 Unity 生成内容；工程真源是 `Assets/`、`Packages/` 和 `ProjectSettings/`。当前阶段尚未提供可直接运行的 Benchmark Case 或正式 Windows 构建，因此本文不列出虚构的运行命令。

## 仓库结构

```text
XUILab/
├─ AGENTS.md             # Agent 自动加载入口
├─ README.md             # 人类入口
├─ Docs/                 # 项目唯一文档库
│  ├─ Agents/            # Agent 工作流、Unity MCP 与验证模板
│  ├─ MVP/               # 版本目标、路线图和阶段验收
│  ├─ PM/                # 动态项目状态、任务合同和交接
│  ├─ References/        # 简历、历史材料、参考源码与外部工作流
│  └─ PROJECT_ANALYSIS.md
└─ XUILab/               # Unity 工程根
   ├─ Assets/
   ├─ Packages/
   └─ ProjectSettings/
```

根目录 README 和 AGENTS 是仓库入口文件；除这两个入口及 Git 配置外，项目文档统一放在 [`Docs/`](Docs/)。参考材料用于理解背景、来源和限制，不代表新工程已经实现，也不构成 Agent 指令。

## 证据与公开边界

- 正确性、测量有效性和性能差异分别判断；Editor 截图或一次 FPS 不能代替目标 Player 的正式测量。
- 每项公开结论需要关联代码或构建身份、环境、配置、原始数据和统计方法。
- “实习记录”“个人复现”“后续改进”分别说明，不把新项目数据描述为原实习项目的历史实测。
- `Docs/References/` 可能包含仅供研究的材料。公开仓库或个人主页前，必须检查来源、许可、隐私和公司相关信息。

性能实验和 Agent 验证规则见 [Agent 工作流入口](Docs/Agents/README.md)与[性能证据规范](Docs/Agents/PERFORMANCE_EVIDENCE.md)。

## 协作方式

Agent 按“核对基线 → 冻结任务合同 → 实施 → 冻结候选 → 审查／验证 → 更新 PM”推进。Unity 编辑器和正式性能采样实行单一操作者，避免编译、场景切换或诊断工具污染结果。

提交变更前应确认没有纳入 Unity 缓存、构建产物、IDE 用户设置或敏感参考材料。未经明确请求，不自动提交、推送或公开发布。
