# 环境快照与实施起点

观察日期：2026-09-05。此页记录本次设计工作中的磁盘检查和 MCP 查询，不是持续更新的运行状态，也不是 M0 验收报告。后续任务必须重新检查实际状态。

## 已观察事实

| 项目 | 观察结果 | 依据 |
| --- | --- | --- |
| 仓库／工程 | `<repo>` ／ `<repo>/XUILab` | 本地目录；MCP project info |
| Unity | `2022.3.45f1c1`，revision `1aff9500e86c` | [ProjectVersion.txt](../../XUILab/ProjectSettings/ProjectVersion.txt) |
| URP／UGUI／TMP | `14.0.11` ／ `1.0.0` ／ `3.0.9` | [manifest.json](../../XUILab/Packages/manifest.json)、[packages-lock.json](../../XUILab/Packages/packages-lock.json) |
| Test Framework | `1.1.33` | 同上 |
| MCP Unity 包 | Git URL 使用 `#beta`；lock hash `acf5e3dd3b864c140862e0c6644ff9e8f2120a64` | 同上；包锁不等于 Python server 的版本 |
| MCP 传输 | stdio，项目查询成功 | 实例资源及 project info |
| 多实例 | 发现两个 Unity 实例；选择后再次确认 XUILab 完整路径 | 实例资源、set_active_instance、project info |
| XUILab 编辑器 | `Assets/Scenes/SampleScene.unity`；非 Play、非暂停、非编译；ready=true | editor state 的本次快照 |
| 当前目标 | `StandaloneWindows64` | MCP project info |
| Git（工作流设计时） | `main` 无首个提交；Docs 与工程等为未跟踪内容；当时 `.gitignore` 为空 | git status、文件检查；本项是历史快照 |

查询时 XUILab 实例 ID 为 `XUILab@759cdb93`。它只用于说明已核对路由，不能写入长期命令。另一个实例不属于本工程；后续操作仍须重新按项目路径选择。

## 尚未被本次检查证明

- 未运行 EditMode／PlayMode 测试、Windows 构建或 Player；没有功能或性能通过结论。
- editor ready 与未编译不等于 Console 没有编译错误；本次没有以 Console 审查证明编译成功。
- 未确认测试场景、Runner、实验配置、视觉基线或自动报告已经建立。
- 未确认场景 dirty 状态；不可据快照直接切场景或覆盖保存。
- 用户的 `uvx --offline --from ...>=0.0.0a0` 使用本地可用包，未读取 Python server 精确版本；后续可在 M0 记录实际版本，不从依赖表达式推断。

## M0-01 的剩余工作建议

1. 依据当前工程而非重新创建模板，核对目录、编译、Windows 构建与启动。
2. 复核后来建立的根 `.gitignore`／`.gitattributes` 是否符合首次提交范围，并决定参考材料与大产物的版本控制方式；未经处理的实习资料不能自然进入公开成果。
3. 固定 manifest／lock 及实际 MCP server 版本信息；`#beta` 是可移动引用，避免无意解析更新。具体固定方式在该任务中决定。
4. 盘点已有额外包，按必要性说明即可，不擅自删包。Performance Testing／Memory Profiler 未列在当前直接依赖中，需要时再评估版本与用途。
5. 初始化实际 PM 状态，记录“工程已创建、MCP 已接通”与剩余验收项；不能把整个 M0 标成完成。

上述是工作流设计时的输入，后续状态以仓库和 PM 实际记录为准。之后已建立根 `.gitignore`／`.gitattributes`，用户也已创建初始提交；这些后续事实不回写成当时已经完成 M0 验收。当前 Unity 工程和 MCP 配置仍应由实际任务重新检查。
