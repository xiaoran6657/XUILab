# Verification — <Task-ID> — <rN>

- candidate: <候选 ID>
- brief_revision: r1
- Validator／实际操作者／Implementer：
- 请求配置／实际可观察配置：
- Brief 修订／candidate-id／build-id／run-id：
- execution_independence：<independent / shared-operator / self-check / not_run；说明>
- 源码／构建／配置身份核对：
- 环境、Unity 工程根与版本：

## 实际检查

| 检查或命令 | job-id／模式 | 终态 | 通过／失败／跳过数量 | 证据 |
| --- | --- | --- | --- | --- |
| <实际执行> | <上下文> | <pass/fail/not_run/not_applicable> | <未知不填 0> | <日志／结果路径> |

- Unity 前后状态、场景、Console 已有与新增错误：
- 视觉观察及对应状态／图片：
- 异步任务是否真正结束：
- operation-id／原始 receipt、terminal、restore／journal 归档身份：
- 静态验收 ID → 本次 Brief ID → 本候选证据：
- 未执行项与原因：

## 性能任务附加检查

- 采样协议、A/B 输入、不变量、实际指标能力：
- 预热／采样／重复数与异常规则是否符合：
- 原始样本、统计方法、轮间波动和产物哈希：
- correctness：<pass/fail/not_run>
- measurement_validity：<valid/invalid/not_assessed；原因>
- performance_comparison：<improved/regressed/no_clear_difference/inconclusive；依据>
- 诊断采集、媒体与正式测量是否分开：

非性能任务将本节标为不适用并说明，不生成虚构指标。

## 结论与恢复

- 已支持的验收项／不能支持的结论：
- 首个失败与下一步：
- 未结束进程、产物归档、Unity 占用释放情况：

进程启动、工具 success、截图存在都不是测试终态；required 检查未运行时，不输出全部通过。
