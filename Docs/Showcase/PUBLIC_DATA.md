# 公开数据与复算

本页描述历史数据的公开派生包，下载状态及附件哈希见[公开交付记录](PUBLICATION.md)。它不表示新提交已重新采样。

## 包内范围

130次有效运行：List 50、Gradient 80。每次含config、environment、identity、samples、summary以及主题指标/采样CSV；渐变还含质量与网格数据。共1230个数据文件，另有manifest。原始Player日志、进程/启动回执、完整构建和私人参考材料不分发。

导出前，每个原文件与原成功运行receipt的SHA-256核对。除config外保持原字节；config仅把outputDirectory改为“[local output directory omitted]”并重新序列化JSON。manifest分别保存originalSha256、导出sha256、变换说明与原receipt哈希，identity.configSha256仍指向原配置，不能把它当作脱敏配置哈希。

## run-files

解压后按 `runs/<run-id>/` 找到数据；[RUN_INDEX](RUN_INDEX.md)给出130个run-id和结果。不要将脱敏目录交给要求原始路径/receipt的完整历史校验器，然后把预期失败当作新实验失败。

在公开仓库根运行：

```powershell
python -B Tools/Publishing/public_evidence.py verify --root <解压后的数据包目录> --expected-manifest-sha256 <发布记录中的清单SHA256>
```

必须从版本发布记录取得独立保存的manifest SHA-256，不能从待检查包中重新计算一个值后当成可信输入。该命令校验文件集合/哈希、run身份、原配置哈希映射、成功终态、1800帧及样本顺序，并从逐帧CSV复算p50/p95/p99，与summary和原报告逐项比对。拒绝缺样本、非有限值、错误身份和篡改数据。它不启动Unity，不代替完整receipt或连续质量复核，也不能证明原始采样环境未受其他程序干扰。

## 统计与适用范围

每次300帧预热、1800帧测量，各组五对独立进程交错。正式列表和渐变使用同一源码候选的不同主题Development构建，主题内A/B二进制相同；Release演示另建。所有数字属于历史m4-final-b017672，代码对应关系见公开版本记录。不可用的CPU/GC/内存指标保留空值；Fixed32质量受限和所有inconclusive场景见[RESULTS](RESULTS.md)。

完整原始证据继续私有保存；公开哈希是完整性和来源对应信息，不是数字签名，也不构成新的独立实验。
