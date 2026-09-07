# PM 状态与交接合同

## 单一事实来源

下表定义当前职责。模板不是执行证据；只有任务获得对应授权后才创建实际记录。

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

路线图不记录动态进度和每次测试结果；Brief 不复制可变流程状态；全局状态引用任务记录。Next Actions 只列尚待处理的动作，移出已完成／取消任务，不附 done 或审查结论。修订历史保留旧报告，不用覆盖旧数据来“更新为通过”。`Artifacts` 按根 `.gitignore` 忽略；本机路径失效前必须交接可访问的归档位置和哈希。

可复制模板：[Task Brief](templates/TASK_BRIEF.md)、[Task Status](templates/TASK_STATUS.md)、[Handoff](templates/HANDOFF.md)、[Review](templates/REVIEW.md)、[Verification](templates/VERIFICATION.md)。全局状态只需按上表职责建立，首轮没有实验数据时不创建空的实验报告。

## 任务类型与编号

- `mvp`：使用路线图已有 ID，例如 `M2-01`、`M3-L1`；范围与依赖由相应阶段定义。
- `infra`：使用 `INFRA-NNN`，三位十进制顺序号，从 `001` 起，建档前检查现有 Tasks 目录避免重号。用于工作流、PM、工具和工程支撑；范围由获授权的 Brief 定义，不计入 MVP 功能完成。

两类共用 `Docs/PM/Tasks/<Task-ID>/` 和以下状态机。单个 INFRA 任务不代表后续批次或 MVP 获得授权。没有实际授权／需要时不预建空任务、报告或新的管理目录。

## 新记录的固定字段（xuilab.pm/v1）

新 TASK_STATUS 使用模板中的 ASCII `- key: value` 行。每个固定键恰好一次，值不加反引号、不带解释后缀；中文解释写在交接正文。这里的格式版本不改变历史实验协议。

| 字段 | 值与职责 |
| --- | --- |
| pm_schema | `xuilab.pm/v1` |
| task_id / task_type | 目录 ID；`mvp` 或 `infra`，与 Brief 一致 |
| state | 下文状态机中的单个值 |
| brief / brief_revision | 本任务 TASK_BRIEF 的相对 Markdown 链接；`r<N>`，与 Brief 同值 |
| candidate | 未冻结为 `none`，否则为无空白的候选 ID；frozen/verifying/done 必须有候选 |
| dependencies | `none` 或其他任务 TASK_STATUS 的相对 Markdown 链接；不自依赖、不循环。ready/running/frozen/verifying/done 的依赖任务必须 done |
| blockers / recovery | 无问题为 `none`，否则写明确问题／恢复条件；blocked 时两项均不能为 none |
| next_action | 一条具体动作；终态可写“等待新授权”，不要在其他页面复制该动作细节 |
| review / verification | `not_run` 或本候选报告的相对 Markdown 链接 |
| review_independence | `independent / self-check / not_run / not_applicable` 中一项 |
| execution_independence | `independent / shared-operator / self-check / not_run / not_applicable` 中一项 |

Brief 固定键为 `brief_revision`、`task_type`、`risk`（R0–R3）、`review_required`、`execution_required`（后两项为 `true/false`）。R2/R3 的 review_required 必须 true；普通 R2 不自动要求独立执行。已有授权即可填写依据，不重复请求许可。

Brief 的 `## 验收矩阵` 使用 `ID | requirement | 判据` 三列；ID 唯一，requirement 为 `required` 或 `not_applicable`，判据／不适用理由非空。Status 的 `## 验收状态` 使用 `ID | result | candidate | evidence` 四列，与 Brief 逐项对应，result 为 `pass/fail/not_run/not_applicable`。required 不得改成 not_applicable；done 的每个 required 项必须 pass、候选一致且 evidence 链接到真实文件。

被 Status 引用的新 Review/Verification 必须声明 `- candidate: <ID>` 与 `- brief_revision: r<N>`。Review 另声明 verdict，值为 `accept / changes_requested / not_reviewable` 中一项。若 review_required=true，done 需要独立审查、实际 Review 链接和 accept；若 execution_required=true，done 需要独立执行与 Verification 链接。检查器只能比对声明与文件存在性，作者身份、结论真实性和证据充分性由主 Agent 核对。

