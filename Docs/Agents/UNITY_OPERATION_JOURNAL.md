# Unity 操作追踪与中断恢复

适用 Agent 发起的单个 MCP build/test job。实现为 [operation_journal.py](../../Tools/UnityOperations/operation_journal.py)，只依赖 Python 3.11+ 标准库，不调用 Unity。实际操作仍遵守 [Unity 手册](UNITY_MCP_PLAYBOOK.md)及 [PM 合同](PM_CONTRACT.md)。批量构建、手点 Editor 菜单、自定义构建菜单不受此工具的防重发约束；不要声称它替换了 Unity 内部 job store。

## 持久身份

默认目录 `Artifacts/unity-operations/<operation-id>/`。文件依次为 `request.json`、`claim.json`、`receipt.json`、`terminal.json`、`restore.json`，只写一次。request 的冻结内容决定 SHA-256 operation-id；instance/operator/before 是观测字段，不用于制造新 ID。修改 attempt、配置或候选会生成新 ID，因此不得为了绕过 claim 随意改变它们。不同 ID 没有全局互斥，唯一 Unity owner 仍由 PM 维护。

发起前必须先持久化 claim，只有 claim 命令返回 exit 0 / dispatch_once 的这一次调用者可以立即发起一次对应 MCP 请求；不得根据之前会话的成功输出再发起。原子独占文件写入防止同 ID 并发 claim。进程在 claim 写入后、发送前中断会产生保守阻塞；这是避免不确定重发的代价。空文件、截断 JSON、链接／junction、未知 schema 均阻塞，不能删文件“恢复”。这不是对人工伪造证据的签名验证；Operator 必须真实保存原始观测，Reviewer核对来源。

## 请求与命令

以下仅为结构示例；实际 Task Brief 决定必要输入、完整参数和恢复内容。inputs 必须覆盖候选源代码、.meta、场景、包、设置、Runner 与实验配置；可从候选清单生成，不能只选一个无关文件。before 必须在当前完整工程发现及状态检查后填写，不能复用历史快照。路径为仓库相对斜杠路径，SHA-256 使用小写。

```json
{
  "schema": "xuilab.unity-operation/v1",
  "kind": "build",
  "task": "M2-04",
  "candidate": "example-only",
  "attempt": "build-r1",
  "project": "XUILab",
  "editor": "2022.3.45f1c1",
  "instance": "fresh-discovery-id",
  "operator": "assigned-owner",
  "parameters": {
    "platform": "StandaloneWindows64",
    "output_path": "Artifacts/example/player.exe",
    "scenes": ["Assets/Scenes/Example.unity"],
    "development": true
  },
  "inputs": {"path/from/candidate": "replace-with-actual-64-hex-sha256"},
  "artifacts": ["Artifacts/example/player.exe", "Artifacts/example/UnityPlayer.dll"],
  "before": {"playing": false, "paused": false, "compiling": false, "importing": false, "tests_running": false, "build_running": false, "prefab_stage": false, "dirty_scene": false},
  "restore_expected": {"playing": false, "paused": false, "scene": "record-original-scene", "dirty_scene": false}
}
```

test 使用 `kind: test`，parameters 至少有 `mode: EditMode` 或 `PlayMode`，并保存实际筛选条件。artifacts 可以为空，因为原始终态摘要本身写入 journal；需要 XML 时在 artifacts 声明路径。build 必须声明输出 exe 为第一项及所需构建文件；工具只检查声明项，完整 Player 分发仍由证据包清单检查。所有声明产物在 claim 前必须不存在，以免旧文件冒充新构建。

```powershell
python -B Tools/UnityOperations/operation_journal.py prepare --file Artifacts/request.json
python -B Tools/UnityOperations/operation_journal.py inspect --operation <returned-id>
python -B Tools/UnityOperations/operation_journal.py claim --operation <returned-id>
# 仅 claim 本次成功后：执行一次已冻结参数的结构化 MCP 调用。
python -B Tools/UnityOperations/operation_journal.py receipt --operation <returned-id> --file Artifacts/receipt-envelope.json
# 后续只轮询原 job；获得实际终态后：
python -B Tools/UnityOperations/operation_journal.py terminal --operation <returned-id> --file Artifacts/terminal-envelope.json
python -B Tools/UnityOperations/operation_journal.py restore --operation <returned-id> --file Artifacts/restoration-envelope.json
```

