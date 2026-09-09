# 固定细分第二次恢复协议

此协议在新调度前冻结，沿用[正式协议](GRADIENT_SUBDIVISION_PROTOCOL-r1.md)和[首次恢复](GRADIENT_SUBDIVISION_RECOVERY-r1.md)的构建、完整160项计划及判据。

- 原 matrix 保留 index 0..51 的52项有效运行及 index52 的一次失焦 invalid；matrix-recovery1 保留 index52..53 的两项有效运行及 index54 的一次180秒超时。超时没有Runner原始目录，正确性 unavailable、有效性 not_assessed，不伪造样本。
- 新 matrix-recovery2 只运行完整原计划 index54..159 的106项，首项重试原第55项。三来源按原 ordinal 合并，原始runId和五轮配对不重编号、不挑选最佳结果。
- 用户明确回复“没有，可以让 Player 保持前台”，授权仅在本次拥有PID的可见窗口上执行启动阶段 SetForegroundWindow。无外部窗口激活、无采样期间焦点维持轮询。10秒内不能取得前台则停止自有进程并保留失败；180秒总时限包含焦点等待。
- 焦点取得记录在进程结束后写receipt；acquiredUtc和最后一次激活必须不晚于原始 events.log 首行 Prepare。否则整次不接受。Runner本身的startFocus、focus_lost、有效性规则不变。
- 新campaign policy以SHA绑定旧policy、两棵保留树的每个文件、全部旧新工具、协议和同一plan/gate/build。原11工具、报告、原数据、原策略均冻结不变。
- 新driver保持独占锁、先写intent、Popen后立即记录准确PID；未知启动状态保留锁/intent，不自动重发。确认终止的失败保留失败记录。任一失败停止后续调度，先诊断再决定新恢复。
- 新报告逐项复验各来源自己的launcher哈希、policy哈希、raw13件及环境，保留两次失败，不用receipt替代raw检查。比较算法、质量0.01目标、统计阈值不变。

本轮仍为dirty-source探索性证据，不能升级为M4干净冻结版本。此工具准备中的首次批量生成被自动审批拒绝且未执行；已检查新路径不存在，改为逐文件独占创建并分别审查，不覆盖已有报告。

独立审查要求三root必须完全分离，包括禁止任何祖先/后代路径关系；新增反例覆盖两个保留root的子目录及共同父目录。被排除attempt也核验launcher哈希，并输出candidate/build、exitCode、duration及可得qualityStatus。焦点操作的阶段归属由原始Prepare时间事后复核；迟到的焦点操作会使整次不被接受，不能宣称工具具备Runner内部实时阶段锁。