## 全局游标和历史兼容

PROJECT_STATUS 只保存一组固定键：`current_task`（非终态 TASK_STATUS 链接或 none）、`latest_task`（最近结束的任务链接或 none）、`unity_owner`（一个 owner ID 或 none）、`unity_task`（占用任务链接或 none）。owner/task 必须一起为空或一起登记；多角色不产生多份 owner。阶段出口摘要可在本页引用，其证据详情仍由任务／阶段出口维护。

当前八个历史任务 `M0-01`–`M0-04`、`M1-01`–`M1-04` 未声明 pm_schema，保留其原格式和历史候选字节。结构检查只读取它们已有 state 的规范前缀供依赖和队列核对，并明确报告 legacy 覆盖限制；不重新验证其旧验收。此兼容名单固定，不按缺少字段自动扩大。其他任务缺 schema 或 schema 未知都报错。

后续若获授权重开历史任务，先评估相关哈希／索引，再显式迁移其当前状态入口到 v1，并从检查器兼容名单移除该 ID，避免删除 schema 后退回旧模式；保留旧 Review、Verification 与冻结清单，不静默回写历史证据。历史报告和协议版本说明不参加新记录字段迁移。

## R0 精简与结构检查

仅当风险为 R0 且不要求独立审查／执行时，可只保留 Brief + Status：固定字段与验收矩阵仍填写；候选身份、自检证据和交接写在 Status 的独立正文段，并用本文件锚点引用。无需为了过程生成空 Handoff/Review/Verification。R1+ 或 required 独立复核使用实际候选与报告。

维护后按 [PM 检查手册](PM_CHECK_PLAYBOOK.md)执行离线检查，再人工核对授权和事实。该工具不修改状态、不计算验收结论、不操作 Unity，也不取代候选哈希检查。通过只表示所覆盖的结构一致。

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

在全局状态中只保存一份活动记录：固定键 unity_owner/unity_task，加上完整 project root、操作目的、取得时间、恢复约定、预期结束条件、是否处于正式测量的正文。不要另外登记第二个 owner。它是协作约定，不是操作系统互斥锁。

取得前确认无其他 owner、编辑器实际状态匹配；占用期间禁止其他写者触发导入。结束后核对测试／Play／构建已停止、恢复约定已履行，再释放。崩溃或失联后先检查实际进程与编辑器状态，不根据时间戳过期就强抢。

## 候选与证据身份

有 Git 提交时记录 commit、dirty 状态、未提交文件清单及内容哈希；没有提交时记录 `commit: none` 和显式选定源文件／配置的 SHA-256 清单。未跟踪文件不在普通 `git diff` 中，必须另外记录。

候选清单至少覆盖受影响源码、关联 `.meta`、场景／预制体、依赖 manifest 与 lock、相关 ProjectSettings、测试／Runner、实验输入。构建与运行使用独立 build-id／run-id 并反向引用候选。生成目录如 `Library` 不作为源文件清单。

首次提交缺失不阻止早期探索实验；按既有路线图，M4 正式基准使用干净、可复建的提交并保存构建与数据身份。后续修改代码不能让旧报告自动变成新候选的证据。

## Unity 操作与验收引用

Agent build/test 记录遵守[操作追踪手册](UNITY_OPERATION_JOURNAL.md)。Handoff/Verification 引用 operation-id、journal 归档位置与哈希、最后动作及恢复缺口；journal 只保存操作事实，不新增任务状态或 Unity owner。静态阶段条款见[验收映射](../MVP/ACCEPTANCE_MAP.md)，实际判据和结果仍分别在 Brief/Status。

## 最小持久交接

每次任务完成、受阻或上下文交接前，至少留下：当前候选／工作区、已完成验收、首个未解决问题、实际测试证据、Unity 占用状态、下一条可执行动作。未运行项目明确写 not_run。

任务做了什么由 Handoff 说明；能否接受由主 Agent 汇总真实检查判断。主 Agent 更新顺序为：任务记录 → 全局游标 → 下一步链接。不要让子 Agent 同时维护多份全局状态。
