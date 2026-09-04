# PM 状态与交接合同

## 单一事实来源

以下为首次实施时创建的路径约定，当前工作流设计不预填任务完成记录。

| 路径 | 唯一职责 | 写入者 |
| --- | --- | --- |
| `Docs/MVP/ROADMAP.md` | 阶段目标、任务依赖、里程碑验收 | 主 Agent 按实际授权维护 |
| `Docs/PM/PROJECT_STATUS.md` | 当前阶段／任务指针、全局阻塞、Unity 占用登记、最近交接入口 | 主 Agent |
| `Docs/PM/Next_Actions.md` | 按依赖排序的任务链接和建议下一步；不是第二份状态表 | 主 Agent |
| `Docs/PM/Tasks/<Task-ID>/TASK_BRIEF.md` | 目标、范围、验收、授权依据和合同修订 | 主 Agent |
| `Docs/PM/Tasks/<Task-ID>/TASK_STATUS.md` | 该任务唯一流程状态、当前候选身份、检查结果和证据链接 | 主 Agent |
| 同任务目录下 `HANDOFF-r<N>.md` | 每次实现交接的文件、检查、限制 | Implementer |
| 同任务目录下 `REVIEW-r<N>.md`、`VERIFICATION-r<N>.md` | 针对明确候选的审查与实际验证记录 | 对应 Reviewer／Validator |
| `Docs/Experiments/` | 实验协议、结果解释、优化决策 | 任务指定作者 |
| `Artifacts/<run-id>/` | 原始运行记录、逐帧数据、日志、诊断和媒体 | Runner／指定采集者 |

路线图不记录每次测试结果；Brief 不复制可变流程状态；全局状态引用任务记录。修订历史保留旧报告，不用覆盖旧数据来“更新为通过”。`Artifacts` 是逻辑归档约定，是否提交大文件在 M0 决定；本机路径失效前必须交接可访问的归档位置和哈希。

可复制模板：[Task Brief](templates/TASK_BRIEF.md)、[Task Status](templates/TASK_STATUS.md)、[Handoff](templates/HANDOFF.md)、[Review](templates/REVIEW.md)、[Verification](templates/VERIFICATION.md)。全局状态只需按上表职责建立，首轮没有实验数据时不创建空的实验报告。

## 状态机

`proposed → ready → running → frozen → verifying → done`

- proposed：已识别，尚未具备完整授权／合同／依赖。
- ready：授权、依赖和必要输入具备，可以开始。
- running：正在实施或定位问题。
- frozen：候选及清单已固定，停止相关写入，等待检查。
- verifying：审查／验证正在进行，包括等待异步测试结束。
- rework：检查发现需修复问题；恢复 running 后产生新候选。
- blocked：缺少明确外部条件；写明阻塞原因、可继续部分与恢复条件。
- done：所有 required 验收项已有符合要求的结果；实验结论不要求一定变快。
- cancelled：用户取消或范围决定明确取消，保留原因和部分产物。

R0 可以在同一轮完成 frozen、verifying 和 done 的记录，无需为流程制造多个任务。任一非终态可进入 blocked；恢复时回到阻塞前适当阶段。检查失败通常进入 rework，不自动等于 blocked。

任务流程状态和检查结果分开：检查结果用 `pass / fail / not_run / not_applicable`，测量有效性另用 `valid / invalid / not_assessed`，性能解释用 `improved / regressed / no_clear_difference / inconclusive`。不要用一个 PASS 覆盖不同层次。

这是路线图中文状态的执行细化：proposed／ready 对应待开始，running／rework 对应进行中，frozen／verifying 对应待验收，done 对应已完成，blocked 对应阻塞。展示时可使用中文，任务记录只维护一个规范状态值，不另存一套可漂移的中文状态。

## Unity 占用登记

在全局状态中只保存一份活动记录：owner、Task-ID、完整 project root、操作目的、取得时间、恢复约定、预期结束条件、是否处于正式测量。它是协作约定，不是操作系统互斥锁。

取得前确认无其他 owner、编辑器实际状态匹配；占用期间禁止其他写者触发导入。结束后核对测试／Play／构建已停止、恢复约定已履行，再释放。崩溃或失联后先检查实际进程与编辑器状态，不根据时间戳过期就强抢。

## 候选与证据身份

有 Git 提交时记录 commit、dirty 状态、未提交文件清单及内容哈希；没有提交时记录 `commit: none` 和显式选定源文件／配置的 SHA-256 清单。未跟踪文件不在普通 `git diff` 中，必须另外记录。

候选清单至少覆盖受影响源码、关联 `.meta`、场景／预制体、依赖 manifest 与 lock、相关 ProjectSettings、测试／Runner、实验输入。构建与运行使用独立 build-id／run-id 并反向引用候选。生成目录如 `Library` 不作为源文件清单。

首次提交缺失不阻止早期探索实验；按既有路线图，M4 正式基准使用干净、可复建的提交并保存构建与数据身份。后续修改代码不能让旧报告自动变成新候选的证据。

## 最小持久交接

每次任务完成、受阻或上下文交接前，至少留下：当前候选／工作区、已完成验收、首个未解决问题、实际测试证据、Unity 占用状态、下一条可执行动作。未运行项目明确写 not_run。

任务做了什么由 Handoff 说明；能否接受由主 Agent 汇总真实检查判断。主 Agent 更新顺序为：任务记录 → 全局游标 → 下一步链接。不要让子 Agent 同时维护多份全局状态。
