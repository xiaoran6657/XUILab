# 离线复现与恢复工具

统一证据入口：[证据目录](../Experiments/EVIDENCE.md)。本手册维护依赖和操作合同；具体候选／执行结果由 PM 记录，历史证据索引保持原身份。

## 依赖

| 工作 | 必需依赖 | 不需要 |
| --- | --- | --- |
| PM 检查 | Python 3.10+ 标准库 | Unity、网络、pip |
| B 批统一检查、证据目录包、SVG 出图、恢复检查 | Python 3.11+ 标准库（使用 hashlib.file_digest） | ReportLab、matplotlib、Unity、网络 |
| List 实际恢复执行 | Windows x64 交互桌面、冻结的完整 Development Player、相匹配的计划／构建哈希、唯一操作者 | 重建 Editor（已有完整 Player 时） |
| M0 旧工具 | Windows PowerShell 5.1；实跑另需对应 Windows Player | Python |
| Unity 重建／测试 | 固定 2022.3.45f1c1，Packages manifest/lock 所列依赖 | Unity 6 |

本轮实测 Python 3.14.3；3.11 是代码最低版本要求，未声称对所有解释器版本执行过测试。无需安装全局工具或执行 pip install。旧 `Artifacts/analyze_list_r3.py` 的 ReportLab 是历史脚本依赖；新出图入口不调用它。新工具只输出 SVG/JSON/Markdown，不复制历史 PDF/PNG 的像素布局或架构说明图。

## 统一离线检查

在检出根运行（`python` 应指向实际解释器）：

```powershell
python --version
python -B Tools/check_offline.py
python -B Tools/check_offline.py --bundle '<证据包目录>' --expected-index-sha256 '<可信交接记录中的 SHA-256>'
python -B -m unittest discover -s Tools/ProjectManagement -p 'test_*.py'
python -B -m unittest discover -s Tools/ListLab -p 'test_*.py'
python -B Tools/ListLab/test_resume_evidence_integration.py --bundle '<证据包目录>' --expected-index-sha256 '<可信交接 SHA>'
```

统一入口只读，不启动 Player；无包时明确 `partial (evidence not_run)`，不能据此宣称数据验证通过。exit 0 表示所请求检查成功，exit 1 为检查失败。八个 M0/M1 legacy PM 提示表示只覆盖旧任务状态前缀，不重新授予旧验收。完整边界见 [PM 检查手册](PM_CHECK_PLAYBOOK.md)。

普通测试无真实包时会跳过一项可选集成；单独的 integration 命令验证 4 个真实 Python 子进程复制历史 fixture、严格校验并产生 receipt，第二次恢复不重复执行。它不启动 Unity Player，也不产生新的性能采样。设 `XUILAB_TEST_EVIDENCE_BUNDLE` 为实际包路径后，unittest discovery 可包含该项。

## 创建与搬迁证据包

已核对的 [List catalog](../Experiments/LIST_EVIDENCE_CATALOG.json) 明确证据身份、原输出路径、三个计划以及从原 SHA 清单选择的范围。`pack` 要求每个源文件匹配既有清单；不会按当前文件重新计算并接受漂移。catalog 必须随代码一起交接。

```powershell
python -B Tools/ListLab/evidence_bundle.py pack --repo . --catalog Docs/Experiments/LIST_EVIDENCE_CATALOG.json --out Artifacts/list-core-transfer
```

输出为一个可直接复制到其他磁盘的目录，包含 `bundle.json` 和按仓库相对路径排列的原始文件。**保存 pack 输出的 indexSha256，通过独立可信交接记录传递给接收者。** SHA 用于完整性和身份绑定，不是数字签名；攻击者若能同时替换目录、catalog 和可信哈希仍可伪造来源。本工具没有上传或发布能力。

`pack` 不覆盖／合并已有目录；失败留下的部分目录不是可用证据包，应保留诊断并选择新的空输出路径重试。拒绝越界、大小写冲突、符号链接和 Windows junction/reparse point。不提供 ZIP 解压器；使用正常文件复制后必须重新 check。

```powershell
python -B Tools/ListLab/evidence_bundle.py check --bundle '<复制后的目录>' --expected-index-sha256 '<交接 SHA>' --out Artifacts/imported-audit.json
python -B Tools/ListLab/analyze_list_evidence.py --bundle '<复制后的目录>' --expected-index-sha256 '<交接 SHA>' --out Artifacts/imported-charts
```

audit 文件及图表目录必须在包外且不存在；父目录应已准备好（出图工具可创建父目录）。包内配置的旧 outputDirectory、源码修订与 dirty 字段保持原始字节。校验器通过 catalog 显式原路径映射，不猜测实际路径或重写 config/identity。单独使用原校验器时可指定 `--recorded-root '<原输出根>'`，省略仍按当前物理路径严格比对。

`check` 的 integrity=pass 只代表选定文件完整。pilot/matrix 逐运行重新计算，并验证环境分组一致；stress 的失败项单独保留，不生成缺轮聚合。catalog 不包含媒体、截图、Editor 恢复日志或源码工程，因此这是 **core 交接包**，不是完整历史归档或可公开发布包。源码由另行检出提供；旧 dirty 采样也不等于当前检出的复建证据。

