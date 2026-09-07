# 显式离线检查调度

Tools/Automation/run_checks.py 提供一个需要人工启动的一次性入口。它把固定的离线检查写成
可审阅的计划，逐项执行后保存状态和终态记录；它不是常驻服务，不会自动重试，也不会启动
Unity Editor、Unity Player 或网络客户端。

## 依赖与范围

需要 Python 3.11 或更高版本，只使用 Python 标准库。允许的检查集合固定为：

check_offline、ProjectManagement、ListLab、UnityOperations、GradientLab、Archiving、Automation。

check_offline 调用 Tools/check_offline.py。其余项目按固定目录调用：

    python -B -m unittest discover -s Tools/<目录> -p test_*.py

命令由调度器生成，没有接受任意 shell 命令的参数，并以参数数组和 shell=False 执行。

## 命令

以下命令从仓库根运行。省略 --root 时由脚本位置推导仓库根；需要复现另一份检出时显式
传入该检出根目录。

    python -B Tools/Automation/run_checks.py plan
    python -B Tools/Automation/run_checks.py plan --checks check_offline ProjectManagement --timeout-seconds 120
    python -B Tools/Automation/run_checks.py run --run-id offline-20260907-a --timeout-seconds 300
    python -B Tools/Automation/run_checks.py inspect --run-id offline-20260907-a

run 必须显式提供一个新的 --run-id。重复 ID 会在执行前拒绝，避免不确定的重发；每次运行在
Artifacts/offline-checks/<run-id>/ 独占创建 plan.json、state.json 和 result.json。Artifacts/
产物按仓库规则忽略，交接时应记录 run-id 和这些文件的哈希。

result.json 中每个命令都有固定参数、开始／结束时间、退出码、状态及有限长度的标准输出。
退出码为零的命令状态是 passed；非零是 failed；超时是 timeout，整体均为失败。计划阶段会拒绝没有 test_*.py 文件的选定测试目录，避免 unittest 的 Ran 0 tests 被误报为通过。
inspect 会重新校验 plan.json、state.json 和 result.json 的固定 schema，重算并比对
plan_sha256，核对固定检查白名单生成的命令身份，并交叉检查终态、命令状态／退出码、
时间戳和日志字段。只修改 state 与 result 的状态，或修改计划命令后同时修改结果，都会
进入 invalid；这能发现双文件的误通过编辑。记录是结构化诊断而不是密码学签名，不能证明
操作者无法伪造全部一致的 JSON。旧版记录或由不同 Python 可执行文件生成的记录，若不再
满足当前 schema／命令身份，会被拒绝为终态；应人工核对并保留原记录，不迁移或改写旧证据。
调度器会继续
收集计划中的后续命令，但不会重试超时或非零命令。

如果进程在终态写入前被终止，目录可能保留 state.status=running；如果由中断处理，状态为
interrupted。此时 inspect 返回 status=needs_review，要求人工确认子进程、日志和工作区后
决定下一步，不把它当作通过，也不自动重发。

## CI

最小托管入口是 [.github/workflows/offline.yml](../../.github/workflows/offline.yml)。它在
Windows/Python 3.11 上运行相同的离线入口和六个工具目录的测试，不启动 Unity，也不上传产物。
隔离单元测试已验证调度器的计划、模拟成功、重复 ID、非零退出、超时和中断检查；本说明不宣称托管 CI
已在远端实际运行。GitHub Actions 的 bootstrap 仍需要访问 GitHub 获取官方 action；相关
来源为 [actions/checkout](https://github.com/actions/checkout) 与
[actions/setup-python](https://github.com/actions/setup-python)。

需要续接已授权的 XUILab 任务时沿用现有
[xuilab-task-resume](../../.agents/skills/xuilab-task-resume/SKILL.md) 技能；本入口不创建
后台任务，也不扩大 MVP 或 Unity 操作授权。
