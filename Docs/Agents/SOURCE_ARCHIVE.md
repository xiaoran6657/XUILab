# 源码与本地证据归档

Tools/Archiving/source_archive.py 生成可搬迁的目录归档。它使用
git ls-files --cached --others --exclude-standard 枚举当前工作树，再应用固定的
安全排除规则。复制的是当前工作树字节，所以 dirty 候选不会被误标为某个历史提交。

归档中的 source/ 是源码副本和交接材料，不是第二个活动 Unity 工程根。Unity 操作、
导入、构建和测试始终只使用仓库内唯一的 XUILab/。

## 结构与检查

归档目录包含 index.json、source/ 和每个显式 extra 的目录。index.json 使用
xuilab.source.archive/v1，记录源码 head、dirty、文件数、字节数，并为 source/ 与
每个 extra 记录逐文件 SHA-256 和大小。

check 只读取归档目录及 index，不需要原始仓库。它拒绝缺失、改动、未索引的文件，
未声明目录，重复或大小写冲突的路径，符号链接、junction 和其他 Windows reparse
point。pack 只接受不存在的输出目录，不会把文件合并进已有归档；失败留下的目录
应视为诊断残留，换一个新路径重试。

## 固定源码排除

以下规则不依赖未来 .gitignore 的改动：

- Artifacts/、.git、.vs、.vscode、.idea，以及根级 Build/、Builds/、Temp/、
  Logs/、Recordings/、MemoryCaptures/；
- XUILab/Library/、Temp/、Obj/、Build/、Builds/、Logs/、UserSettings/、
  MemoryCaptures/、Recordings/、ExportedObj/；
- Unity 和 IDE 生成扩展名，例如 .sln、.csproj、.suo、.user、.pdb、.mdb、
  .opendb 和 .unityproj；
- 任意位置的 __pycache__/、.pyc、.pyo、.pyd；
- .env 和 .env.*（保留 .env.example），以及 *.local、*.secret。

仓库已有的 Docs/References/ 会包含在本地源码归档中，使归档可以完整离线检查。
这些参考材料可能包含公司、个人或第三方内容；本归档只供本机交接，不表示获得公开
再分发许可，也不构成公开发布。

显式 extra 不采用源码排除规则，但必须是普通目录，内部不能有任何 reparse point，
从而可以按字节保留既有证据、媒体和图表。

## 证据、媒体和图表

使用 --extra NAME=PATH 显式加入目录。名称是单个安全路径段。可复制的一行命令示例：

    python -B Tools/Archiving/source_archive.py pack --repo . --out Artifacts/infra-d-source-archive --extra core=Artifacts/infra-b-core-r1 --extra media=Artifacts/list-media --extra charts=Artifacts/list-analysis-r3

名称为 core（也接受 evidence、evidence-core、evidence_core）时，目录必须包含
bundle.json，并在复制前通过 Tools/ListLab/evidence_bundle.py 的
check_integrity。index 会保存 bundle 的 SHA-256 及 evidenceId、candidateId、buildId、
sourceRevision，并将其标为 historicalEvidenceBundle。

其他 extra（例如 media、charts）会标为 currentSnapshot，不继承 core 的
candidate、build 或 source 身份。图表必须由根 Agent 从已接受 core 重新生成并完成
XML、数据和视觉检查；文件哈希通过不能替代视觉检查。

可信交接记录应携带源码归档 index 的 SHA。移动归档后可用一行命令独立检查：

    python -B Tools/Archiving/source_archive.py check --archive Artifacts/infra-d-source-archive --expected-index-sha256 <source-archive-index-sha256>

工具不会创建 ZIP、上传、发布、启动 Unity 或创建 Git 提交。

## Dirty 候选与 Git 顺序

不能用 git archive HEAD 代替 dirty 工作树：HEAD 不包含未提交修改，普通 git diff
也不包含 untracked 文件。pack 在复制前冻结全部源码和 extra 的路径及 SHA-256；
复制结束后再次核对完整路径集合、每个文件哈希、Git HEAD/dirty 状态和 core 身份，
发现改动则不写完整 index。对删除的 tracked 文件也会明确失败，避免形成伪完整源码包。

先冻结归档 index 和源码哈希，完成独立审查，再由根 Agent 统一执行获授权的本地
Git 归档。最终干净重建和测试只在提交后的唯一 XUILab/中执行，并生成新的构建和
操作身份。旧 dirty 构建、core bundle 和历史运行保留原身份。

归档是字节完整性和交接记录，不是签名。接收者仍应核对提交身份、构建日志、Unity
版本、Packages manifest/lock 和 PM 任务记录。
