# Review — <Task-ID> — <rN>

- candidate: <候选 ID>
- brief_revision: r1
- verdict: <accept / changes_requested / not_reviewable>
- Reviewer／Implementer 身份：
- 请求配置／实际可观察配置：
- Brief 修订／candidate-id／实际文件身份：
- review_independence：<independent / self-check；理由>
- verdict 的理由：<具体接受范围或不接受原因；不另存第二个结论值>

## 审查范围

- 实际读取的合同、代码、资产、报告和原始数据：
- 候选是否匹配、是否存在审查期间写入：
- 目标、授权范围、公共接口与依赖：
- 对象所有权／生命周期、边界、失败处理：
- 适用的程序集、`.meta`、场景与序列化检查：
- 性能实验的公平性、指标语义和证据关联：<如适用>

## 发现

| ID／优先级 | 位置或证据 | 具体问题与影响 | 需要的修复或复查 |
| --- | --- | --- | --- |
| <问题 ID> | <路径／数据> | <可证实描述> | <验收关联> |

没有发现时明确写“在已审范围内未发现阻塞问题”，不要据此声称未运行测试通过。

## 限制与交接

- 无法审查／未验证的结论：
- 必须完成的验证：
- 可选改进：<不应把无关偏好升级为必做项>
- 结论对应的候选和边界：

Reviewer 不直接修改实现；需要修复时交回 Implementer 并重新关联候选。
