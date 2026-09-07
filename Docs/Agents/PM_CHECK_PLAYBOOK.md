# PM 离线结构检查

用于维护启动入口和 `xuilab.pm/v1` 任务记录。规范字段以 [PM 合同](PM_CONTRACT.md)为准。脚本只读文件、输出诊断，不修改 PM、不启动 Unity、不运行 Benchmark、不自动批准任务。

## 运行

在仓库根使用 Python 3.10 或更高版本；仅需标准库，不安装依赖。命令中的 `python` 应解析到实际可用的解释器。

```powershell
python -B Tools/ProjectManagement/check_pm.py
python -B -m unittest discover -s Tools/ProjectManagement -p 'test_*.py' -v
```

检查器也接受 `--root <仓库路径>`，默认从自身位置定位仓库。它将结果写到 stdout，结构错误返回 exit 1，通过返回 exit 0。测试使用一次性临时目录；不改真实任务记录。`-B` 避免产生 Python 字节码缓存。

## 检查范围

- 新任务字段、状态、类型、Brief 修订与验收 ID 对齐；required 结果、候选及报告声明的基本关联。
- 依赖存在、无自依赖／循环、执行阶段的前置任务已经 done；blocked 有问题与恢复条件。
- 全局 current/latest 指针、唯一 unity_owner/unity_task 配对；Next Actions 不含已完成／取消的任务或重复任务链接。
- 根入口、Docs/README、Agents（含模板）、MVP、全局 PM 和新格式任务 Markdown 的本地链接目标存在。忽略 fenced code、占位符、外部链接与锚点验证；不会请求网页或递归读取外部数据。

Artifacts 链接在本机可能不可用，缺失作为 warning 报告，不把没有恢复证据包当作文档损坏。普通文档／工具路径缺失是 error。此检查不保证 Markdown 的所有语法形式或锚点正确；新增复杂引用须人工核对。

## 历史兼容与结论边界

固定兼容八个旧任务：M0-01 至 M0-04、M1-01 至 M1-04。没有 schema 的旧任务会显示 legacy 覆盖提示，只解析其已有 state 前缀，不检验旧候选和完整验收。其他任务缺 schema 或使用未知 schema 都报错；不能通过删除 schema 绕过检查。

exit 0 只表示已覆盖结构一致。它不证明 Review 作者独立、required 证据充分、文件哈希正确、运行有效或性能改善；这些仍需实际证据和主 Agent 验收。文档自然语言中的过时叙述也需审查，检查器不会推断用户授权或替人更改状态。

## 收口顺序

先冻结实际文件并验证，再获得所需审查；更新任务状态 → 全局 current/latest → Next Actions。完成后再运行结构检查，保存实际命令、终态、失败与修复记录。检查失败时修复记录或实现，不能删除 required 条款来制造通过。

本工具仅覆盖 A 批 PM 合同；候选清单自动化、Benchmark 恢复与产物打包属于独立后续范围。

## 静态验收映射

统一离线入口同时运行[验收映射检查](../MVP/ACCEPTANCE_MAP.md)，可单独运行 `python -B Tools/ProjectManagement/check_acceptance.py`。新 v1 MVP Brief需绑定静态条款到本任务 required ID；历史记录不回填，INFRA不套用MVP条款。映射通过仅表示结构覆盖，不能推断实际验收。
