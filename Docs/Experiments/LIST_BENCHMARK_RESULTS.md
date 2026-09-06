# List Lab Windows Player 实验 — r3

2026-09-06。这是未提交候选的工程探索，**不是作品集公开性能声明**。本次完成 50 轮共同主矩阵、4 轮预检，以及压力档的 3 轮有效运行和 1 轮预算超时。虚拟实例在已完成的 100/300/1000/10000 档保持 13 个；但 1000 档不限帧的 p95 帧间隔相对普通列表退化。100 档与 60 FPS 补充组的 p95 差异为 inconclusive。

正确性、测量有效性与性能方向分别判定。最终独立审查/验收入口为 [M1-04 状态](../PM/Tasks/M1-04/TASK_STATUS.md)，设计取舍见 [案例草稿](LIST_LAB_CASE_STUDY.md)。

## 身份与方法

| 项目 | 本次值 |
| --- | --- |
| candidate | `list-r3-8756E9288BE4`，dirty=true |
| source revision | `9f032952199644624a58df41988e3679304ba7ac` + [冻结源码清单](../PM/Tasks/M1-04/WORKSPACE_SNAPSHOT-r3.sha256) |
| build | `list-dev-20260906T071112Z`，[全量二进制清单](../PM/Tasks/M1-04/BUILD_SNAPSHOT-r3.sha256) |
| Editor / Player | Unity 2022.3.45f1c1、Windows x64、Mono Development、可见窗口 |
| 硬件 / OS | Ryzen 5 5600G，12 logical processors；Radeon RX 9070；Windows 10 10.0.19045 64bit |
| 图形 / 画面 | Direct3D11，960×540，High Fidelity，VSync=0；两后端相同 Cell/字体/Canvas/视口/裁剪 |
| 主矩阵 | 100/1000 × scroll/lifecycle × -1 target；1000 scroll额外60 FPS；每后端每配置5个新进程 |
| 动作 | 300 warmup / 1800 sample；确定性 C# 三角轨迹/生命周期；每组 ABBA ABBA AB |
| 统计 | 每轮 `(n-1)*p` 线性插值；跨5轮median、min/max、MAD、IQR；不拼接帧 |

协议为 [LIST_BENCHMARK_PROTOCOL.md](LIST_BENCHMARK_PROTOCOL.md)，布局/生命周期边界为 [LIST_CONTRACT.md](LIST_CONTRACT.md)。每个有效 run 保留基础七文件与两个 List 扩展文件、相邻日志和进程 receipt；源根为 `Artifacts/list-player-r3`。严格验收器另有版本化工具清单，对 config 字节SHA、九文件集合、身份、环境、逐行动作/计数、下一帧对齐和 summary 重算。

## p95 帧间隔

以下是**各轮 p95 的中位数 [最小, 最大]**，单位 ms。方向判定使用预先冻结的规则：五轮范围不重叠，且中位数差值大于双方 MAD 之和，才写 improved/regressed；否则为 inconclusive。

| N / 动作 / 目标帧率 | 普通 ScrollRect | 虚拟窗口 | 虚拟相对普通 |
| --- | --- | --- | --- |
| 100 / scroll / -1 | 16.570 [16.468,16.687] | 16.822 [16.462,17.004] | inconclusive |
| 100 / lifecycle / -1 | 16.477 [16.252,16.756] | 16.307 [15.354,16.414] | inconclusive |
| 1000 / scroll / -1 | 12.955 [9.284,13.498] | 16.511 [16.429,16.638] | regressed |
| 1000 / lifecycle / -1 | 13.280 [12.759,14.717] | 16.564 [16.469,16.927] | regressed |
| 1000 / scroll / 60 | 17.087 [17.015,17.203] | 17.065 [17.024,17.456] | inconclusive |

![p95五轮比较](../../Artifacts/list-analysis-r3/p95-comparison.png)

完整 MAD/IQR、p50/p99/max、over-budget、冷开、首次可交互及生命周期分段表见 [推导表](../../Artifacts/list-analysis-r3/tables.md)。[SVG](../../Artifacts/list-analysis-r3/p95-comparison.svg) 与 [PDF](../../Artifacts/list-analysis-r3/p95-comparison.pdf) 可用于进一步排版。

## 功能计数和生命周期成本

所有有效主矩阵轮次的可见内容/模板/绑定、精确 active 与窗口租赁数、每行动作、位置和终态检查通过。位置最大误差为0 px（容差0.05 px），拒绝归还0，Cleanup后unique=0。稳态scroll预热后两后端都不继续创建/销毁。

