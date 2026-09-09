# 列表单项刷新实验结果

候选 `list-refresh-update-r3`，构建 `list-refresh-dev-r4`。110 次矩阵运行及 4 次独立预试验均通过正确性、测量有效性与逐帧复算。冻结判据得到 **3 组 improved、8 组 inconclusive**；不存在为了通过而删除慢帧、挑选轮次或替换失败运行。

## 结果与边界

下表为五次独立进程的 p95 中位数，单位 ms；变化为 Target 相对 Window。判据在首次 Player 前冻结：五对至少四对同方向，且中位数差超过 `max(5%窗口基线中位数, 两组p95全距的一半)`。不同后端、不同限帧模式分别比较。

| 后端 / 动作 / 限帧 | Window | Target | 变化 | 结论 |
| --- | ---: | ---: | ---: | --- |
| normal-idle-fps-1 | 4.2099 | 4.0930 | -2.78% | inconclusive |
| normal-sparse-fps-1 | 4.1864 | 4.2085 | +0.53% | inconclusive |
| normal-burst-fps-1 | 4.2465 | 4.1119 | -3.17% | inconclusive |
| normal-high-fps-1 | 28.9868 | 4.5268 | -84.38% | improved |
| normal-batch-fps-1 | 28.9842 | 4.9015 | -83.09% | improved |
| virtual-idle-fps-1 | 0.6390 | 0.6342 | -0.75% | inconclusive |
| virtual-sparse-fps-1 | 0.6368 | 0.6404 | +0.56% | inconclusive |
| virtual-burst-fps-1 | 0.6410 | 0.6375 | -0.55% | inconclusive |
| virtual-high-fps-1 | 0.9519 | 0.6743 | -29.16% | improved |
| virtual-batch-fps-1 | 1.0322 | 1.0312 | -0.10% | inconclusive |
| virtual-high-fps60 | 17.0035 | 17.0040 | +0.00% | inconclusive |

普通列表高频更新降低约24.46ms（84.38%），普通列表批量降低约24.08ms（83.09%）；虚拟列表高频降低约0.278ms（29.16%）。这些是当前 Development Player、N1000、固定窗口和共同校验负载下的帧间隔差异，不是主线程CPU或Canvas耗时。

Window 路径枚举当前 cells 并调用 Intersects：普通列表保留1000个，虚拟窗口13个；Target路径只检查指定索引。既有字典已支持索引映射，本次成果是公开数据更新、失效/异常合同和目标派发。批量组双方均9Bind/帧，普通列表仍有较大差异，与全列表扫描成本解释一致；没有独立CPU marker来量化扫描/Canvas各占多少。

稀疏和突发动作每60帧发生一次，p95主要落在无更新帧，inconclusive并不证明更新时等价。以下p99和严格16.6666667ms超预算比例作为描述性证据，未替换预定主判据：

| 组 | Window p99中位数 | Target p99中位数 | Window超预算 | Target超预算 | Bind总数 W/T |
| --- | ---: | ---: | ---: | ---: | ---: |
| normal-idle-fps-1 | 4.640 | 4.616 | 0.000% | 0.000% | 0 / 0 |
| normal-sparse-fps-1 | 28.025 | 4.768 | 1.667% | 0.000% | 270 / 30 |
| normal-burst-fps-1 | 74.874 | 4.566 | 1.667% | 0.000% | 810 / 90 |
| normal-high-fps-1 | 29.946 | 4.930 | 100.000% | 0.000% | 16200 / 1800 |
| normal-batch-fps-1 | 29.577 | 5.338 | 100.000% | 0.000% | 16200 / 16200 |
| virtual-idle-fps-1 | 0.678 | 0.653 | 0.000% | 0.000% | 0 / 0 |
| virtual-sparse-fps-1 | 0.910 | 0.697 | 0.000% | 0.000% | 270 / 30 |
| virtual-burst-fps-1 | 1.000 | 0.738 | 0.000% | 0.000% | 810 / 90 |
| virtual-high-fps-1 | 1.034 | 0.715 | 0.000% | 0.000% | 16200 / 1800 |
| virtual-batch-fps-1 | 1.107 | 1.098 | 0.000% | 0.000% | 16200 / 16200 |
| virtual-high-fps60 | 17.029 | 17.030 | 75.722% | 75.500% | 16200 / 1800 |

60FPS组p95约17.00ms，双方近乎重合。该帧间隔包含等待和计时粒度；严格阈值附近的超预算比不能直接解释为渲染工作超过预算。虚拟批量组也无明确收益，双方都需要重绑全部九项。

## 配置和可复现入口

设备：Windows 10  (10.0.19045) 64bit；AMD Ryzen 5 5600G with Radeon Graphics（12逻辑处理器）；AMD Radeon RX 9070 / Direct3D 11.0 [level 11.1]。Unity2022.3.45f1c1、Windows x64 Development Mono、D3D11、960×540、Linear、High Fidelity。

每次独立进程预热300帧、测量1800帧。主矩阵VSync0/不限帧；补充virtual/high为target60。N1000、双模板、offset492、可见10–18九项，普通1000 leased、虚拟13 leased；cached和created另见逐帧原始数据，不把13 leased称为池内总共13个。

Frame Interval available；Main Thread、GC Allocated In Frame、System Used Memory全部unavailable，未替换为零；UI rebuild marker也unavailable。每次coldBuildMs单列在原始metrics/复算details，未纳入稳态p95。

