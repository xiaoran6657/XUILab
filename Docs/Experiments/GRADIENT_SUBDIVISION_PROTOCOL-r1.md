# 固定段数扫描协议 r1

M3-G1；首次Player前冻结。沿用 gradient-schlick-v1、encoded-rgb、straight RGBA等权、目标maxError<=0.01，不预设固定64或自适应一定达标。Start=(.04,.75,.95,1)、End=(.95,.15,.4,.6)。默认FixedSegments=32。

## 质量矩阵

真实UGUI Mesh：宽高900×450与(900/14×0.9)×(480/8×0.9)，后者约57.857143×54；两方向×bias .05/.5/.95×segments8/16/32/64，共48组合。保存实际Mesh颜色、坐标、索引与密集4097点连续double参考。未量化分段曲线的max/RMS和Color32误差分开；量化上界0.5/255+float误差。多尺寸用于验证几何，不以数值误差代替感知质量。

受控像素沿用M2质量v2：256×128线性RGBA8、无Blend/HDR/MSAA/postprocess、显式Gamma顶点开关、同诊断Shader/原有管线临时副本，方向与四段数和代表bias扫描。像素对实际量化分段函数max<=2/255、RMS<=1/255；连续曲线误差独立，不为极端bias放宽0.01。

## Player代表成本集

下表是覆盖集，非全笛卡尔积；不跨group推断单独尺寸因果。grid100为14列8行、全部可见；large为单图。

| group | layout/count | 每图宽×高 | direction | state | bias |
| --- | --- | --- | --- | --- | --- |
| large-static-05 | large/1 | 900×450 | Horizontal | static | .05 |
| large-static-50 | large/1 | 900×450 | Vertical | static | .5 |
| large-static-95 | large/1 | 900×450 | Horizontal | static | .95 |
| grid-static-05 | grid/100 | 57.857143×54 | Vertical | static | .05 |
| grid-static-50 | grid/100 | 57.857143×54 | Horizontal | static | .5 |
| grid-static-95 | grid/100 | 57.857143×54 | Vertical | static | .95 |
| large-dynamic | large/1 | 900×450 | Horizontal | all | .05↔.95 |
| grid-dynamic | grid/100 | 57.857143×54 | Vertical | all | .05↔.95 |

每group四段数×5独立进程=160runs；轮1/3/5按8,16,32,64，轮2/4反序，group顺序固定。pilot单独large动态8/64和grid动态8/64共4次，不计入五轮。每run独立进程，300预热/1800采样；动态从warmup状态继续，测量action索引从300开始，300帧半周期、完整600帧往返。相邻半周期连接端点同值不dirty。每条sample/action对齐下一Unity帧；首条不得SetBias重置或Canvas flush。

每段共享截面2顶点，实际记录Mesh vertices/indices/triangles/selectedSegments。静态准备一次冷构建时间单列；稳态含Mesh生成、Canvas和渲染的真实帧间隔，动态另记组件dirty/rebuild，不能把它们称为总Canvas/GPU时间。质量扫描在采样结束后覆盖完整600帧动态bias最坏值，禁止只看最终帧；超目标仍保留quality_limited。

固定Unity2022.3.45f1c1、Windows x64 Development Mono、D3D11、960×540、Linear/High Fidelity、target-1/VSync0；数据/材质/种子与作用集合一致。仅Frame Interval required，CPU/GC/memory/UI/GPU缺失写unavailable。无截图/录屏/逐帧MCP/重Profiler/文件写入进入采样窗。

## 身份、失败和统计

预冻完整源码/构建/计划/gate SHA，实际exe自检；启动前意图与全局锁，结束确认owned PID退出并保留receipt/log。未知进程保留锁和意图，不自动再发；超时180s只终止owned进程，确认终态后保留失败，不覆盖或替换原run。任何失败先停止，按明确恢复记录处理未执行项。

每run线性插值p*(n-1)算p50/p95/p99/max/超过16.6666667ms比例，按group/segments展示五轮、中位数和全距，不合并进程。与同group固定32配对：五对至少四对同方向且中位数差超过max(5%固定32中位数,双方p95全距的一半)，才improved/regressed；否则inconclusive。质量与成本分别报告；质量不达标的模式可以报告成本但不能称满足目标的优化。质量Pareto观察不自动选择默认；G2仍沿M2约定min1/max64和0.01目标。
