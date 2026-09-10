# 公开交付记录

2026-09-10已公开仓库与v0.1.0-preview.1预览Release；[24项匿名访问和文件核对](Data/public-access-verification.json)通过。

本版本源码位于[xiaoran6657/XUILab](https://github.com/xiaoran6657/XUILab)，版本附件入口如下。当前下载可用状态以[GitHub Release](https://github.com/xiaoran6657/XUILab/releases/tag/v0.1.0-preview.1)页面为准。

发布前冻结提交为`231c8161175c7edd8debfe7b75ac7aa6f4a9f020`，已完成[对应CI](https://github.com/xiaoran6657/XUILab/actions/runs/34464845765)、远端克隆检查、公开ZIP解压复算、草稿附件hash核对及[独立复核](../PM/Tasks/INFRA-006/REVIEW-r2.md)。版本tag保留冻结的源码和资料快照；公开后的访问验收在main的[交付验证](../PM/Tasks/INFRA-006/VERIFICATION-r1.md)补记。

v0.1.0-preview.1为技术预览，M4个人学习复盘仍待完成。[源码对应](PUBLIC_SOURCE.md)、[主页交接](WEBSITE_HANDOFF.md)、[许可边界](THIRD_PARTY_NOTICES.md)。

| 附件 | 字节 | SHA-256 |
| --- | ---: | --- |
| [agent.mp4](https://github.com/xiaoran6657/XUILab/releases/download/v0.1.0-preview.1/agent.mp4) | 414794 | `e70e4ff084b0ad534892bf71f5f541a17072bb00ade6928b7b1fb2da3b9b4a60` |
| [gradient.mp4](https://github.com/xiaoran6657/XUILab/releases/download/v0.1.0-preview.1/gradient.mp4) | 501212 | `e6bcb69035b8c29882e285c484138b8163c025545b7525579c98332a18d2fdd0` |
| [list.mp4](https://github.com/xiaoran6657/XUILab/releases/download/v0.1.0-preview.1/list.mp4) | 3527638 | `40013b4390a225c1f8c489ff55cd237208f1f9c86ae220bc65a14444aee268f4` |
| [XUILab-evidence-v0.1.0-preview.1.zip](https://github.com/xiaoran6657/XUILab/releases/download/v0.1.0-preview.1/XUILab-evidence-v0.1.0-preview.1.zip) | 37253431 | `8cac30c276e142d42871ea86e6b7ddfa02ec0e33f9ab4bcb7110523e79098ba7` |
| [XUILab-showcase-v0.1.0-preview.1.zip](https://github.com/xiaoran6657/XUILab/releases/download/v0.1.0-preview.1/XUILab-showcase-v0.1.0-preview.1.zip) | 5988987 | `1418fff477c40ba8bd6973a9ead906d3993b6906850442725583e69b163e3d78` |
| [XUILab-Windows-x64-v0.1.0-preview.1.zip](https://github.com/xiaoran6657/XUILab/releases/download/v0.1.0-preview.1/XUILab-Windows-x64-v0.1.0-preview.1.zip) | 32677629 | `ddc5e44c72ceb710563b62465eb6d1e1024af0e8d3a7d6eb4a2180fc43dbb818` |

[SHA256SUMS.txt](https://github.com/xiaoran6657/XUILab/releases/download/v0.1.0-preview.1/SHA256SUMS.txt)。素材包manifest SHA-256：`8304f96ede32b5145df30af19352d6057fc4a6fbaacbbb8a8de3cb116262cdb9`；数据包manifest SHA-256：`559ce56773e35a96aa464ca8db845831dfd90b610d18fa10717c1939c5fd394f`。

素材manifest和输入计划的prepared-not-published是创建时快照，不代表当前访问状态；保持原字节以便验证。三视频均为45秒帧驱动演示，不是实时性能录像。离线CI不执行Unity构建、Player或性能采样。
