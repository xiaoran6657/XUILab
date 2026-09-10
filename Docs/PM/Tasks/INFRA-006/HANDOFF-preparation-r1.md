# 公开准备交接

当前开发分支codex/public-delivery，基线811a357，准备增量包含MIT/第三方声明、主页资料、12张图、两份完整报告、历史源清单、1230文件原始数据的公开manifest，以及公开导出/验证工具。尚未推送源码；目标远端已实际创建为PRIVATE。

完整离线public-local-r3通过：PM/验收映射与六组工具测试共247项，其中List一项可选真实证据集成跳过。前两次失败及修复见[失败记录](FAILURES-r1.md)。新Publishing工具19项测试通过；独立工具首轮审查要求加强外部manifest与build/case绑定，已落实并新增反例测试，最终复核待返回。

18文件资料包manifest SHA256 8304f96ede32b5145df30af19352d6057fc4a6fbaacbbb8a8de3cb116262cdb9。130-run/1230文件公开数据r3 manifest SHA256 559ce56773e35a96aa464ca8db845831dfd90b610d18fa10717c1939c5fd394f，独立副本位于Docs/Showcase/Data/public-evidence-manifest.json。原始receipt文件SHA逐项核对，p50/p95/p99逐帧复算通过；config仅脱敏输出目录。记录绑定于Artifacts/publication-validation-r1/public-tools-r2.json。

295项Unity输入与历史m4-final-b017672清单逐字节一致。仅发布工具、离线兼容修复、测试夹具和文档变化，不把这些改动算成新的Unity采样。Unity测试/构建/采样本轮not_run；原性能结果保持历史身份。

12张PNG无tEXt/iTXt/zTXt/eXIf附加块；3段MP4元数据仅见ffmpeg/libx264编码器，无作者/位置/创建时间字段。原Release r4包仍待最终发布附件复核。

下一步：分组保存本地准备增量，在隔离发布副本中净化全部历史、修复公开链接与最小PM，再冻结候选独立审查、推送私有远端并核对实际CI，最后公开。原本地Refs/PM/Artifacts保持不动。