## 派生结果

新出图工具每次从包内原始样本重算完整 50-run matrix；不接受未验证的 aggregate JSON。结果为 `audit.json`、`comparison.json`、`tables.md`、`p95-comparison.svg`。每个配置分别聚合五个独立进程的 p95，保留 min/max/MAD/IQR；不拼接逐帧值，不把压力失败放进性能图。

方向沿用历史探索式判据：范围不重叠且两组中位数差大于 MAD 之和时才标 improved/regressed，否则 inconclusive。它不是显著性检验，frame interval 也不是组件 CPU 时间。可选指标缺失保持 unavailable；证据包校验成功不代表性能改善。

## 恢复计划

通用入口为 [resume_list_plan.py](../../Tools/ListLab/resume_list_plan.py)，替代旧 Artifacts 中固定最后一项的特例脚本。默认只检查；`--execute` 才能启动进程。实际参数以 `--help` 为准，执行前遵守 [Benchmark 操作前检查](BENCHMARK_RUN_PLAYBOOK.md)及唯一 Unity Operator 约定。不要把完整历史 core 包当作待补跑计划，也不要在不可变包内执行。

对本次历史包的只读示例（应得到 completed=3、failed=1，无 pending）：

```powershell
python -B Tools/ListLab/resume_list_plan.py --root '<包目录>/Artifacts/list-player-r3' --manifest '<包目录>/Artifacts/list-player-r3/list-r3-stress-manifest.json' --recorded-root '<repo>/Artifacts/list-player-r3'
```

对另一个获授权、尚有 pending 的冻结计划，在包外工作副本执行：

```powershell
python -B Tools/ListLab/resume_list_plan.py --root '<待恢复工作目录>' --manifest '<待恢复工作目录>/<stamp>-<plan>-manifest.json' --recorded-root '<原始输出根>' --player '<当前构建目录>/<Player.exe>' --build-root '<当前构建目录>' --recorded-build-root '<旧构建目录>' --execute --continue-after-failure
```

默认从 manifest 文件名推导 series 与相邻 build-hashes JSON；非标准命名必须显式 `--plan`、`--series-id`、`--build-hashes`。省略 `--execute` 不校验二进制实际哈希，仅检查计划／运行与 hash JSON 结构。`--continue-after-failure` **只跳过已失败项，执行剩余 pending**，绝不重试原失败 run-id。若没有历史失败可省略此开关。锁存在、任一残缺／冲突运行都会拒绝执行。

原 `run_list_matrix.py` 的新计划 CLI 保持原参数，冻结与运行现已共用恢复锁和意图记录。实际执行前及各子进程前检查冻结 manifest/hash 文件字节与所有已钉住的构建哈希；旧 launcher 的 build-hashes 只钉 EXE 和 XUILab 程序集，完整 Player 搬迁还必须先通过 core 包的 287 文件清单。恢复工具不把部分哈希清单夸大为完整构建验证。

待恢复计划应先作为独立工作目录交接：保留冻结 manifest、build-hashes、原始运行、receipt/failure 和意图记录；构建路径迁移使用显式映射。对已完成项重新校验原始文件与 receipt，失败项保持失败；残缺目录、缺失 receipt 或遗留意图／锁不会自动被当作 pending。确认原进程已结束、保存诊断和恢复决定后，才能手工处理残留锁；不能按时间超期自动抢占。

复制到新机器后新增的运行不自动构成同一环境序列；最终聚合仍需环境一致性检查，不满足时保留分开的证据，重新授权独立实验。新输出根与原记录路径的映射只解决搬迁校验，不授权混合主机性能。

## M0 与历史工具

`Tools/Benchmarking/` 的四个 PowerShell 工具继续按 [Benchmark 复跑手册](BENCHMARK_RUN_PLAYBOOK.md)使用：`Get-XUILabM0CalibrationSummary.ps1` 是只读数据校验／汇总；`Test-XUILabM0CalibrationEvidence.ps1` 需要已有 M0 原始数据并在临时副本执行反例；`Test-XUILabM0CalibrationOrchestration.ps1` 是受控编排测试。`Invoke-XUILabM0Calibration.ps1` 会实际启动 Player，不属于默认离线检查。

B 不迁移 M0 到 List catalog，也不修改 M0 运行合同。旧 List 特例脚本和原图表留在 Artifacts，历史 SHA 清单继续标识它们。新的工具源、测试和使用说明随代码交接，以后不再把可维护工具只存于忽略目录。

## 后续离线工具

M2/M3 的离线计划、预算、显式参考质量与恢复入口见 [Gradient 工具合同](GRADIENT_BENCHMARK_TOOLING.md)；这不代表已有 Gradient Runtime 或正式阶段证据。全套离线检查可用 [一次性调度](OFFLINE_AUTOMATION.md)，完整源码与显式媒体/证据目录使用 [源码归档](SOURCE_ARCHIVE.md)。必要任务续接沿用现有薄技能。