所有命令可通过 `--root` 指定仓库，`--store` 指定本次持久记录位置。不要更换 store 绕过原记录。写入命令 exit 0 仅表示记录被接受；必须读取 inspect 的 outcome/restoration，不能把 CLI exit 0 当构建通过。

## 原始响应与终态

receipt/terminal envelope 字段为 `operation`、`project_root`（Python 展开的绝对工程路径）、`candidate`、`instance`、`observed_at`（统一 UTC ISO 8601）、`response`。response 保存结构化 MCP JSON 的原始 `success/data`；外层 MCP content 文本若包着 JSON，只解码一层，不改内部字段。工程/candidate 是 Operator 与当次 project info 和请求比对后的绑定，MCP job 回应通常不自带项目路径，不能误称原生证明。

支持本仓库安装 MCP 包 `acf5e3dd3b` 的单 job 字段结构：build data 为 `job_id/result/platform/output_path/errors/completed_at`；test data 为 `job_id/status/mode/finished_unix_ms/result.summary`，summary 为 `total/passed/failed/skipped/resultState`。工具升级后先核对 schema；未知形式保留原始返回并人工核对，不能改成 succeeded 凑兼容。

build 只有 succeeded、零 errors、存在完成时间、平台／输出匹配且声明产物存在非空，才记录 pass。test 只有 succeeded、summary.resultState=Passed、结束时间、非零总数且全部 passed、零 failed/skipped 才 pass；跳过需另走任务合同审查，不自动接受。failed/cancelled/skipped 为 fail，running/pending/未知 job/错误回应不能写终态。终态保存产物 SHA-256，inspect 重查漂移与记录一致性。工具不证明 Player 能启动、不做性能判定。

restore envelope 包含 `operation/project_root/observed_at/state/raw`；state 是本次真实 editor state、场景／设置等规范化观测，raw 保存相应原始对象。要求晚于终态、匹配 restore_expected、编译／导入／测试／构建均停止。原始对象与规范化字段的对应由 Operator/Reviewer核对；这是离线记录，不能证明此后 Editor 永远空闲。失败构建也要恢复，但恢复 pass 不会覆盖 outcome fail。

## 仅凭文件续接

| inspect 动作 | 下一步 |
| --- | --- |
| claim_after_live_preflight | 重新发现目标工程、核对冻结输入及当前状态、登记 owner 后 claim |
| reconcile_input_drift | 保存差异，明确新候选及旧操作处置；不能复用旧构建验收 |
| reconcile_lost_receipt_do_not_resend | 查实际 Editor/job/日志和输出；找到匹配 job 才保存 receipt；无法证明则维持 unknown，记录阻塞 |
| poll_existing_job | 仅轮询返回的 job_id；断线重连先按完整工程重新发现，禁止触发新测试／构建 |
| verify_restoration | 核对终态和产物，读取当前 Editor 状态，履行恢复合同并保存 restore |
| closed_do_not_resend | 将 outcome 与 restoration分别写入 Verification；fail仍须修复／新候选，不能声称全部通过 |
| reconcile_do_not_resend／命令错误 | 保留原记录及错误；核对截断、未知 schema、身份或数据缺失后决定人工恢复 |

instance ID改变、job store丢失、发起回执不确定时，本版不提供一键重置或重试。保存旧 journal 和原始观测，在任务记录写首个阻塞、核对结论、实际无在途工作及新 attempt 的依据后才能计划新操作。journal 不会自动断言“没有 job 就从未构建”。

## 交接与检查

Handoff 至少链接 journal 相对目录、operation-id、最后动作、候选清单、原始响应及当前恢复缺口。Artifacts 被忽略，换机器前将实际 journal 作为独立证据归档并记录清单 SHA-256和可访问位置；B 的 List core 包不会自动收录它。缺记录时填写 unavailable，不能从会话摘要重建成功结果。

正式采样窗口不写 journal、不做额外 MCP 查询。只在运行前后登记；采样与性能判定仍由确定性 C# Runner及[性能证据规范](PERFORMANCE_EVIDENCE.md)负责。

回归命令：`python -B -m unittest discover -s Tools/UnityOperations -p 'test_*.py' -v`。受控 fixture通过不等于真实 Editor/Player通过。
