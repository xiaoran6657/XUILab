# Gradient Lab：让渐变质量和网格成本可以分别核对

本文对应冻结候选 `m4-final-b017672`。实验比较 `Fixed32` 与显式选择的 `Adaptive64`，关注非线性 Schlick bias 渐变在不同组件规模、静态／动态输入下的质量与帧间隔。数据来自主题专用的 Windows Development Player 构建；它不和 List Lab 跨主题比较绝对毫秒。

## 1. 背景与约束

实时 UI 中常见的一类问题是：颜色沿曲线变化，但网格只在少数截面上做线性插值。均匀增加段数能改善一部分输入，却会在平缓区域浪费顶点；极端 bias 又可能在固定段数下仍超出误差目标。另一个证据缺口是把连续函数误差、Color32 量化、屏幕像素观感和 CPU/GPU 时间混成一个“看起来更好”的结论。

本案例的质量合同是受支持矩形、uniform white base、RGBA/Schlick 参数和 4097 个连续参考点；连续 RGBA 最大绝对误差目标为 0.01。非矩形拓扑、纹理、非均匀底色和任意 Shader 不自动继承这个结论。`Fixed32` 的极端 bias 结果即使可运行，也必须标记 `quality_limited`。

## 2. 我的工作边界

| 范围 | 本案例如何归属 |
| --- | --- |
| Unity 基础 | UGUI `BaseMeshEffect`、VertexHelper、URP 和颜色类型是第三方运行基础。 |
| XUILab 工程 | `GradientFunction`、`GradientEffect`、`GradientSegmentSelector`、`GradientTransitionController` 以及质量／生命周期测试是项目实现。 |
| Agent 工作 | Agent 负责按固定配置构建主题 Player、交错运行、保留样本和复算报告；数字不由媒体或文案反向调整。 |
| 学习状态 | [渐变学习篇](../../Learn/GRADIENT_SUBDIVISION.md)解释源码和证据，但不证明用户已经亲自实现或理解；个人复盘另行记录。 |

第三方许可证和项目贡献范围见[来源说明](../SOURCES.md)。

## 3. 技术问题

`bias` 改变曲线中点的位置，不能只用端点判断质量。需要同时回答三个问题：连续函数是什么，怎样把误差大的区间变成更多截面，以及这些截面怎样进入 UGUI 网格。自适应选择达到段数上限仍可能超标；达到误差目标也不等于屏幕像素、GPU 或总内存已被证明更好。

## 4. 设计与实现

`GradientFunction.Weight/Evaluate/Normalize/Quantize` 定义权重、RGBA 插值、输入约束和 8 位量化。`GradientEffect.ModifyMesh` 识别输入拓扑；`StrictRectangle` 通过轴对齐四角、6 索引、绕序、对角线和 UV 仿射关系后，`Subdivide` 沿矩形边界插值并写入新顶点。Unsupported Image 走 fallback，得到颜色结果不代表完整曲线质量已评估。

`GradientSegmentSelector.Select/Error` 使用确定性的 `schlick-greedy-midpoint-v1`：先放端点，计算各段误差，选择误差最大的段，同误差取最左，再在中点插入，直到达到容差或上限。`GradientEffect.EnsureSelection` 按颜色、bias、曲线、范围和容差缓存选择；尺寸和方向变化只重新映射截面。`GradientTransitionController` 负责随时间推进 bias，不直接绘制网格。源码入口见[GradientFunction](../../../XUILab/Assets/XUILab/GradientLab/Runtime/GradientFunction.cs)、[GradientEffect](../../../XUILab/Assets/XUILab/GradientLab/Runtime/GradientEffect.cs)和[GradientSegmentSelector](../../../XUILab/Assets/XUILab/GradientLab/Runtime/GradientSegmentSelector.cs)。

## 5. 验证方法

矩阵包含 8 个场景（large/grid、static/dynamic、bias 05/50/95）× 2 策略 × 5 个独立进程，共 80 次；每次预热 300 帧、采样 1800 帧，五轮交错。每次先算 p95，再比较五轮中位数和范围，沿用预先固定的方向与阈值。质量另用连续参考计算最大误差，和帧间隔分开记录。

