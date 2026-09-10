# 有界自适应细分实验结果

候选 `gradient-adaptive-r1`，构建 `gradient-adaptive-dev-r1`，源码 `b40eac4397bf5f717d86deaa2058f13c33b3e7b8` + dirty。这是M3探索性证据，不是M4干净发布基准。协议见[Adaptive r1](GRADIENT_ADAPTIVE_PROTOCOL-r1.md)。

80项正式独立进程均正确且采样有效，另有4项有效pilot，不计入比较。2项正式失焦无效尝试和3项pilot故障全部保留。首次15个有效运行在2026-09-08且Editor打开，余65项在2026-09-09且Editor关闭；动态网格第1对跨日，其余情景第1对同日，轮2–5均同日。用户确认MiniEngineSandbox不再切换前台后恢复65项无新增失败。

## 质量与拓扑

固定32在极端bias的连续RGBA误差约0.0384221，超过0.01目标；自适应在极端bias选择12段，误差约0.00723908；中心bias为1段。动态600个bias最大误差0.009941919907，自适应全部达标，实际段数1..12。默认cap64是上限，不代表恒定使用64段。

单个组件固定32为66顶点/64三角形；自适应中心4/2、极端26/24。100组件最多6600→2600顶点。颜色量化误差独立列出（动态最大0.001959860445）；受控像素与连续近似不是同一指标。质量只覆盖本矩阵矩形Image、uniform white base、规定RGBA/Schlick函数，不承诺任意纹理/Shader或非均匀底色。

## 五轮帧间隔

| 场景 | Fixed32 p95中位ms | Adaptive p95中位ms | 原定判据 |
| --- | ---: | ---: | --- |
| large-static-05 | 0.775005 | 0.790005 | inconclusive |
| large-static-50 | 0.791100 | 0.816615 | inconclusive |
| large-static-95 | 0.786420 | 0.775340 | inconclusive |
| grid-static-05 | 0.735075 | 0.705200 | inconclusive |
| grid-static-50 | 0.772020 | 0.738905 | inconclusive |
| grid-static-95 | 0.710765 | 0.748405 | inconclusive |
| large-dynamic | 0.792510 | 0.733230 | inconclusive |
| grid-dynamic | 9.123955 | 4.723390 | improved |

自动判据得到7项inconclusive、动态网格1项improved，后者中位差-4.400565ms（-48.23%）。首轮跨日，因此不能将五对全部视为严格相同后台环境；轮2–5同日的四对也都较低，约减少47%–49%，是方向一致的补充观察，不取代预定五轮协议，也不删掉首轮重算主报告。静态与单个动态的跨日波动远大于小差异，保持inconclusive。独立审查复算80项分位数全部一致；同日轮2–5动态网格中位9.110040→4.702830ms（-48.38%），仅作补充观察。独立接受本场景的有限结论，不能据自动标签直接宣称普遍性能收益。

## 选择器与冷启动成本

静态测量窗口selector调用/缓存命中/ticks均为0；动态每组件1794次有效bias变化，100组件179400次，dirty/rebuild数对齐。每组件只缓存一个结果，正式矩阵中bias变化全部失效，cacheHits=0；geometry-only缓存命中由生命周期测试覆盖。

自适应动态选择计时中位数：单组件2.6368ms/1800帧、100组件168.6465ms/1800帧（约0.094ms/采样帧）。这部分已包含在帧间隔中，并含缓存检查及计时仪器开销，不能当作整帧CPU或GPU成本。100组件冷选择约0.9985ms，冷Prepare约53.4922ms，后者包括创建与Canvas flush。CPU、GC、内存、UI/GPU计数器仍unavailable。

观察：动态矩形网格在减少非均匀Mesh段数的同时达到了更严格的连续质量目标，每采样帧选择计时约0.094ms，不能与p95差值直接等量比较；帧间隔变化同时受拓扑和提交工作影响。可能解释是生成/提交几何量减少；没有CPU/GPU分项，因此不能据此锁定瓶颈。静态场景不据此宣称更快。默认Fixed32保持兼容，Adaptive显式可选；M3-05综合决定记录适用范围。

## 原始证据

- 完整报告：`Artifacts/gradient-adaptive-player-r1/matrix-report-r1.json`，每轮分位数、全距/MAD、质量、选择开销、来源root与invalidAttempts。
- 构建：同目录`build-manifest.json`（282源输入、296构建文件）；门禁`Artifacts/gradient-adaptive-validation/preflight-r1.json`，五完整程序集30+6+7+8+32通过。
- 正式有效来源：`matrix`前14、`matrix-recovery1`第15、`matrix-recovery2`剩65。当前恢复策略`matrix-policy-recovery2.json`；来源及排除增强检查`failed-attempt-audit-r1.json`。
- pilot：`pilot-recovery3`与`pilot-report-r1.json`。旧`pilot`/`pilot-recovery1`/`pilot-recovery2`分别为失焦、缺焦点回执、系统Python缺NumPy；均未计入正式或有效pilot。
- 图与逐组CSV：`Artifacts/gradient-adaptive-player-r1/plots-r2/`；绘图依赖复用本机`Artifacts/gradient-report-deps`，版本锁定`Tools/GradientLab/requirements-plot.txt`。

![逐轮质量与成本（历史记录未公开）](../Showcase/HISTORICAL_RECORDS.md)

正式采样期间未截图、录制、逐帧MCP或运行重型分析；图表来自采样完成后的报告。历史归档与独立接受入口见[任务状态（历史记录未公开）](../Showcase/HISTORICAL_RECORDS.md)。
