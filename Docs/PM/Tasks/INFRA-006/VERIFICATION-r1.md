# 公开交付验证

- candidate: public-source-r2
- brief_revision: r1

验证者root；执行独立性self-check。最终源码审查由独立Reviewer另行登记，本文件不冒充独立实跑。

## 源码与远端CI

首版冻结候选efb386cc80aee1e8948e7a0a73d578a13aaf06a2。私有远端[CI 34463455743](https://github.com/xiaoran6657/XUILab/actions/runs/34463455743)已success；依赖安装、离线计划、Publishing测试及15项tracked素材/report核对均通过。功能工具前序19f7c72的[CI 34461682531](https://github.com/xiaoran6657/XUILab/actions/runs/34461682531)也通过，共265项测试，3项因无私有完整证据而skip。efb386c只补许可与发布说明，没有代码变更。

实际从GitHub新克隆19f7c72，Python3.12.14/NumPy2.3.5执行7命令计划passed（246测试、3skip），15项tracked素材核对passed。二版整改后294项Unity Git输入与原提交一致，1项模板编辑器布局仅脱敏预置目录；对比原实测文件262项字节一致、32项仅换行、1项模板布局路径变化，逐文件双SHA见[源码对应](../../../Showcase/PUBLIC_SOURCE.md)。没有在公开候选新跑Unity测试/构建/Player/性能。

两次远端失败及恢复没有删除，见[失败记录](FAILURES-r1.md)。成功结论不覆盖那些失败候选。

## 附件

最终Windows ZIP SHA256 ddc5e44c72ceb710563b62465eb6d1e1024af0e8d3a7d6eb4a2180fc43dbb818。相较r4基础包，275个既有条目全部字节一致，仅添加项目MIT、锁定MCP MIT与PUBLIC_PACKAGE.json；无二进制变化，无新构建。

素材ZIP与数据ZIP解压到新目录后，按公开REPLAY命令分别通过18文件校验与1230文件/130run逐帧统计复算，外部manifest SHA匹配。数据包不包含完整原receipt和日志，未声称完成该原始范围的验证。

GitHub草稿Release的7个附件名、大小、服务器digest与最终本地文件逐项一致；当时draft=true、仓库PRIVATE，target=efb386c。附件及SHA见[发布记录](../../../Showcase/PUBLICATION.md)。最终发布后的匿名访问与下载核对待完成。

二版历史整改：全部待推送历史清理模板布局中的预置作者目录；最终扫描与CI需绑定二版新SHA。首版独立审查记录见[REVIEW-r1](REVIEW-r1.md)。

## 二版冻结与放行前终态

最终版本冻结为231c8161175c7edd8debfe7b75ac7aa6f4a9f020；[CI34464845765](https://github.com/xiaoran6657/XUILab/actions/runs/34464845765)实际success。该SHA的911可达对象/663 blob重新扫描，UTF8/UTF16LE私人标识、模板作者及凭据模式无命中；中性说明和当前INFRA006以外的原内部PM/References历史均排除。882个当前Markdown本地目标存在；此检查不包括锚点及远端访问。

独立复核[REVIEW-r2](REVIEW-r2.md)明确accept。私有草稿Release ID386159265，target=231c816，7附件名称/大小/服务器SHA与最终r2包一致。此前的efb386c CI与扫描只作首版历史，不能代替本节二版终态。版本tag固定该审查源码与资料快照，随后只补交付记录；公开访问仍须另记实际结果。
