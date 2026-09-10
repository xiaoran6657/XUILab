# 首版公开候选独立审查

- candidate: public-source-r1
- brief_revision: r1
- verdict: changes_requested

Reviewer public_content_audit独立只读审查efb386cc80aee1e8948e7a0a73d578a13aaf06a2与最终r2附件。源码工具、远端CI、附件与许可检查通过；阻塞为Unity模板Layout.wlt保留预置作者目录，要求移除或脱敏。另要求更新PUBLICATION过期状态、对最终HEAD重新扫描、说明包内RUNNING.txt的历史快照措辞。

Windows r2 ZIP全部275个r4既有条目一致，PUBLIC_PACKAGE.json对277个非自身文件逐项验hash通过。List回归71项/1可选skip通过；Unity新实跑及完整原receipt复核仍not_run。此报告不能作为首版公开放行，整改候选另行独立复核。
