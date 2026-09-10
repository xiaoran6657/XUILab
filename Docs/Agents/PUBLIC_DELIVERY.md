# 公开交付与私有原件

公开资料入口为[Showcase](../Showcase/PROFILE.md)，网站项目按[主页交接](../Showcase/WEBSITE_HANDOFF.md)取用。当前开发仓库和完整本地归档不能直接镜像推送至公开仓库。

## 导出合同

展示文件由[固定输入清单](../Showcase/PUBLISHING_INPUTS.json)选择，导出工具先校验来源哈希与路径，再复制到新目录；不会上传或覆盖既有输出。只生成公开数据时遵循[数据包说明](../Showcase/PUBLIC_DATA.md)。

```powershell
python -B Tools/Publishing/public_assets.py export --root . --plan Docs/Showcase/PUBLISHING_INPUTS.json --output Artifacts/public-showcase-new
python -B Tools/Publishing/public_assets.py verify --root Artifacts/public-showcase-new --expected-manifest-sha256 <可信清单SHA256>
python -B Tools/Publishing/public_evidence.py export --root . --output Artifacts/public-evidence-new
python -B Tools/Publishing/public_evidence.py verify --root Artifacts/public-evidence-new --expected-manifest-sha256 <可信清单SHA256>
```

export需要本地完整原始输入，普通公开clone只包含小型图与报告，不能凭缺失输入重新生成全部证据。verify用于已下载公开包。固定输入变更须重新审查，不自动更新哈希以接受漂移。

## 历史与发布副本

历史净化仅在隔离副本执行；所有历史排除References、原PROJECT_ANALYSIS和内部PM，tip另建中性说明及最小状态。真实机器路径与作者私人身份脱敏，分组提交顺序尽量保留。旧SHA与新SHA不同；原始性能数据保持旧candidate/sourceRevision，公开映射逐文件说明哪些Unity输入相同、哪些工具/文档有变更。

公开副本只推送经过检查的main及明确版本tag；不能推送原开发仓库全部refs或把私有备份重新合并进公开历史。后续公开开发应从公开main检出，私有材料单独保留。历史净化、链接修复、源码比对和独立审查均是实际步骤，工具安装或clone成功不代表公开审核通过。

先以私有仓库完成CI实际运行，再核对版本附件、校验清单和隐私/许可审查，最后公开。网站另项目部署；本任务不会创建github.io仓库。
