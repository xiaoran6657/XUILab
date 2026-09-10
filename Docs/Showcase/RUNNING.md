# 运行Windows展示包

源码为b0176724d58c7cda86b472340845d239714888d0，Unity 2022.3.45f1c1，Windows x64 Release、Mono、Linear色彩空间，产品名XUILab。场景顺序为ListLab、GradientLab、BenchmarkSmoke。实际构建[终态（历史记录未公开）](HISTORICAL_RECORDS.md)为0错误/0警告；性能数字来自独立Development构建。

## 启动

解压[Windows演示包](https://github.com/xiaoran6657/XUILab/releases/download/v0.1.0-preview.1/XUILab-Windows-x64-v0.1.0-preview.1.zip)到一个新目录，保留XUILab.exe、XUILab_Data、MonoBleedingEdge和UnityPlayer.dll的相对位置，双击XUILab.exe。也可在解压目录执行：

```powershell
.\XUILab.exe -screen-fullscreen 0 -screen-width 1280 -screen-height 720 -force-d3d11
```

目标为1280×720窗口；已验证缩放到960×540并恢复。顶栏切换三个主题，Quit退出；鼠标操作按钮，列表支持拖动和滚轮。High Fidelity质量，诊断可设置自己的帧率，不用于正式统计。只验证本机Windows环境，不声称覆盖其他GPU/Windows安装。

## 三个入口

| 入口 | 操作与观察 |
| --- | --- |
| List Lab | Backend切换Normal/Virtual；100/1000切换N；Top/Bottom跳到首尾；Save/Restore保存恢复位置；Reopen验证重新打开。Policy切换VisibleWindow/TargetOnly，Update item更新数据。底部显示visible、leased、cached、created和Bind计数。 |
| Gradient Lab | Fixed/Adaptive切换；Segments改固定段数；Bias/Direction改曲线和方向；Transition/Stop控制过渡。Simple示例使用细分；Sliced/Tiled/Filled明确标为fallback。 |
| Agent / Runner | Normal预期Completed/Pass/Valid/exit0；Fail预期Failed/NotRun/NotAssessed/exit1；Invalid预期Completed/Pass/Invalid/exit3。后两项出现False是预期诊断结果。运行记录只在内存，正式样本走独立入口。 |

## 包身份和处理

[包清单及ZIP哈希（历史记录未公开）](HISTORICAL_RECORDS.md)关联原始构建。Unity标记DoNotShip的Burst调试文件未进入包；12个无签名项目程序集中的CodeView PDB目录文字在副本内改为文件名，字节长度、IL、元数据及其他字节保留，变换偏移/原字串哈希见[包内清单（历史记录未公开）](HISTORICAL_RECORDS.md)。所有第三方二进制均与原构建逐字节相同，保留签名；早期r2/r3清理范围过宽而不作为交付。原始构建完全保留，打包不是新源码候选。

包附实际依赖的许可/NOTICE；完整隐私与许可范围见[SOURCES](SOURCES.md)。原始本机日志、参考材料和失败打包目录不作为对外资料。新机器若缺依赖或启动失败，保留日志并据环境排查，不沿用本机通过结论。
