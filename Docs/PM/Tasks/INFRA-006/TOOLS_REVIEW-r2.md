# 发布工具独立复核

- candidate: public-tools-r2
- brief_revision: r1
- verdict: accept

Reviewer public_content_audit对四个冻结Python文件复核。请求配置GPT-5.6 Luna/max，实际服务端模型unknown；共享文件系统，只读审查。19项针对性测试已通过；不是独立Unity执行。

复核接受外部expected-manifest-sha256、报告顶层buildId与逐行caseId匹配、元数据预扫描，以及新增反例覆盖。12PNG无文本/EXIF块、3视频仅编码器元数据的诊断另行核对。资料manifest与公开数据manifest绑定在Artifacts/publication-validation-r1/public-tools-r2.json；公开数据外部副本为Docs/Showcase/Data/public-evidence-manifest.json，SHA559ce56773e35a96aa464ca8db845831dfd90b610d18fa10717c1939c5fd394f。

边界：内部一致性不能独立证明原始测量真实性；发布流程必须保存独立清单SHA并核对最终文件。此accept仅覆盖导出工具r2，不代替最终净化仓库、附件和公开操作审查。后补的Git换行例外和tracked素材CI检查需要最终候选核对。
