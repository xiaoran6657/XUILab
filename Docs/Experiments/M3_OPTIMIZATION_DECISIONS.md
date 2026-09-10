# M3 默认策略与学习记录

最终决定：列表保持 `ListRefreshPolicy.VisibleWindow` 默认；渐变保持 `GradientSubdivisionMode.Fixed`、32段默认。`TargetOnly` 与 `Adaptive` 为显式可选。此决定维持兼容和可解释性，不表示Fixed32达到所有质量目标；极端bias需要0.01连续RGBA误差时，应在受支持矩形与底色范围显式采用Adaptive，并检查quality_limited。未为决策修改Runtime。

## 列表：观察、假设、证据与决定

原观察：原RefreshItem只更新一项数据时仍重绑9个可见Cell。字典映射原已存在；普通列表遍历1000 cells，虚拟列表遍历13 leased。M3-L1反射注入是冻结M1诊断，不是公开更新API。[原始诊断](LIST_REFRESH_BASELINE.md)。假设是公开数据发布与目标派发可减少无关Bind和扫描，而非Canvas必然同比下降。

改动为公开UpdateItem/批量更新、TargetOnly派发、离屏pending、模板/租赁映射及异常和重入合同。相同数据、动作、窗口、构建和五轮独立进程，仅改变刷新策略。正确性覆盖滚动、reset、离屏重入、销毁、异常恢复；可见单项9→1 Bind，离屏0 Bind且无新建。复杂度代价是pending与生命周期维护，不宣称额外内存为零。

[逐轮报告](LIST_REFRESH_RESULTS.md)包含110个有效矩阵运行、4个pilot、所有五轮p95和p99/预算补充。预定判据3 improved、8 inconclusive。普通高频28.9868→4.5268ms（-84.38%），普通批量28.9842→4.9015ms（-83.09%），虚拟高频0.9519→0.6743ms（-29.16%）。虚拟批量与60FPS没有明确p95收益；稀疏更新的p95主要落在无更新帧，不能解释为更新等价。双方批量9Bind仍有普通列表差异，说明扫描和Bind是不同因素。

选择：需要单项内容更新并能遵守公开API合同时显式TargetOnly；兼容调用方维持VisibleWindow。不能通过反射写内部数据绕过pending。帧间隔不是CPU耗时，Bind不是Canvas rebuild；缺失CPU/GC/内存/UI分项保持unavailable。失败测试、构建路径恢复和所有运行保留。

## 渐变：观察、假设、证据与决定

原观察是均匀固定段在极端bias不能同时经济且达到0.01误差。假设是按Schlick曲线误差分配非均匀截面，在上限内减少几何并保持明确质量结果。

[G1固定段报告](GRADIENT_SUBDIVISION_RESULTS.md)的160个有效进程比较8/16/32/64段。极端bias连续RGBA误差依次约0.19047/0.09471/0.03842/0.01305，全部quality_limited；中心均达标。动态100组件8、16比32快，64退化，但速度不能抵销质量失败。实际像素符合分段插值不等于分段函数符合连续目标。

[G2自适应报告](GRADIENT_ADAPTIVE_RESULTS.md)的80个正式有效进程与4个有效pilot使用相同曲线、场景、动作、误差定义。Adaptive实际1..12段，600个动态bias最大误差0.009941919907；cap64是上限。Fixed32单组件66顶点/64三角形，自适应极端26/24。缓存仅一组选择输入，几何变化可复用，bias变化需重选；限额、非有限输入、颜色/几何及fallback均有回归。

原定五轮判据7 inconclusive、动态网格1 improved，p95中位9.123955→4.723390ms（-48.23%）。首对动态网格跨日且Editor后台状态不同；轮2–5同日补充方向一致（约-48.38%），不能删除首轮或将环境混杂隐藏。选择计时约0.094ms/采样帧（100组件）已包含在帧间隔，不能与p95差等量归因。静态和单个动态不声称普遍收益；CPU/GC/内存/UI/GPU分项unavailable。

选择：保留Fixed32兼容默认；对受支持矩形Image、规定Schlick/RGBA质量目标且需要降低几何的调用方显式Adaptive。检查质量结果并保留cap/fallback，不承诺任意纹理、shader或非均匀底色。两次正式失焦及三次pilot故障全部保留为excluded，无效尝试不混入80个有效统计。

## 代表回归与历史边界

新候选runtime-defaults-r1的EditMode34/34、现行PlayMode23/23，来自本轮新job；详见[M3-05验证（历史记录未公开）](../Showcase/HISTORICAL_RECORDS.md)。首次PlayMode全程序集因M3-L1旧诊断前提不成立而失败，已保留[恢复记录（历史记录未公开）](../Showcase/HISTORICAL_RECORDS.md)，未修改历史诊断或降低Runtime校验。所有当前探索报告仍绑定各自dirty源码/构建身份，不升级为M4干净基准。

## 两主题学习复盘

列表应能依次说明：数据发布→可见判定→Bind/Unbind→Graphic dirty→实际Mesh/Canvas工作→帧间隔，指出哪层已观测、哪层unavailable；解释为何9→1 Bind不推出9倍帧率，为何批量组同9Bind仍可能减少扫描。可用稀疏p95与p99对比复述“指标覆盖动作频率”的限制。

渐变应能说明：连续函数→截面选择→分段插值→Color32量化→屏幕像素，并分别解释误差。用Fixed64仍超0.01与Adaptive12段达标说明非均匀分配；用静态inconclusive说明顶点下降不保证帧间隔改善；说明缓存失效与选择计时的维护代价。

用户实际口头/书面复述尚未执行；相关Profiler trace的独立解读仍待安排，不能由材料代替学习验收。M4前需补两主题可复述解释和至少一段trace及其不可证明范围。M4输入包括上述协议、原始证据包、失败尝试、默认/可选合同以及新的干净提交重建身份；变高缓存、手工定位、Shader对照仍未实施，不替代两项必需实验。
