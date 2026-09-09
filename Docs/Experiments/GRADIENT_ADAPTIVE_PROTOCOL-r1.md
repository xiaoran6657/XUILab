# 有界自适应细分对照协议 r1

M3-G2；首次 Player 前冻结。算法和质量范围见 [任务合同](../PM/Tasks/M3-G2/TASK_BRIEF.md)，沿用 [固定扫描](GRADIENT_SUBDIVISION_PROTOCOL-r1.md) 八个 scenario 的几何、方向、颜色、动作、作用集合及环境。G1 旧候选只作为历史输入；本轮固定32与Adaptive同一新构建比较。

## 选择与正确性

Fixed32保持默认；Adaptive为min1/max64/tolerance .01、schlick-greedy-midpoint-v1。参数包含固定segments32（仅Fixed使用）、mode、min/max/tolerance/算法版本。Adaptive expectedVertices/expectedTriangles填-1表示必须观测，不作为实际零值。逐帧验证真实SelectedSegments范围、总vertices=2*(segments+visible)、triangles=2*segments、mode/bias、下一帧结算和dirty/rebuild；结束验证每个实际CanvasRenderer Mesh计数。

静态采样不调用选择器；动态每次bias有效变化选择一次，端点重复不dirty、不重建、不选择。每组件单项缓存，冷Prepare初次选择与稳态分开。每帧selection-samples.csv包含调用数、cache hits、Stopwatch ticks、可见组件最小/最大段数、受限组件数和最大解析估计；metrics记录频率、冷/稳态汇总和范围。选择计时包含缓存检查及仪器开销，不宣称整帧CPU时间。Fixed同样读取计数，期望全部为0。geometry-only缓存命中由独立生命周期测试验证，正式矩阵不混入额外几何动作。

## 质量与受控像素

两种尺寸900×450与57.857143×54、两方向、bias .05/.5/.95，读取实际非均匀Mesh位置/索引/Color32。默认阈值另加min1/max4/.01故意受限和min1/max64/.00001更严阈值。对4097点独立double参考分别报告未量化近似max/RMS、函数float偏差和Color32量化；受限必须保留实际误差。受控像素仍为256×128线性RGBA8、原诊断Shader/临时管线，max<=2/255、RMS<=1/255相对实际分段量化函数，不等于相对连续目标。非均匀底色质量未评估，任意纹理/Shader不在连续函数上界范围。

采样后质量扫描静态1个bias、动态完整600个bias，每bias按真实选择算法生成节点，导出可变长度quality-scan.csv。离线工具独立重算选择与4097点误差。quality.json保留最大近似误差那个bias的4097点；RMS如报告仅为该bias的RMS，不假称所有bias最大RMS。解析estimate、dense误差、Color32和像素分开。

## 运行顺序和有效性

八scenario × Fixed32/Adaptive64 × 五独立进程=80；轮1/3/5固定再自适应，轮2/4反序。pilot为large/grid动态两模式共4次，不计正式比较。每进程300预热、1800样本，600帧往返，测量从预热终态继续；同G1禁止采样窗内文件写入/截图/逐帧MCP/Profiler。Windows x64 Development Mono、D3D11、960×540、Linear/High Fidelity、target-1/VSync0，固定Editor2022.3.45f1c1。Frame Interval是wall-clock，CPU/GC/内存/UI/GPU unavailable。

候选源码、协议、build manifest、gate和完整计划SHA绑定。启动由拥有PID的launcher获取前台；只能在Prepare前尝试激活，记录实际时间；采样期间不维持抢焦点。失焦/超时/身份错误保留失败并停止，恢复只执行经核实未完成项，不覆盖旧日志。每次180s上限，只终止明确归属PID并等待退出。

每项p50/p95/p99按p*(n-1)线性插值。八组各五对，逐轮与全距/中位数展示：至少4/5同方向，且p95中位数差超过max(固定32中位数5%,两组较大全距一半)，才improved/regressed，否则inconclusive。质量未达标不能称满足目标；允许负收益。G2不改变默认，结果交M3-05做取舍。
