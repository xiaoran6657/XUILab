# GradientLab 固定32段 Player 基线

本阶段得到24组各5次独立进程的有效数据（120次），另有2000/5000元素全量动态场景各1次180秒超时，按[冻结恢复协议](GRADIENT_MATRIX_RECOVERY-r1.md)跳过其余8次重复。完整130次计划状态为 **partial**；24组完整结果可以比较，两个超时组无有效帧时结论。此为 dirty 工作区下的受控开发基线，不是 M4 公开基准。

## 正确性、有效性和质量

120次 completed 均经原始数据、下一帧动作对应、预期 dirty/rebuild、实际可见集合、提交网格/颜色/索引、输出清理、启动焦点与构建/计划身份复核，correctness=pass、measurementValidity=valid。标准 bias .25 静态及 .25→.75 动态的固定32近似最大RGBA分量误差约0.001216856；bias .05/.95分别约0.038422115/0.038422127，超过0.01并正确标为quality_limited。质量函数采用encoded RGB/Alpha等权；dense 4097点与Color32量化分别检查，量化误差约0.0019608以内。网格误差不是最终屏幕像素误差；受控Shader/像素证据见[M2-03验证](../PM/Tasks/M2-03/VERIFICATION-r5.md)。

## 身份与环境

- candidate `gradient-runner-r5`，build `gradient-baseline-dev-r5`；sourceRevision `b40eac4397bf5f717d86deaa2058f13c33b3e7b8`，dirty=true。
- [272项源清单](../PM/Tasks/M2-04/WORKSPACE_SNAPSHOT-r5.sha256)、[296文件构建清单](../../Artifacts/gradient-player-r5/build-manifest.json)、[前置语义gate](../../Artifacts/gradient-validation/preflight-r5.json)。
- Unity2022.3.45f1c1、Windows x64 Mono Development；Ryzen5 5600G/12逻辑处理器、RX9070、Windows10 19045、D3D11，High Fidelity、Linear项目、960×540、VSync0、targetFrameRate=-1。
- 300帧预热+1800帧采样，每组5个新进程，正/逆序交替。完整配置/动作/几何见[首次采样前协议](GRADIENT_BENCHMARK_PROTOCOL.md)及[原计划](../../Artifacts/gradient-player-r5/matrix-plan.json)。每轮(n-1)p线性插值，跨轮median/range/MAD/IQR，未拼接所有帧。
- Main Thread、GC Allocated、System Used Memory均为unavailable（Recorder无有效样本）；UI marker、DrawCalls/Batches、GPU未取得。本报告没有CPU耗时、零GC、GPU或批次改善结论。帧间隔不是Mesh专属耗时。

## 五轮结果

p95是帧间隔毫秒。下面只显示有五轮的组；完整p50/p95/p99/max/超预算比例、每轮样本和波动见[机器报告](../../Artifacts/gradient-player-r5/matrix-report-r1/matrix-review.json)和[逐run表](../../Artifacts/gradient-player-r5/matrix-report-r1/runs.csv)。

| 布局/生成数 | 状态/方向/bias | p95 median ms | 五轮范围 ms | 质量 |
| --- | --- | ---: | --- | --- |
| grid/100 | image/Horizontal/0.25 | 0.634 | 0.627–0.641 | pass |
| grid/100 | disabled/Horizontal/0.25 | 0.632 | 0.625–0.637 | pass |
| grid/100 | linear/Horizontal/0.25 | 0.632 | 0.627–0.638 | pass |
| grid/100 | static/Horizontal/0.25 | 0.636 | 0.631–0.637 | pass |
| grid/100 | same/Horizontal/0.25 | 0.635 | 0.624–0.636 | pass |
| grid/100 | few/Horizontal/0.25 | 1.378 | 1.371–1.383 | pass |
| grid/100 | all/Horizontal/0.25 | 8.519 | 8.495–8.658 | pass |
| grid/100 | static/Vertical/0.25 | 0.633 | 0.628–0.673 | pass |
| grid/100 | static/Horizontal/0.05 | 0.631 | 0.628–0.642 | quality_limited |
| grid/100 | static/Horizontal/0.95 | 0.631 | 0.626–0.634 | quality_limited |
| grid/500 | static/Horizontal/0.25 | 0.624 | 0.621–0.636 | pass |
| grid/500 | all/Horizontal/0.25 | 40.548 | 40.317–40.859 | pass |
| grid/1000 | static/Horizontal/0.25 | 0.707 | 0.702–0.715 | pass |
| grid/1000 | all/Horizontal/0.25 | 80.408 | 80.141–80.675 | pass |
| grid/1000 | few/Horizontal/0.25 | 9.220 | 9.169–9.251 | pass |
| split/1000 | few/Horizontal/0.25 | 9.001 | 8.915–9.144 | pass |
| clip/1000 | static/Horizontal/0.25 | 2.088 | 2.076–2.101 | pass |
| clip/1000 | all/Horizontal/0.25 | 3.841 | 3.800–3.916 | pass |
| clip/1000 | few/Horizontal/0.25 | 2.457 | 2.440–2.491 | pass |
| large/1 | linear/Horizontal/0.25 | 0.634 | 0.631–0.642 | pass |
| large/1 | static/Horizontal/0.25 | 0.632 | 0.631–0.633 | pass |
| large/1 | all/Horizontal/0.25 | 0.635 | 0.629–0.647 | pass |
| grid/2000 | static/Horizontal/0.25 | 0.887 | 0.878–0.908 | pass |
| grid/5000 | static/Horizontal/0.25 | 1.434 | 1.432–1.451 | pass |

