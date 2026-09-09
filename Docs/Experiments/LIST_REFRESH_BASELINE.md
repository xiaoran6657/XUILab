# 列表窗口刷新基线诊断

## 结论

原M1 RefreshItem(index)无论目标是否可见，都扫描cells并重新绑定全部9个可见Cell。ListCellPool.Rebind先Unbind清空Text再Bind恢复，因此未变行也产生dirty和Mesh工作。普通后端扫描1000项，虚拟后端13项；可见目标只占总绑定中的1项，离屏目标占0项。

两个后端的12个单项场景均得到总9 Bind、18 vertex dirty、9 layout dirty，后续自然帧/强制flush合计观察到9次Text Mesh探针调用。这是实际UGUI链路观察，不能把9→1直接写成CPU、Canvas或帧时同比例改善。

## 冻结输入与实际执行

候选list-refresh-trace-r1，277项输入清单见[M3-L1](../PM/Tasks/M3-L1/WORKSPACE_SNAPSHOT-r1.sha256)。M1 Runtime16项与M1-04原r3逐哈希一致；仅新增测试探针，不改基线实现。Unity2022.3.45f1c1，Windows Editor，两个后端各N1000、48px行高、384px viewport、初始offset492、双模板、无动画/fade。移动项使用自然ScrollRect velocity，实际移动普通6.071716px、虚拟1.104309px，非SetPixelOffset伪造滚动。

实际PlayMode单测试内执行18个独立场景，1/1Passed、0failed/skipped。操作及恢复见[验证](../PM/Tasks/M3-L1/VERIFICATION-r1.md)。[原始trace](../../Artifacts/list-refresh-trace-r1/trace.json) SHA-256：0de1f1d46d0c92cc911a8129b3a30e0a9c51287213049264a2ff1621d26a9ad8；[离线复算](../../Artifacts/list-refresh-validation/trace-r1-verification.json)重新核对每阶段映射、绑定、文本、几何、池、事件index、重入及自然移动。

## 观察

| 场景 | 目标/总Bind（两个后端） | 普通/虚拟扫描 | vertex/layout dirty | Mesh探针调用 |
| --- | --- | --- | --- | --- |
| 可见中部、首行部分可见、末行部分可见 | 1/9 | 1000/13 | 18/9 | 9 |
| 刚离屏仍prefetch、完全离屏 | 0/9 | 1000/13 | 18/9 | 9 |
| 自然滚动中可见项 | 1/9 | 1000/13 | 18/9 | 9 |
| 模板reset | 全表1000/窗口13次总Bind | 1000/13 | 见原始trace，初始新Cell不可观测 | 18 |
| 插入reset | 全表1001/窗口13次总Bind | 1000/13 | 同上 | 18 |
| 删除reset | 全表999/窗口13次总Bind | 1000/13 | 同上 | 18 |

模板/插删通过现有SetItems，属于一次数据重置操作，不是单项写入，也不能把按实例复用推导的targetBind当成真正单项API性能。新Cell在外部探针安装前已可能dirty，后安装probe自身亦会dirty；其Mesh18仅诊断，不能和前六场景当作同条件成本比较。

可见集合初始10–18，prefetch租赁8–20。更新index9后再进入可见时，普通和虚拟都仍显示旧Label；更新index700后，普通因始终保留该Cell也显示旧Label，虚拟因新租赁绑定最新数据而正确。这是reflection-only诊断注入揭示的基线缺口：现有公开API没有单项数据写入接口，不能声称用户可通过正常API直接产生该更新。

## 计数边界与假设

每个case新建列表，安装probe后稳态flush、清零；记录before、同帧dispatch后、下一自然帧、显式Canvas flush，离屏额外记录重入。Graphic dirty回调保留事件发生时Index，Mesh探针不修改VertexHelper；零次观察的vertices=-1表示不可用。Canvas.willRenderCanvases观测2次是事件，不是Canvas重建次数；FixedRowLayout实际重建调用、Canvas marker、CPU/GC均unavailable。全部订阅解绑、列表销毁后Pool unique0。

M3-L2冻结假设：保持相同公开数据发布/可见内容和动作，仅比较窗口策略与目标策略；目标可见时只绑定一次，离屏只更新数据，进入可见时必须刷新，不能以旧文本换取计数下降。已有index→cell字典应被复用；重点是数据版本/失效、模板和租赁同步，而不是重新创造映射。

A/B必须在Player中区分稀疏、突发少量、高频，另保留大量可见项同时更新的窗口批量参考。Bind、dirty和Mesh下降只证明工作减少，真实帧时/CPU/GC仍分别评估；无清晰差异允许保留简单默认。Editor本诊断performance=not_assessed。
