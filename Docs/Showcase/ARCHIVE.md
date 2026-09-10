# 本地归档与恢复

完整本地快照使用项目现有[源码归档工具](../Agents/SOURCE_ARCHIVE.md)，位置为`Artifacts/m4-local-archive-r1/`。它是用于保存/审查的目录副本，不是第二个活动Unity工程。实际归档文件数、index SHA256和检查终态以[归档回执（历史记录未公开）](HISTORICAL_RECORDS.md)为准；仅目录存在不等于成功。

归档保留源码工作树、全部最终运行、失败尝试、原始构建、展示包、图片/视频原帧、测试与构建journal以及生成脚本。source/记录实际HEAD与dirty状态；391项被测输入仍指向干净提交b017672，后来的PM/Showcase文档没有冒充提交内源码。

## 搬迁检查

复制整个归档后，用Python>=3.11运行归档中的工具，并传入从可信交接获取的index SHA：

```powershell
python -B <archive>/source/Tools/Archiving/source_archive.py check --archive <archive> --expected-index-sha256 <index-sha256>
```

命令是模板，替换尖括号内容。检查不依赖原仓库；不能只相信同目录内可被一起替换的index。源码、每个extra的所有文件必须与清单一致，工具拒绝缺失/改动/额外文件和junction等reparse point。

恢复到新工作区时，将source/内容放回仓库根；按[恢复映射（历史记录未公开）](HISTORICAL_RECORDS.md)把extra放回对应Artifacts相对路径。只打开恢复后的XUILab/。原receipt保留原机器路径，不重写成新路径来假装当时在那里运行；历史核对遵循[复跑说明](REPLAY.md)，新运行使用新的身份和目录。

本地归档含原日志、路径和可能涉及个人/公司的Docs/References背景资料，只供本地保留，**不能直接上传公开**。可运行展示包单独见[RUNNING](RUNNING.md)；公开许可与实际发布状态见[公开交付记录](PUBLICATION.md)。Unity安装、Library包缓存、Python/Node本机依赖、ffmpeg可执行文件不作为源码工具重新分发；运行时版本与来源清单保留。

归档中PM是归档时点快照；最终收尾文档如晚于该快照，会由单独`m4-final-docs-r2.zip`和manifest记录。源码候选与最终运行数据不因文档后补而改变。