![五轮p95汇总](../../Artifacts/gradient-player-r5/matrix-report-r1/frame-p95.png)

Image-only与Effect-disabled视觉等价，p95区间重叠，结论no_clear_difference。Static与same-value同画面、同参数，五轮dirty/rebuild均0，帧时没有清晰区别；这支持setter不主动持续标脏，不能推出渲染零成本。Linear与Nonlinear不是相同曲线，不把约0.63ms静态结果说成无损优化。

同一全量动态动作下，Grid100/500/1000的p95中位数8.519/40.548/80.408ms，呈明显规模压力；500/1000超过16.667ms预算。每个动态元素1800帧中实际变化1794次，其余6次在连续半周期端点无变化，dirty/rebuild总数与此一致。静态5000可运行，p95中位数1.434ms，不代表5000持续重建可用。2000/5000全量动态的180秒超时覆盖启动、预热、采样和退出；没有完整samples，不用180秒除帧数伪造帧时，不推断崩溃或具体瓶颈。

Grid1000局部更新100个元素与Split相同位置、材质和动作，p95中位数9.220/9.001ms；五对结果均Split较低，但最后一对只差0.026ms。当前只是局部场景的小幅有利趋势，不据此更改默认Canvas结构；没有Canvas marker或batch观测，机制归因及普遍收益为inconclusive。

Clip生成1000行，实际可见19行（含末尾部分可见），981行culled；few更新2行，all更新19行。因此clip all的3.841ms不能与Grid1000 all的80.408ms当作同工作量优化。Clip1000静态2.088ms高于Grid1000静态0.707ms，提示生成数量、裁剪遍历及不同几何也有成本；没有单项CPU计时，不能将差值命名为RectMask2D独占成本。

## 复算与失败保留

[三组pilot验证](../../Artifacts/gradient-player-r5/pilot-verification.json)已通过。矩阵工具重新验证每个receipt、13项产物身份及hash、600状态质量扫描/实际网格，得到120 completed、2 timeout、8 deferred、0 unresolved/not_run。`player_matrix_report.py`因完整计划partial返回1，这是预期非全通过信号；120个有效run及24完整组不受其余压力组缺项污染。

原始目录：[matrix-runs](../../Artifacts/gradient-player-r5/matrix-runs)、[恢复策略](../../Artifacts/gradient-player-r5/resume-policy-r1.json)。保留r4大小写配置hash误判及旧失败目录；r5是新候选/构建/计划，没有改写失败receipt。报告工具与恢复工具在构建之后新增、分别hash绑定，不冒充272项原构建输入。历史证据在M3修改前还需冻结源快照，不能拿M3工作区直接通过旧输入门禁。

复算入口见[工具手册](../Agents/GRADIENT_BENCHMARK_TOOLING.md)。使用原Python/NumPy和Artifacts/gradient-report-deps中已锁版本运行工具，输出必须新目录。独立数据审查与最终验收见[M2-04状态](../PM/Tasks/M2-04/TASK_STATUS.md)。

## 下一步

M3优先保留同一曲线和色彩合同，扫描8/16/32/64固定段数的质量—成本，再评估有误差上限的自适应细分。不能只凭段数下降宣布变快，必须同条件Player比较并保留quality_limited/无清晰收益结果。[实现解释与媒体](GRADIENT_LAB_CASE_STUDY.md)。