- [冻结协议](LIST_REFRESH_PROTOCOL-r1.md)
- [完整计划](../../Artifacts/list-refresh-player-r4/matrix-r4.json) / [预试验计划](../../Artifacts/list-refresh-player-r4/pilot-r4.json)
- [构建清单](../../Artifacts/list-refresh-player-r4/build-manifest.json) / [实际测试门禁](../../Artifacts/list-refresh-validation/preflight-r3.json)
- [110-run原始复算](../../Artifacts/list-refresh-player-r4/matrix-verification-r1.json) / [4-run预试验复算](../../Artifacts/list-refresh-player-r4/pilot-verification-r1.json)
- [114-run目录/日志/收据补充验收](../../Artifacts/list-refresh-player-r4/matrix-supplement-r2.json) / [预试验补充](../../Artifacts/list-refresh-player-r4/pilot-supplement-r2.json)
- [逐轮图SVG](../../Artifacts/list-refresh-player-r4/report-r2/list-refresh-p95.svg) / [全比较表JSON](../../Artifacts/list-refresh-player-r4/report-r2/comparison-table.json)
- [功能与Runner验证](../PM/Tasks/M3-L2/VERIFICATION-r3.md) / [实际恢复](../../Artifacts/list-refresh-validation/player-matrix-r4-restore.json)

构建输入294项、完整Player296文件；manifest SHA `00e65dc06fac859828fb94ca8d14a9958aabef675ac7189edc6b0c6c4c00b256`。主计划SHA `62c588a2a84eb158bac925737fa7af4f891cd1027ad73499ac650e6021839b91`。源码HEAD `b40eac4397bf5f717d86deaa2058f13c33b3e7b8`，dirty=true；这是M3探索证据，不是M4干净提交基准。

## 五轮p95明细

| 组 | Window r1..r5 (ms) | Target r1..r5 (ms) |
| --- | --- | --- |
| normal-idle-fps-1 | 4.1783, 4.0509, 4.2099, 4.3364, 4.2894 | 4.0767, 4.0739, 5.2197, 4.7819, 4.0930 |
| normal-sparse-fps-1 | 4.5608, 4.1864, 4.1616, 4.2363, 4.1793 | 4.0806, 4.7793, 4.5636, 4.2085, 4.1379 |
| normal-burst-fps-1 | 4.2465, 4.3909, 4.3472, 4.2174, 4.1752 | 4.0880, 4.1119, 4.0996, 4.1717, 4.1305 |
| normal-high-fps-1 | 28.8002, 29.2432, 29.1370, 28.9868, 28.7217 | 4.6646, 4.2449, 4.5877, 4.2786, 4.5268 |
| normal-batch-fps-1 | 28.9842, 29.0864, 28.8273, 29.5889, 28.7057 | 4.9089, 4.8916, 4.8755, 4.9623, 4.9015 |
| virtual-idle-fps-1 | 0.6298, 0.6372, 0.6448, 0.6390, 0.8080 | 0.6342, 0.6375, 0.6376, 0.6302, 0.6269 |
| virtual-sparse-fps-1 | 0.6528, 0.6368, 0.6424, 0.6346, 0.6318 | 0.6404, 0.6330, 0.6433, 0.6368, 0.6436 |
| virtual-burst-fps-1 | 0.6417, 0.6335, 0.6406, 0.6410, 0.6674 | 0.6427, 0.6315, 0.6287, 0.6375, 0.6641 |
| virtual-high-fps-1 | 0.9692, 0.9417, 0.9405, 0.9519, 0.9704 | 0.6827, 0.6662, 0.6666, 0.6743, 0.6814 |
| virtual-batch-fps-1 | 1.0406, 1.0322, 1.0272, 1.0256, 1.0559 | 1.0172, 1.0216, 1.0312, 1.0392, 1.0320 |
| virtual-high-fps60 | 17.0026, 17.0028, 17.0044, 17.0047, 17.0035 | 17.0033, 17.0040, 17.0056, 17.0039, 17.0046 |

## 学习与后续决定

可见单项Target确实从9Bind减为1，离屏更新0Bind/0创建，并在入屏后恢复最新数据。代价是pending、模板映射与回调异常恢复复杂度；54项真实测试和20组独立trace复算覆盖这些边界。批量更新说明减少扫描与减少Bind是不同因素。当前继续保留VisibleWindow默认，由M3-05结合渐变实验与最终回归选择默认策略。

失败路径保留：r2测试因预期异常日志未声明而失败，修正精确LogAssert后r3通过；首次成功构建的输出路径表示不兼容journal，保留原响应并在独立目录按native路径完成下一构建。详见[实施记录](../PM/Tasks/M3-L2/IMPLEMENTATION_LOG.md)。

补充验收不伪造旧receipt的启动字段：日志SHA在完成后捕获用于保全。执行身份来自冻结launcher的Popen/wait记录、实际Player路径门禁、构建来源及全raw关联；不声称密码学进程证明。Core参数化测试有三个数组用例被MCP显示为同名System.String[]，按冻结源的精确多重集合核验，未丢弃明细。SVG r2及PNG已视觉检查，11组轴/标签/图例可见；r1透明背景问题通过r2白底修复，原数据不变。
