# 图形与演示视频

发布与下载状态见[公开交付记录](PUBLICATION.md)。全部关联m4-final-b017672。原始截图来自独立Release诊断，图表来自固定Development报告，二者不混为一次性能运行。统一1600×900图形及1280×720视频；没有AI合成截图、裁剪或视频后加数字。

## List Lab

![List封面](Media/ListLab/cover.png)

[45秒视频](https://github.com/xiaoran6657/XUILab/releases/download/v0.1.0-preview.1/list.mp4)。0–15秒Normal从首到尾；15–30秒Virtual重复滚动；30秒后TargetOnly更新，36秒保存/回顶，38秒恢复，41秒重新打开。展示分辨率下visible=8与正式采样fixture的9行不同，不能混用计数。

| 说明图 | 解释 |
| --- | --- |
| [性能](Media/ListLab/performance.png) | 5组，每组全5轮，零起点轴、p95中位数与轮间范围；6组未测 |
| [池合同](Media/ListLab/pool-contract.png) | 数据、可见窗口、租借/缓存实例分别计数 |
| [更新路径](Media/ListLab/update-paths.png) | Window与Target是两条备选策略 |

## Gradient Lab

![Gradient封面](Media/GradientLab/cover.png)

[45秒视频](https://github.com/xiaoran6657/XUILab/releases/download/v0.1.0-preview.1/gradient.mp4)。0–15秒Fixed32改变bias；15秒切Adaptive；30秒改变方向，曲线继续变化。底部诊断数字可能在切换首帧晚一帧更新，不作为正式数据。

| 说明图 | 解释 |
| --- | --- |
| [性能](Media/GradientLab/performance.png) | 8场景与所有重复，4组inconclusive保留 |
| [质量与成本](Media/GradientLab/quality-cost.png) | 连续误差、实际顶点、选择器累计开销分开 |
| [合同](Media/GradientLab/gradient-contract.png) | 曲线语义、网格选择与fallback边界 |

## Agent / Runner

![Runner封面](Media/AgentBenchmark/cover.png)

[45秒视频](https://github.com/xiaoran6657/XUILab/releases/download/v0.1.0-preview.1/agent.mp4)。0秒启动normal，16秒启动配置fail，18秒启动pause invalid，34秒后保留invalid终态。Failed和Invalid清楚显示process success=False。

| 说明图 | 解释 |
| --- | --- |
| [运行流程](Media/AgentBenchmark/pipeline.png) | 准备、确定性C#采样、导出后验证 |
| [三类终态](Media/AgentBenchmark/outcomes.png) | 并列案例；Completed不自动等于Valid |
| [失败恢复](Media/AgentBenchmark/recovery.png) | 列表14+36，渐变入口失败后新80次；失败不删除 |

## 时间与可复现性

每段视频均为675张原始PNG，以15 fps编码成45秒H.264/yuv420p，无音轨、切镜、拼接、后期标注或合成帧。动作由帧驱动，抓图的真实耗时可能长于播放时长；因此是技术演示，不是实时性能录像。转码后逐帧解码675帧均成功，见[视频清单（历史记录未公开）](HISTORICAL_RECORDS.md)。原始帧保留在[list（历史记录未公开）](HISTORICAL_RECORDS.md)、[gradient（历史记录未公开）](HISTORICAL_RECORDS.md)、[agent（历史记录未公开）](HISTORICAL_RECORDS.md)。

[图形manifest（历史记录未公开）](HISTORICAL_RECORDS.md)记录脚本SHA、输入报告SHA、run-id；[渲染manifest（历史记录未公开）](HISTORICAL_RECORDS.md)绑定SVG与1600×900 PNG。三主题各1封面+3说明图；原图、旧版和失败渲染保留，不把旧版当最终版本。[图形生成脚本（历史记录未公开）](HISTORICAL_RECORDS.md)、[渲染脚本（历史记录未公开）](HISTORICAL_RECORDS.md)、[捕获（历史记录未公开）](HISTORICAL_RECORDS.md)、[编码（历史记录未公开）](HISTORICAL_RECORDS.md)可审查。
