# Task Brief — <Task-ID>

> 模板；填写后存入 `Docs/PM/Tasks/<Task-ID>/TASK_BRIEF.md`。删除无关提示，不能把占位符当事实。

- brief_revision: r1
- task_type: <mvp 或 infra>
- risk: <R0/R1/R2/R3>
- review_required: <true 或 false；R2/R3 必须 true>
- execution_required: <true 或 false>
- 任务范围依据：<MVP 阶段或 INFRA 授权目标；依赖状态在 TASK_STATUS 唯一维护>
- 用户授权依据：<请求范围；已有授权即可，不人为增加审批>
- 风险理由：<解释顶部 risk 的依据；不再填写第二个等级>
- 流程状态入口：<同目录 TASK_STATUS.md；此处不复制状态>

## 目标与范围

- 问题／预期行为：
- 已有成果与本次剩余工作：
- 本次不包含：
- 允许修改的功能目录与操作类型：
- 禁止修改／需保留的用户改动：
- 必要衍生文件：<同范围 .meta、测试、生成证据；不是无限扩展授权>

## 工程合同

- 输入、输出、核心不变量、失败行为：
- Runtime／Editor／Test 程序集及直接依赖：<不涉及填 not applicable + 理由>
- 场景／Prefab／资源及归属：
- 公共接口／序列化兼容影响：
- 实现来源与第三方依赖：

## 验收矩阵

| ID | requirement | 判据 |
| --- | --- | --- |
| <A1 等唯一 ID> | <required 或 not_applicable> | <目标、方法、成功判据、预期证据；不适用写理由> |

- 性能实验协议：<链接；变量、不变量、指标能力、统计及有效性规则>
- 是否要求独立审查／独立执行：<分别填写；按风险决定>
- 用户学习复盘目标：<如适用；与技术完成分开记录>

## 路线图验收映射

新 v1 MVP 任务按[静态映射](../../MVP/ACCEPTANCE_MAP.md)填写本任务所有 acceptanceIds，绑定到上方 required ID；INFRA 填 not_applicable，不伪造 MVP 映射。

| acceptance_id | brief_id |
| --- | --- |
| <稳定条款 ID> | <本次 required ID> |

## 分工与执行条件

- 主 Agent／Implementer／Reviewer／Validator：<实际身份或待分派>
- 委派依据：<用户或适用指令；无授权不自动创建>
- 请求模型／推理配置：<默认继承或明确请求>
- Unity Operator 与占用登记入口：
- 测试场景、构建输出和状态恢复约定：
- 停止条件／外部依赖／可继续工作：

## 基线与修订

- 开始时 commit／dirty／未跟踪文件及清单：
- 基线哈希与环境记录：
- 合同修订历史：<修订、原因、授权关联；不得事后弱化验收掩盖失败>
