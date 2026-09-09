# Gradient 颜色与过渡合同 v1

- contract_id: gradient-schlick-v1
- candidate: gradient-contract-r2
- brief_revision: r2
- 来源：XUILab个人复现的新合同；不声称还原LUI历史数学实现。

## 颜色函数

实际绘制矩形由输入Mesh的坐标界限确定；Horizontal从左到右、Vertical从下到上。t在[0,1]，端点分别为Start/End。Linear模式 w=t；Nonlinear模式采用 w=t / ((1/b-2)*(1-t)+1)，Bias b限制在[0.05,0.95]，表示t=0.5时End颜色的权重，b=0.5等价线性。不存在另一个含混的gradientPosition参数。

Evaluate返回Color.LerpUnclamped(Start,End,w)。RGB和alpha均在输入的数值空间插值，颜色限定LDR [0,1]；本合同把颜色数值解释为编码RGB，Linear和Gamma工程均不在CPU执行.gamma/.linear转换。它不是线性光插值；实际UGUI渲染/显示转换属于后续像素验证，必须记录工程颜色空间。当前工程Linear保持不变。

顶点输出color=输入UIVertex.color逐通道乘Evaluate(t)，最终量化到Color32；Graphic.color已包含在输入颜色中，不能重复乘。纹理和材质alpha在原UGUI Shader阶段相乘，不读取纹理、不创建/修改材质。相同起止色不会被特殊强制成不透明。

样例：t=0/0.5/1，b=.05时w=0/.05/1，b=.5时0/.5/1，b=.95时0/.95/1。分母始终为正；导数为((1-b)/b)/(t+((1-b)/b)*(1-t))²，严格正。纯API非有限输入拒绝；有限t clamp，有限Bias clamp。序列化校验将非有限Bias恢复.5、颜色非法通道恢复安全值；setter比较规范化后的精确值再dirty。

## 网格和降级

Linear仅修改现有顶点颜色，索引/所有其他通道保留。Nonlinear的固定基线使用32段、33截面；相邻截面共享2顶点，因此66顶点/192索引/64三角形。

细分要求4个唯一轴对齐矩形角点、6个索引构成两个同向非退化三角形且共享对角线、相同z、uv0满足仿射矩形映射。不同顶点顺序和两种合法对角线均支持。非有限通道或退化宽高不细分。Image仅Simple允许细分（PreserveAspect依实际绘制矩形）；其他Graphic须通过同一几何检查。

Sliced/Tiled/Filled/Radial和非矩形网格按已有顶点着色，保持拓扑并报告VertexFallback；空Mesh/退化范围安全返回并报告Empty/Degenerate，不产生NaN或非法索引。关闭组件完全保留输入。

新顶点沿左右/上下边分别插值position、normal、tangent、uv0–uv3及输入color；normal/tangent不额外归一化。再按曲线乘色。Shader兼容只针对已测试材质；M2-03用受控读取附加通道材质和数值测试交叉验证。

## 过渡

Controller与Mesh生成分离。StartTransition(fromBias,toBias,duration)显式指定起止；启动立刻应用from，重复启动替换旧动画。有限duration<=0立即应用to并结束；非有限参数拒绝且不改变旧状态。进度clamp到[0,1]，Linear easing或SmoothStep(3p²-2p³)。默认Unscaled时钟，可选Scaled；Runner关闭自动时钟并调用SetProgress(p)，避免帧率改变动作。

Cancel(false)保留当前值并结束；Cancel(true)应用终值后结束。disable/destroy取消并保留当前值，重新enable不自动恢复；池复用必须显式重新启动。反向通过交换from/to实现。SetProgress在未运行时无操作；到1后结束，不再回写。未绑定有效Effect时明确拒绝启动。

## 质量和实验预设

先验证固定32基线再允许M3固定8/16/64与自适应模式。密集参考4097点，RGBA各通道等权，记录max绝对误差与RMS（不称感知误差）；颜色量化另计1/255容差。质量目标maxError<=0.01，自适应min=1/max=64，上限仍超目标必须quality_limited，禁止事后放宽。

M2代表静态/动态对照使用同色、同布局、同可见数：image-only/disabled/linear/nonlinear/same-value/transition，单图、grid、RectMask2D列表，100/500/1000与2000/5000压力；采用覆盖组合而非全笛卡尔积。M3固定段数扫描两个方向、大小与bias=.05/.5/.95，静态及动态。具体执行清单在M2-04、M3-G1/G2的协议中于首轮前冻结。

正式Player方法沿用v1的300预热/1800采样/5独立进程和ABBA顺序，诊断/媒体另跑。默认策略保持M2固定32及M1整窗口刷新，直至M3-05按实际证据作决定。没有预设性能必须改善。

## r2 精确边界（实现冻结前补充）

宽/高<=1e-5为Degenerate。角点与z容差e=max(1e-5,min(width,height)*1e-5)；4唯一角/6索引，两个三角形同向且均非退化，每角至少引用一次，共享的两角必须构成对角线，原绕序保持。uv0四通道仿射条件为|uvBL+uvTR-uvTL-uvBR|²<=1e-10；常量或一维退化UV允许（合法单色纹理采样），非仿射回退。任意顶点次序映射为BL/TL/TR/BR，合法两种对角线均支持。

水平沿底/顶两条边插值，垂直沿左/右边插值；t=0/1复制对应端点字段（颜色仍需乘渐变）。RGBA输入Color32先转float，沿边插值后乘Evaluate，只在输出统一量化一次：clamp01后floor(channel*255+0.5)，无中间Color32舍入。normal/tangent/uv0–uv3逐分量线性插值、不归一化；输入任一位置/附加通道非有限则报告InvalidInput并保持输入，禁止新增几何（不承诺修复原输入已有NaN）。

Controller可观察IsRunning、Progress、CurrentBias和EndReason（None/Completed/Cancelled/Disabled）。Start使用规范化Bias，duration<=0即Progress=1/IsRunning=false/CurrentBias=to/Completed。SetProgress非有限先拒绝，不改变任何状态；未运行时有限值无操作。p=1结束后再调用不会回写。Cancel(false)保留Progress与CurrentBias并结束/Cancelled；Cancel(true)若运行则完成/Completed，无运行时不改变终态。disable/destroy若正在运行则保留值/进度并结束/Disabled，re-enable保持；新Start清除旧结束原因/进度，以新起点开始。自动推进与手工进度共用唯一状态，无异步旧回调。Clock/Easing只接受已定义枚举。

质量记录固定colorSpace=encoded-rgb、alphaMode=straight-rgba-equal-weight；数值误差比较未量化的连续曲线与未量化的分段函数，Color32顶点误差单列，截图误差固定实际项目Linear、输出sRGB/alpha合成规则后另评估，不能混用。
