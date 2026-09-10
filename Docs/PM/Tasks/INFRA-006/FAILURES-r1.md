# INFRA-006 失败与恢复

## 首次完整离线检查

public-local-r1使用系统Python3.14.3；PM/验收映射、ProjectManagement、ListLab、UnityOperations、Archiving、Automation均通过，ListLab一项可选真实证据集成跳过。GradientLab的109项测试出现12 failures、19 errors，根因为缺少NumPy；启动安全测试在预派发依赖检查就被拒绝，尚未进入模拟Popen。

原始终态保留在Artifacts/offline-checks/public-local-r1/result.json，overall status=failed，不覆盖。本次发现原CI未安装后来Gradient质量验证新增的依赖，旧“全套仅标准库”说明已过时。

修复：Tools/requirements-ci.txt固定numpy2.3.5，CI先安装再执行；Docs说明区分标准库调度器与完整测试依赖。无全局安装、不修改Runtime或原始实验结果。恢复验证使用新run-id并记录实际Python/NumPy版本。

## 第二次完整离线检查

public-local-r2使用Python3.12.14/NumPy2.3.5；GradientLab恢复通过，但ListLab有15 errors，首因Path.read_text(newline=...)在Python3.11/3.12不存在。原说明最低3.11与实际API不一致。修复为Path.open(newline="")上下文读取，保持不转换换行的语义；现有ListLab测试覆盖正常证据、篡改与搬迁。新工具SHA与历史冻结版本区分，Runtime未改。

## Git换行转换检查

准备提交后逐字节比较发现，根规则会将部分证据JSON的CRLF转换为LF，导致公开clone中的manifest与记录SHA不同。修复为仅对Docs/Showcase/Data/*.json和PUBLISHING_INPUTS.json保留原字节；其他项目文本继续LF规范。原始数据、清单与哈希均未重写，Git中重新记录原字节，并在发布副本再次比对。该修复不涉及Unity源文件。