普通列表在稳态保持N个实例；虚拟列表单模板共13个实例，滚动时leased随窗口在边界变化，剩余对象进入cache。清空/禁用时租赁归零。虚拟生命周期结束仍累计created=13、destroyed=0；普通1000生命周期累计created=2968、destroyed=1968，来自两次释放/重建与同一16个缓存上限，最终仍owned=1000。这不等同于内存泄漏。

| 1000档观测量 | 普通 | 虚拟 |
| --- | --- | --- |
| scroll不限帧，p50五轮中位 ms | 8.642 | 3.703 |
| 同组同步UI构造时间中位 ms | 465.032 | 169.594 |
| 同组首次下一帧就绪时间中位 ms | 1006.165 | 746.969 |
| lifecycle清空动作对应帧间隔中位 ms | 67.429 | 3.782 |
| lifecycle重填动作对应帧间隔中位 ms | 329.543 | 6.276 |
| lifecycle重开动作对应帧间隔中位 ms | 325.531 | 12.076 |

这些中位数描述具体观测，不替代上面的 p95 方向规则。同步UI构造从创建 Canvas 到第一次 SetItems/Layout，**不含进程启动、场景加载或此前生成数据快照**；“首次下一帧就绪”是 Runner 的下一帧代理指标，不是完整应用启动耗时或端到端输入延迟。生命周期单次动作的范围见推导表。

![实例和生命周期说明](../../Artifacts/list-analysis-r3/list-architecture.png)

## 压力边界

压力计划独立于五轮主矩阵。300档两后端完成；10000档虚拟列表完成1800样本，unique=13、位置误差0、Cleanup unique=0，单轮p95=16.430 ms。单轮数据不进入五轮聚合。

10000档普通列表 `list-r3-stress-list-normal-10000-scroll--1-r1` 达到180秒预算。编排器只终止其创建的PID48156，receipt记录180.126秒；没有完整九文件终态，**p95、完成样本数及内部失败阶段 unavailable**，不能把超时填成零或有效比较。旁证保留在 [orchestration failure](../../Artifacts/list-player-r3/list-r3-stress-list-normal-10000-scroll--1-r1-orchestration-failure.json)。

编排器在超时后停止，主 Agent 通过 [剩余计划执行脚本](../../Artifacts/finish_list_stress_r3.py) 校验原冻结manifest和build hash，只执行原计划最后的virtual10000；未重试失败普通轮，也未覆盖任何输出。压力档结论为“3轮有效 + 1轮预算失败”，不是整组全部通过。

## 有效性和解释限制

- 仅采用可见r3运行。r2隐藏窗口虽通过数据检查却导出黑帧，且存在工具重试构建干扰风险，全部排除；见 [恢复记录](../PM/Tasks/M1-04/RECOVERY-r2-hidden-player.md)。
- 正式窗口期间没有截图、录像、编码、Unity导入/测试/构建或重型分析。另一Unity项目仍打开，未控制或测量其全部后台负载；本结果只覆盖这台机器本次显示环境，不能泛化到其他设备。
- Main Thread、GC Allocated In Frame、System Used Memory没有可用 recorder 样本；UI rebuild/batches/vertices没有验证的测量源，均 unavailable。不能声称“零GC”或从Bind推出网格重建数量。
- 帧间隔包括可见Player的显示/调度影响，不能当作列表组件CPU耗时。虚拟列表在1000档p50、构造和重建动作上的数值较低，同时p95较高；本次没有足够marker证据解释其因果，不归因于某个驱动或合成器。
- 60 FPS组over-budget比例约0.76，阈值严格为16.6666667 ms，很多样本只略超该值；不能解读为“76%肉眼卡顿”。
- 所有有效帧和高波动轮次保留，没有为了得到收益丢弃数据。M4公开数字需要在另行授权后，以干净提交重新构建复测。

## 媒体与复核入口

[30秒演示草稿](../../Artifacts/list-media/list-demo-r4.mp4) 由最终同build的独立可见Player生成，450帧/15fps，依次展示普通、虚拟和双模板/渐隐/位置恢复；它不是测量视频。原始图像为 `Artifacts/list-media/frames-r4`，capture.json与帧保留。图表由 [分析脚本](../../Artifacts/analyze_list_r3.py) 从同批原始数据导出。

审查、源码/构建/工具/产物哈希与状态分别见 [M1-04交接](../PM/Tasks/M1-04/HANDOFF-r3.md) 和 [任务状态](../PM/Tasks/M1-04/TASK_STATUS.md)。没有提交、推送或公开发布本轮产物。
