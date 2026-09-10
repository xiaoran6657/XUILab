# 来源、贡献与分发边界

本页对应源码候选 m4-final-b017672（提交 b0176724d58c7cda86b472340845d239714888d0）。第三方身份依据实际 [manifest](../../XUILab/Packages/manifest.json)、[lock](../../XUILab/Packages/packages-lock.json) 和已解析包文件核对。当前交付用于本地保存与评审；没有执行公开发布。

## 项目工作

| 内容 | 来源与边界 | 实现入口 |
| --- | --- | --- |
| 固定行高列表、Cell池、Wrapper、索引刷新 | 在Unity UGUI上独立实现；未导入LoopScrollRect，未复制参考材料中的公司Runtime源码。结果仅对本项目合同负责 | [List合同](../Experiments/LIST_CONTRACT.md)、[ListLab](../../XUILab/Assets/XUILab/ListLab/) |
| 参数化渐变、固定/自适应细分 | 本项目实现曲线语义、网格修改、误差与成本实验；不把Unity UGUI/渲染管线算作个人实现 | [GradientLab](../../XUILab/Assets/XUILab/GradientLab/)、[渐变学习入口](../Learn/GRADIENT_SUBDIVISION.md) |
| 确定性Runner、操作journal、恢复/校验/统计工具 | 项目自动化实现；Agent参与编写与审查，用户个人理解进度仍独立记录 | [工具入口](../Agents/REPRODUCIBILITY_PLAYBOOK.md)、[证据规范](../Agents/PERFORMANCE_EVIDENCE.md) |
| 展示图形、列表内容、渐变色 | 由项目代码生成；展示文字使用Unity内置LegacyRuntime.ttf。字体不声明为项目原创，也不作为独立字体文件分发 | [ListLabFactory](../../XUILab/Assets/XUILab/ListLab/Runtime/ListLabFactory.cs)、[GradientLabFactory](../../XUILab/Assets/XUILab/GradientLab/Presentation/GradientLabFactory.cs) |
| 教程URP图标 | Unity项目模板中的Assets/TutorialInfo/Icons/URP.png；不是项目原创展示素材 | [原文件](../../XUILab/Assets/TutorialInfo/Icons/URP.png) |

## 实际依赖

UGUI 1.0.0、URP 14.0.11、TextMesh Pro 3.0.9的已解析包均包含LICENSE.md，文件声明Unity Companion License。完整依赖版本及传递依赖以lock为准；本页不把它们重新许可为项目原创代码。实际解析包的90份package.json及现有许可/NOTICE文件已按原字节保存到[来源清单](../../Artifacts/m4-final-validation/dependency-notices-r1/manifest.json)，每项附SHA-256；重新获取包也应保留其原声明。

MCP for Unity已解析package.json版本为10.2.1-beta.3；manifest使用beta引用，但lock固定解析提交acf5e3dd3b864c140862e0c6644ff9e8f2120a64。该工具服务Editor操作，来源为 [CoplayDev/unity-mcp](https://github.com/CoplayDev/unity-mcp)，许可入口由实际package.json的licensesUrl提供。最终源码不打包Library/PackageCache替代依赖获取；不要把可移动beta名字当作已固定的身份。

2026-09-10用户同意公开方案后，新增根目录[MIT许可](../../LICENSE)，适用于有权授权的原创部分。第三方范围见[许可与第三方声明](THIRD_PARTY_NOTICES.md)，原依赖条款保持不变。

## 研究材料与公开文案

[Docs/References](../References/README.md)包含历史材料，仅是研究输入。它们不进入展示Player、媒体或公开文案素材；公司源码、历史简历数字、个人路径不得被包装为本项目已验证成果。案例只描述问题类别、XUILab中的实际实现和当前候选实测数据，不代用户声称已理解或亲自独立完成所有代码。

完整私有运行日志可能包含用户名、机器名、内网IP和绝对目录，保留在原始证据中用于本地复核；不会随展示用图表/视频直接发布。展示索引引用经过明确标识的本地原始证据。将来公开资料需要另行执行脱敏与发布检查，而不是修改原始数据的字节和哈希。

Windows Release展示包与Development测量构建分开：Release目录实际未发现Roslyn/CodeAnalysis、PDB或MDB文件；正式性能数字只来源于Development矩阵。第三方来源说明、技术完成和个人学习复盘分别记录，不用许可证文件的存在替代完整验收。
