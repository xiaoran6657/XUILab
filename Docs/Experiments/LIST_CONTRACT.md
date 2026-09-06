# List Lab 合同 v1

日期：2026-09-06。实现前冻结，关联 M1-01 至 M1-04。

## 来源与边界

采用本项目独立实现的固定行高虚拟窗口，不导入 LoopScrollRect，不复制 `Docs/References/` 源码，不声称精确复现实习项目。底层使用项目已锁定的 Unity UGUI 1.0.0 ScrollRect、RectMask2D、LayoutGroup 与 Text；许可随 Unity package，manifest/lock 保持现状。模拟排行榜数据与图形由项目生成，无外部素材。

## 数据、布局与位置

- 数据为不可变条目快照：唯一 stable id、template key（0/1）、预生成显示文本。重复 id、未知模板和 null 输入拒绝；替换前验证，失败保留旧数据。
- 固定行高 48，间距 0，视口 720×384（8 行），上下各预取 2 行；含部分行的最大窗口 13。单模板缓存上限 16／模板，双模板各 16。普通实现一次创建 N 个相同 Cell，滚动不创建销毁。
- 同一工厂生成 Cell，外层由固定行高 LayoutGroup 定位，内层 Wrapper 承载图形、文字和动画。普通与虚拟仅改变实例保留范围；同样字体、尺寸、裁剪、Canvas 和 Binder。虚拟 content 高度仍为 N×48。
- 位置快照为 top stable id + fallback index + 行内 offset。恢复先找 id，缺失则 clamp fallback index；空数据回到 0；最终像素位置 clamp 到 content-height minus viewport-height。误差容差 0.05 px；恢复清零 ScrollRect velocity。
- 刷新单项仍重绑当前窗口，供 M3 对照；不提前实现 M3 优化。

## 生命周期与归属

Create → Rent → Bind → Unbind → Return → cached 或 Destroy。池以实例身份登记唯一所有者与租赁状态，按不可变 template key 路由。重复／未知／失效 Return 返回 false 并增加拒绝计数，不入栈。Rent 清理待租缓存的失效对象；显式 Sweep 清理外部销毁的租赁与缓存，避免冷开 N 次租赁产生 N 次全表扫描。

Bind 前要求未绑定；显式 Rebind 先校验输入再 Unbind/Bind。Unbind 停止过渡并重置 Wrapper scale/alpha/position、文本与 index/id。Return 必须先确认归属再 Unbind。禁用释放全部租赁并保留有界缓存；重开按当前数据和位置重租。清空数据释放租赁；销毁 owner 清空租赁及缓存，幂等。外部销毁无法补执行 Unbind，不把此异常路径称为 Bind/Unbind 成功配对。

计数：created/destroyed 是累计唯一实例事件（外部销毁在 Sweep 观察时计入）；leased/cached 是存活集合且不相交；unique total = leased + cached = created - destroyed（Sweep 后）。active 是 hierarchy active 的存活租赁；visible 是与视口相交的已绑定项；unowned 应为 0（所有工厂实例由池登记）。Bind/Unbind 为累计成功绑定事件。销毁请求先退出所有权，Unity 延迟销毁在下一帧核对。

## 展示与测量隔离

双模板、Wrapper 动画、边缘 CanvasGroup alpha 渐隐和诊断层单独验证。渐隐不改 material，不拦截输入，RectMask2D 保留裁剪；主 A/B 关闭动画、渐隐和动态诊断。测量中不逐帧字符串格式化、日志、文件写入或 MCP 查询。

M1-04 使用测量协议 v1 的 300 warmup / 1800 samples / 5 independent Player processes，主共同规模 100、1000，单模板，960×540，60 FPS 与 uncapped 分开。冻结动作与 Case 扩展配置后才采样；冷开单独计时，不用 warmup 后首帧代替。10000 为受限压力探索，300 为参考。正式收益仅在正确性通过、有效性检查通过之后解释；未提交候选数据明确为探索性，M4 干净提交复建另行授权。