| 条件 | 实际身份 |
| --- | --- |
| 源码／构建 | `m4-final-b017672`；`m4-gradient-development-b017672-r2` |
| 环境 | Unity 2022.3.45f1c1、Windows 10、960×540、D3D11、VSync 0、High Fidelity、Mono Development |
| 正确性与有效性 | 80/80 运行 `pass / valid`；固定和自适应使用同一主题专用二进制 |
| 质量输入 | 受支持矩形、uniform white base、RGBA 连续误差目标 0.01 |

## 6. 结果

| 场景 | Fixed32 → Adaptive64 p95 中位（ms） | 变化 | 判定 |
| --- | ---: | ---: | --- |
| large-static-05 | 0.621510 → 0.621805 | +0.05% | inconclusive |
| large-static-50 | 0.621300 → 0.622810 | +0.24% | inconclusive |
| large-static-95 | 0.617900 → 0.623615 | +0.92% | inconclusive |
| grid-static-05 | 0.615605 → 0.569105 | -7.55% | improved |
| grid-static-50 | 0.614525 → 0.563405 | -8.32% | improved |
| grid-static-95 | 0.613310 → 0.566125 | -7.69% | improved |
| large-dynamic | 0.622205 → 0.609605 | -2.03% | inconclusive |
| grid-dynamic | 8.445310 → 4.388835 | -48.03% | improved |

最终是 4 组 `improved`、4 组 `inconclusive`。动态网格的下降来自 100 个组件场景；不能外推成所有静态 UI 都更快。`Fixed32` 极端 bias 连续 RGBA 最大误差约 `0.0384221`，所以是 `quality_limited`；`Adaptive64` 本轮实际使用 1–12 段，动态最大误差约 `0.009941919907`，极端静态约 `0.00723906`。Adaptive 64 是上限，不是每次使用 64 段。选择器累计时间已包含在帧间隔中，不能再直接从 8.445310 或 4.388835 中扣除；Main Thread、GC、内存和 GPU 分项均 `unavailable`。最初一次渐变尝试因默认进入 ListLab、参数入口错误而 exit2 且无 raw，已保留并排除，不能改写成样本。

## 7. 学习与适用边界

可推广的原则是把“曲线语义→截面→分段网格→颜色量化→屏幕结果”分层验证，并让质量目标与时间成本各自有字段。自适应适合曲率集中的场景，但需要明确 fallback、容差、上限和缓存失效。当前结论只覆盖协议规定的矩形和颜色输入，不是任意材质的视觉保证；文档也不代替用户完成学习。

## 8. 复跑与证据

先读[结果与统计边界](../RESULTS.md)、[证据索引](../EvidenceIndex.md)和[RUN_INDEX](../RUN_INDEX.md)，再按[渐变计划](../../../Artifacts/m4-final-validation/gradient-matrix-plan-r2.json)、[策略](../../../Artifacts/m4-final-validation/gradient-policy-r2.json)和[报告](../../../Artifacts/m4-final-validation/gradient-report-r2.json)定位 run-id。质量和生命周期检查见[GradientAdaptiveTests](../../../XUILab/Assets/XUILab/GradientLab/Tests/EditMode/GradientAdaptiveTests.cs)、[GradientMeshTests](../../../XUILab/Assets/XUILab/GradientLab/Tests/EditMode/GradientMeshTests.cs)与[GradientTransitionController](../../../XUILab/Assets/XUILab/GradientLab/Runtime/GradientTransitionController.cs)。定义和限制见[渐变学习篇](../../Learn/GRADIENT_SUBDIVISION.md)及[证据导航](../../Learn/EVIDENCE_NAVIGATION.md)。原始运行目录在本地 `Artifacts/m4-gradient-runs-r2/`，应保留失败尝试、构建身份和报告输入的绑定。


[媒体画廊](../MEDIA.md)提供封面、三张说明图与45秒独立演示。
