# INFRA-006 失败与恢复

## 首次完整离线检查

public-local-r1使用系统Python3.14.3；PM/验收映射、ProjectManagement、ListLab、UnityOperations、Archiving、Automation均通过，ListLab一项可选真实证据集成跳过。GradientLab的109项测试出现12 failures、19 errors，根因为缺少NumPy；启动安全测试在预派发依赖检查就被拒绝，尚未进入模拟Popen。

原始终态保留在Artifacts/offline-checks/public-local-r1/result.json，overall status=failed，不覆盖。本次发现原CI未安装后来Gradient质量验证新增的依赖，旧“全套仅标准库”说明已过时。

修复：Tools/requirements-ci.txt固定numpy2.3.5，CI先安装再执行；Docs说明区分标准库调度器与完整测试依赖。无全局安装、不修改Runtime或原始实验结果。恢复验证使用新run-id并记录实际Python/NumPy版本。

## 第二次完整离线检查

public-local-r2使用Python3.12.14/NumPy2.3.5；GradientLab恢复通过，但ListLab有15 errors，首因Path.read_text(newline=...)在Python3.11/3.12不存在。原说明最低3.11与实际API不一致。修复为Path.open(newline="")上下文读取，保持不转换换行的语义；现有ListLab测试覆盖正常证据、篡改与搬迁。新工具SHA与历史冻结版本区分，Runtime未改。

## Git换行转换检查

准备提交后逐字节比较发现，根规则会将部分证据JSON的CRLF转换为LF，导致公开clone中的manifest与记录SHA不同。修复为仅对Docs/Showcase/Data/*.json和PUBLISHING_INPUTS.json保留原字节；其他项目文本继续LF规范。原始数据、清单与哈希均未重写，Git中重新记录原字节，并在发布副本再次比对。该修复不涉及Unity源文件。

## 首次私有CI

[34460245242](https://github.com/xiaoran6657/XUILab/actions/runs/34460245242)在acc4f72上failure，jobs为空，CLI提示workflow file issue。核对发现pip的--only-binary=:all:后冒号加空格位于YAML未引用标量中，导致工作流解析失败。改为折叠块标量保留命令原样；新提交重新触发，原失败保留。

## Windows短路径身份

[34460749088](https://github.com/xiaoran6657/XUILab/actions/runs/34460749088)在fb1809b上实际执行Python3.11.9，List 70测试出现5 failures/3 errors，其他6个命令通过。构建清单路径只有abspath，Player路径使用resolve，Windows 8.3别名导致同一文件不匹配。新增真实GetShortPathNameW回归，本机修复前复现同样ResumeError。修复统一现存pinned文件的解析身份，解析前后仍检查reparse；并拒绝同一文件不同别名绑定冲突哈希。源码工具有变化，旧Unity样本未重跑。

## Windows包许可文本补充

发布前发现r4附有MCP package.json的licensesUrl但未附实际MIT正文，同时包含MCPForUnity.Runtime.dll。公开派生包只增加锁定acf5e3dd3b864c140862e0c6644ff9e8f2120a64的原MIT文本、项目MIT和PUBLIC_PACKAGE.json。上游Git blob e7f878d1da6b4d9488058157ce6b48cb584460b1已按下载内容复算；MIT文本SHA256 6efe650c965012ac418238dcd6b9116e4130a5220717ef0dfb539dd159c4245c。原r4全部275条目保持字节一致，不改二进制、不新建Unity构建。新公开ZIP SHA256 ddc5e44c72ceb710563b62465eb6d1e1024af0e8d3a7d6eb4a2180fc43dbb818；旧草稿附件在仓库私有期间替换，旧本地文件保留。

## 独立审查的模板目录整改

首版独立审查changes_requested：Unity模板Layout.wlt的m_LastProjectPath保留作者目录。二版通过全新隔离克隆，在全部历史中只替换该字符串；meta/GUID不变。该字段仅由TutorialInfo/Scripts/Editor/ReadmeEditor.cs载入编辑器布局，不参与Player逻辑。本地原工程与二进制均不改，公开295项Unity输入的对照更新为294项Git一致/1项布局路径脱敏；与原测量工作区262字节一致/32换行/1布局变化。后续扫描绑定二版最终HEAD，不沿用旧b822f07扫描结论。
