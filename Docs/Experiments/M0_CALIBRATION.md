# M0 测量协议校准

日期：2026-09-06。当前结论：r5 的冻结实验数据经第三次审查仍可信；r6 补齐 22 字段后，冻结后独立复审发现字段名和成功态字符串仍按 PowerShell 默认规则忽略大小写，因此 r6 为 `changes_requested`。r7 已改为 case-sensitive exact contract、扩充回归并通过三路冻结后独立复审；它没有改变 Runtime/Player 数据，复用 r5 build 与 20-run 冻结证据。M0 阶段出口为 `pass`。本报告不包含 UI 优化收益。

## r7 大小写敏感合同修复

- Invoke 的字段集合改用 case-sensitive membership；`P99FrameIntervalMs` 不再等价于 `p99FrameIntervalMs`。
- success 的 schema、run-id、state、failure、correctness、validity 和 performance 字符串全部改为 case-sensitive equality；`COMPLETED`／`VALID`／`NOT_ASSESSED` 不再满足小写协议值。
- strict verifier 的 JSON property set、冻结目录／文件集合、capability 名称与 status/unit 分支同步采用大小写敏感比较；证据 harness 新增 summary 属性名大小写篡改。
- Windows PowerShell 5.1 编排回归为完整合法摘要 10/10 accepted、sidecar 0，21/21 negative rejected；strict verifier 对 r5 20-run exit 0，evidence harness 为有效副本 1/1 accepted、14/14 tamper rejected。
- 本轮仍没有 Runtime、场景、Player 或协议数据变更，所以不新建 Unity build，也不重跑 EditMode／PlayMode／20-run。三路 Luna max 只读复审均给出 `accept`，未发现 P0/P1/P2。

## Superseded r6 编排合同与保留策略修复

- `Invoke-XUILabM0Calibration.ps1` 现在要求 summary 精确包含协议 v1 的 22 个字段，缺失或额外字段一律拒绝；原始 JSON string／boolean／integer／number/null 类型与有限性在转换前验证。
- success 语义同时锁定 `failureCode=none`、空 `failureReason`、`performanceComparison=not_assessed`，并要求 p50/p95/p99/max/over-budget 为非 null 有限数值；optional 统计只允许 null 或对应有限 number/integer。
- Windows PowerShell 5.1 编排回归以完整合法摘要运行 Main 10-run，10/10 接受且 sidecar 0；19 个缺字段、额外字段、类型／非有限值与 success 语义负向场景全部非零退出。该矩阵未覆盖字段名／枚举值大小写，因此由 r7 取代。
- 根 `.gitignore` 统一忽略整个 `Artifacts/`，compact evidence、Player logs、build、capture 和媒体都只保留在本机；仓库以本报告和 PM 文档中的身份、哈希和恢复位置索引证据。
- 本轮没有 Runtime、场景、Player 或协议数据变更，所以没有新建 Unity build，也没有重跑 EditMode／PlayMode／20-run。r5 的严格 verifier 与 13 项证据篡改测试仍对原冻结集合执行；r6 只补强单轮编排接受边界。

## r5 候选、修复与身份

- candidate：`m0-04-calibration-20260905T150509Z-25f3a323-dirty-r5`
- source revision：`25f3a323e54f536f3e77fda94e117f05a756c9c1-plus-m0-overlays`；dirty calibration，未 commit
- build：`m0-04-runner-dev-20260905T150533Z`；Unity 2022.3.45f1c1；Windows x64／Mono／Development
- BuildReport：Succeeded；0 errors；0 warnings；126,087,997 bytes；59.5730095 s
- build-summary SHA-256：`C37C13776F0D6BE8EE3EE859F603B374055B98C09470A1343E89FEF82E59DFB0`
- launcher EXE SHA-256：`2A6C58DA77A27ACBC350D259B08E7FB1786454EEF2C30BA3D7700D6877941F62`
- Runtime DLL SHA-256：`6C37B9D1FE04B8FD55B79ABF46397E656E2D3DFDE399629D4074917BC6452ED3`
- final main stamp：`20260905T152312Z`；final overhead stamp：`20260905T153204Z`
- 本机环境指纹：Unity 2022.3.45f1c1；Windows 10 64-bit；AMD Ryzen 5 5600G／12 logical processors；AMD Radeon RX 9070／Direct3D11；960×540；High Fidelity；Mono Development。

r5 的 verifier 在任何转换前校验 JSON 原始类型，并拒绝 NaN／Infinity、字符串布尔、字符串数字、隐藏 extra artifact 及 optional capability 状态／reason 与 CSV 不一致。r5 当时的编排回归只证明可解析但缺 `state` 的 summary 会非零退出并保留 sidecar；第三次审查确认它不足以证明完整单轮 summary 合同，现由上面的 r6 矩阵取代。Runtime writer 先序列化最终 config 的同一字节，再以这些字节重算并写入 `identity.configSha256`；EditMode 回归刻意在 identity 创建后修改 config，证明落盘 hash 仍匹配。

实际目录中存在六个成功的 r5 build：冻结使用的 `150533Z`，以及未采用的 `150633Z`、`150649Z`、`150705Z`、`150721Z`、`150737Z`。后五个没有覆盖冻结 build identity，只保留为 MCP 同步调用完成时序的诊断记录。

## r5 验证终态

| 检查 | 终态 |
| --- | --- |
| EditMode job `7911d1d824bb48739390b50b71cbed43` | 32/32 passed；0 failed；0 skipped；1.0798959 s |
| PlayMode job `7cd3a87bffa74be29e5c28e1f91d2f57` | 3/3 passed；0 failed；0 skipped；1.2480358 s |
| 编译／Console | 固定 Editor ready；0 error／0 warning |
| PowerShell parser | 4/4 scripts，0 parse error |
| 严格 verifier（真实 final r5） | exit 0；20/20；类型、有限性、schema、身份、环境、七文件、CSV 重算与完整合同通过 |
| verifier 自测 | 有效副本 1/1 接受；13/13 篡改拒绝，包括 NaN／布尔字符串／整数字符串／optional status-reason／隐藏 extra artifact |
| r5 malformed-summary 编排回归（已由 r6 取代） | fake Player 只覆盖可解析但缺 `state` 的 summary；入口 exit 1，sidecar reason 为 `summary_contract_evaluation_failed` |

## r5 最终主序列与开销聚合

final main 10/10 与 final overhead 10/10 均 completed／correctness pass／measurement valid／process success／exit 0，且每轮 1800/1800 samples。聚合只使用每轮统计，不拼接 frames。

| group | p50 median / range / MAD / IQR ms | p95 median / range / MAD / IQR ms |
| --- | --- | --- |
| idle-60fps | 16.668200 / 16.667699–16.668750 / 0.000201 / 0.000201 | 17.004600 / 17.003501–17.006414 / 0.000400 / 0.000600 |
| known-load-60fps | 20.113151 / 20.078950–22.876100 / 0.032150 / 0.048200 | 21.279505 / 21.233780–24.107601 / 0.024915 / 0.037565 |
| recorders-on-uncapped | 0.133700 / 0.128300–0.141200 / 0.005300 / 0.007650 | 0.190125 / 0.163505–0.215920 / 0.005525 / 0.006600 |
| recorders-off-uncapped | 0.131000 / 0.126550–0.134100 / 0.002600 / 0.003000 | 0.177005 / 0.155440–0.191315 / 0.011725 / 0.022400 |

known-load 只证明仪器能分辨预置恒定负载；由于一轮调度波动明显，它不构成产品性能比较。recorders on/off 范围重叠，performance comparison 保持 `inconclusive`，不能声明零开销。20 个按 run-id 排序的 `runId|artifactSetSha256` 行（LF 结尾）集合 SHA-256 为 `607845706AB28A86C137591CFE62B8B2C3CFD12CA36831EA56F0180797461475`。

## r5 失败路径旁证与预跑边界

| run／sidecar | 终态 | 关键结论 |
| --- | --- | --- |
| `m0-04-cal-main-idle-r1-20260905T152147Z` | failed / prepare_failed / not_assessed / exit 1；0 samples | `config.json` 精确字节 hash 匹配 identity；外层 sidecar 为 `run_contract_failed`；summary SHA `8884EA5D…`，sidecar SHA `FE21FC90…` |
| `m0-04-cal-main-idle-r1-20260905T152219Z` | completed / sample_shortage / invalid / exit 3；1 sample | 最终 config hash 匹配；invalid 未伪装成功；summary SHA `885B6434…`，sidecar SHA `1E9CEF18…` |
| synthetic malformed summary `20260905T153635Z` | parseable JSON，缺 `state`；入口 exit 1 | sidecar `summary_contract_evaluation_failed`；临时目录由测试在验证边界后清理 |

首次 r5 prepare-failure 试跑 `20260905T151944Z` 暴露编排器把 failed summary 的 null 统计误判为 malformed；该轮仍为非零退出且有 sidecar，没有冒充成功。修复后用 `152147Z` 重跑并按 failed 合同分类。`150813Z`／`151557Z` 的 preliminary 20-run 在最后一次编排脚本修订前生成，因此只保留为历史；final 聚合只使用 `152312Z`／`153204Z`。

## Superseded but intact r4 修复与候选身份

- candidate：`m0-04-calibration-20260905T055710Z-25f3a323-dirty-r4`
- source revision：`25f3a323e54f536f3e77fda94e117f05a756c9c1-plus-m0-overlays`；dirty calibration，未 commit
- build：`m0-04-runner-dev-20260905T055946Z`；Unity 2022.3.45f1c1；Windows x64／Mono／Development
- BuildReport：Succeeded；0 errors；0 warnings；126,087,957 bytes；14.94688 s
- build-summary SHA-256：`F28A58CDDA7E0027B01110779374CA9430E7EB6ACAB49BD0E8DD55BC22CA77B6`
- launcher EXE SHA-256：`2A6C58DA77A27ACBC350D259B08E7FB1786454EEF2C30BA3D7700D6877941F62`
- Runtime DLL SHA-256：`74D3137C29477389633A11ABF2E772FE3C543A40DF75CD0B12C5D5FB7D18A33D`
- main stamp：`20260905T060837Z`；overhead stamp：`20260905T061707Z`
- 本机环境指纹：Unity 2022.3.45f1c1；Windows 10 64-bit；AMD Ryzen 5 5600G／12 logical processors；AMD Radeon RX 9070／Direct3D11；960×540；High Fidelity；Mono Development。

r4 将 Measure 改为两阶段 action→下一帧 capture；PlayMode 用例直接断言 `sample.UnityFrame == action.UnityFrame + 1`，并验证同索引 35 ms heavy action 的样本中位数高于 light action。protocol v1 现在只接受单项 required `Frame Interval`；`identity.configSha256` 改为落盘 `config.json` 精确字节哈希。严格 verifier 会锁定 20 个目录、index 1..5、candidate/build/source、配置／环境／schema、七文件无额外项、CSV 1800 行与连续索引／累计时间，并从 CSV 重算 summary。

Unity MCP 的同步菜单调用在响应超时后发生重试，最终留下六个 r4 成功 build：`055805Z`、`055859Z`、`055915Z`、`055930Z`、冻结使用的 `055946Z`，以及稍后完成的 `060001Z`。五个未采用 build 没有覆盖冻结身份，仅保留为工具 retry 诊断。

## r4 tests 与严格验证

| 检查 | 终态 |
| --- | --- |
| EditMode job `ba4fa7829b6b40edaa2ea5f1dcc706e9` | 32/32 passed；0 failed；0 skipped；1.0762049 s |
| PlayMode job `8a162504409a4f06b6ec588fcf88eaf8` | 3/3 passed；0 failed；0 skipped；1.2065439 s |
| 编译／Console | 固定 Editor ready；0 error／0 warning |
| 严格 verifier（真实 r4） | exit 0；20/20；CSV 统计重算与完整合同通过 |
| verifier 负向测试 | 有效副本 1/1 接受；CSV、summary、config、identity hash、duplicate index、environment、extra artifact、missing index 共 8/8 拒绝 |

## r4 主序列与开销聚合

main 10/10 与 overhead 10/10 均 completed／correctness pass／measurement valid／process success／exit 0，且每轮 1800/1800 samples。聚合只使用每轮统计，不拼接 frames。

| group | p50 median / range / MAD / IQR ms | p95 median / range / MAD / IQR ms |
| --- | --- | --- |
| idle-60fps | 16.667601 / 16.667200–16.668100 / 0.000300 / 0.000400 | 17.003506 / 17.003000–17.004204 / 0.000499 / 0.000600 |
| known-load-60fps | 22.539700 / 22.519650–22.747150 / 0.020050 / 0.029351 | 23.009315 / 22.955160–23.838230 / 0.036245 / 0.053296 |
| recorders-on-uncapped | 0.125000 / 0.123500–0.125400 / 0.000400 / 0.000600 | 0.142605 / 0.140520–0.146215 / 0.002085 / 0.004130 |
| recorders-off-uncapped | 0.124800 / 0.124400–0.126000 / 0.000100 / 0.000200 | 0.142700 / 0.140900–0.154515 / 0.001800 / 0.004500 |

known-load p50 明显高于 idle，只证明仪器能分辨预置恒定负载；它不构成产品优化比较。recorders on/off p50 和 p95 范围重叠，performance comparison 保持 `inconclusive`，不能声明零开销。

## r4 Player fail／invalid／编排旁证

| run／sidecar | 终态 | 关键结论 |
| --- | --- | --- |
| `m0-04-cal-main-idle-r1-20260905T060510Z` | failed / prepare_failed / not_assessed / exit 1；6 文件、无 CSV | 采样前失败不伪造样本；summary SHA `EEA41C9A…` |
| `m0-04-cal-main-idle-r1-20260905T060547Z` | completed / required_metric_unavailable / invalid / exit 3；1800 samples | invalid 完整导出但不等于 process success；summary SHA `3F4EA7C4…` |
| `m0-04-cal-main-idle-r1-20260905T060725Z` | completed / sample_shortage / invalid / exit 3；1 sample | 两阶段 fault index 保留精确已测前缀；summary SHA `2D6C7ECC…` |
| `m0-04-cal-main-idle-r1-20260905T060200Z-orchestration-failure.json` | 1 s timeout；只终止已启动 PID 6564；退出后再次查询无该进程 | sidecar 记录 `wall_clock_timeout_process_terminated`、exit -1、log、身份；SHA `C15F6B80…` |
| `m0-04-cal-main-idle-r1-20260905T060304Z-orchestration-failure.json` | export fault；Player exit 1；无 summary/run 目录 | 外层仍记录 `summary_missing` + `diagnosticFault=export_failure`、PID 29580、log 与身份；SHA `E54AE290…` |

首次 timeout 试跑 `20260905T060049Z` 暴露 sidecar 对 PowerShell nullable 值错误使用 `.Value`，仅留下 Player log；Player 已终止。修复为显式整数转换后用新 run-id `060200Z` 重跑并通过预期失败合同。该首次失败保留，不删除、不计为成功证据。

## r4 产物集合哈希

每个 hash 对严格验证后的 run 内七文件按固定文件名计算；任一 artifact 改动都会改变集合哈希。

| run | artifact-set SHA-256 |
| --- | --- |
| main idle r1 | `5218250ADF70547808E26E60F75919AD9D01FE19ED9A17252DB9C1F6F6687917` |
| main idle r2 | `9B510681D5BD16E8E1E5A4CC8068846B2D605D86C979E129FA1FB65B8C06EE03` |
| main idle r3 | `F6B26D1E3804AB984BA329FAC4558CB026B1B38E627C8ABEC63E792564AE9AB3` |
| main idle r4 | `80F2F3A16893BCE83BB14A2391CDCDBA935781095EF985B7A1450132CB57683C` |
| main idle r5 | `EF941CAF544599D686EA1822164CEEEE34F0052C2641F54C10C3A9D6130828E4` |
| main load4m r1 | `7CB62894E03AFA7122E21E85DAED17A01A9DDD831029B10490372D1547B2E899` |
| main load4m r2 | `F85709D44A12F73AAC6D9B3339D7F53619A2FBF3DA3E7CCE326410002DEA7AB6` |
| main load4m r3 | `339BCBE0C242B378B8A9DC91C5A28B0520C876490C10D980E69A6E805FACC19A` |
| main load4m r4 | `672C126013EF7FB5E286911F95B9F832EE9170AD92230E098CA5673EAD1BDA55` |
| main load4m r5 | `BB619D270D813619CE63C3A90A9044960E26DF9E891033A514E8EEA8DCDE8007` |
| overhead on r1 | `BA9276ACC53759BC5C4BC6D01195CD74299466046BAC16D9D76D53286B456EA0` |
| overhead on r2 | `456649B5A7F08EF177931D8FE41A8819A071C143101A9997C9C7703D87A0B0D4` |
| overhead on r3 | `0DD2E08ED52576F4AA51A9186AB33F8C8CD081666609A4A651AC16CB06FF438F` |
| overhead on r4 | `8FF834158A65FFA87CECBFFBC7973ADE79BE8DCCC8DB61A18A4ED15F9BD1FB96` |
| overhead on r5 | `F12EACB54402BEE6EECDF42271A70BCA7056CE0D1D9E148BDF4F34D88EE8774B` |
| overhead off r1 | `EBE7BD7B31CBA0AD40237DA9F2F70DFDAF3C9A7FFED56E75B934CB0DB9B13938` |
| overhead off r2 | `59D1D91848C516B0B59906764B514B6D25E8E88F0D86D3B637B4651A22D75D15` |
| overhead off r3 | `E2518085347ABB01294049B39E78D19692246AD4719B4AAD97DD3AC044FD8E4E` |
| overhead off r4 | `D53350270CF3E5AD2B6BA376ED4D16A48F83A0CC10E38F1CA113B4DF8A844046` |
| overhead off r5 | `C7797E5FF323C5C174CD9E314B583B170E96E22F16EE511507D9932F506C9BC0` |

## Superseded r3 report

以下 r3 数据按当时 compact-JSON config hash 规则自洽，且恒定负载敏感性观察仍有诊断价值；但后续审查发现 action/sample 一帧错位和 verifier 强度不足，因此 r3 不再代表 M0 stage exit，也不能用于逐帧动作归因。

## 精确候选身份

- candidate：`m0-04-calibration-20260904T234357Z-25f3a323-dirty-r3`
- source revision：`25f3a323e54f536f3e77fda94e117f05a756c9c1-plus-m0-overlays`；dirty calibration，未 commit
- build：`m0-04-runner-dev-20260904T234357Z`；Unity 2022.3.45f1c1；Windows x64／Mono／Development
- BuildReport：Succeeded；0 errors；0 warnings；126,087,309 bytes；22.2836004 s
- build-summary SHA-256：`01505ADBE44D1785EAB918A5D9FE51062597BD103211FB72972044D6B505288B`
- launcher EXE SHA-256：`2A6C58DA77A27ACBC350D259B08E7FB1786454EEF2C30BA3D7700D6877941F62`
- Runtime DLL SHA-256：`8F3238F643FE9A21AD64F0DFEE93A23AF13370D3E182972B353D1E4F28F6DF12`
- 本机环境：Windows 10 64-bit；AMD Ryzen 5 5600G；12 logical processors；AMD Radeon RX 9070；Direct3D 11；960×540；High Fidelity；VSync 0。

Unity launcher EXE 在不同脚本 build 间可能相同，不能单独证明代码身份；Runtime DLL、build summary、源码候选与逐轮 identity 一起构成身份链。

## 运行前冻结

- 主序列：idle 与 known-load 各 5 次，target 60，固定顺序 `I1,L1,L2,I2,I3,L3,L4,I4,I5,L5`。
- 开销序列：uncapped idle，recorders on/off 各 5 次，固定 `ABBA,ABBA,AB` 结构。
- 每轮 300 warmup、1800 measure、capacity 1800，独立 Player 进程。
- known-load：每帧 4,000,000 CPU iterations + 32,768 bytes allocation；只用于验证仪器敏感性。
- required：Frame Interval；optional：Main Thread、GC Allocated In Frame、System Used Memory。当前 optional recorder 没有 usable samples，保持 unavailable/null。
- 每轮保留 p50/p95/p99/max/over-budget；跨轮只聚合每轮统计，不拼接逐帧样本。
- correctness、measurement validity、performance comparison 分开；known-load 不生成优化结论，recorders 开销只有可从噪声分离时才判断方向。

## r3 正式主序列

stamp：`20260904T234600Z`。

| run | Case | p50 | p95 | p99 | max | over-budget |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| idle r1 | idle | 16.689151 | 17.005620 | 17.031224 | 17.083799 | 0.876667 |
| load4m r1 | known-load | 22.711800 | 23.335609 | 23.872706 | 26.120700 | 1.000000 |
| load4m r2 | known-load | 22.708001 | 23.301626 | 23.997264 | 31.266000 | 1.000000 |
| idle r2 | idle | 16.686850 | 17.005905 | 17.038345 | 17.313700 | 0.864444 |
| idle r3 | idle | 16.683450 | 17.003000 | 17.021208 | 17.093200 | 0.878333 |
| load4m r3 | known-load | 22.744849 | 23.376280 | 23.819212 | 25.402499 | 1.000000 |
| load4m r4 | known-load | 22.750850 | 23.390540 | 24.085471 | 25.405999 | 1.000000 |
| idle r4 | idle | 16.691250 | 17.006020 | 17.036429 | 17.073600 | 0.884444 |
| idle r5 | idle | 16.683050 | 17.005401 | 17.042535 | 17.104501 | 0.881667 |
| load4m r5 | known-load | 22.723700 | 23.301320 | 23.660955 | 25.115600 | 1.000000 |

| group | metric | median | min–max | MAD | IQR |
| --- | --- | ---: | ---: | ---: | ---: |
| idle-60fps | p50 ms | 16.686850 | 16.683050–16.691250 | 0.003400 | 0.005701 |
| idle-60fps | p95 ms | 17.005620 | 17.003000–17.006020 | 0.000285 | 0.000504 |
| idle-60fps | p99 ms | 17.036429 | 17.021208–17.042535 | 0.005205 | 0.007120 |
| idle-60fps | max ms | 17.093200 | 17.073600–17.313700 | 0.011301 | 0.020701 |
| load4m-60fps | p50 ms | 22.723700 | 22.708001–22.750850 | 0.015699 | 0.033049 |
| load4m-60fps | p95 ms | 23.335609 | 23.301320–23.390540 | 0.034289 | 0.074655 |
| load4m-60fps | p99 ms | 23.872706 | 23.660955–24.085471 | 0.124558 | 0.178052 |
| load4m-60fps | max ms | 25.405999 | 25.115600–31.266000 | 0.290399 | 0.718201 |

10/10 run 均 completed／correctness pass／measurement valid／process success／exit 0，1800/1800 samples，七文件完整。known-load 明确提高帧间隔，证明协议能发现预置负载；该对照用于校准，不构成产品优化百分比。60 FPS idle 的 over-budget 比例受 16.6666667 ms 边界与帧率节拍影响，不等价于业务 CPU 超预算比例。

## r3 Recorders 开销序列

stamp：`20260904T235311Z`。

| group/run | p50 | p95 | p99 | max |
| --- | ---: | ---: | ---: | ---: |
| on r1 | 0.139800 | 0.175505 | 0.194501 | 1.417200 |
| on r2 | 0.140250 | 0.179805 | 0.201100 | 1.461600 |
| on r3 | 0.141900 | 0.196105 | 0.212402 | 1.355200 |
| on r4 | 0.139600 | 0.175130 | 0.194808 | 1.320900 |
| on r5 | 0.141000 | 0.183920 | 0.209102 | 1.426100 |
| off r1 | 0.141600 | 0.195400 | 0.215008 | 1.256400 |
| off r2 | 0.139800 | 0.177010 | 0.206820 | 1.278300 |
| off r3 | 0.138700 | 0.173210 | 0.192805 | 1.220300 |
| off r4 | 0.140400 | 0.179600 | 0.199201 | 1.197800 |
| off r5 | 0.140800 | 0.188605 | 0.212300 | 1.305500 |

| group | p50 median / range / MAD / IQR ms | p95 median / range / MAD / IQR ms |
| --- | --- | --- |
| recorders on | 0.140250 / 0.139600–0.141900 / 0.000650 / 0.001200 | 0.179805 / 0.175130–0.196105 / 0.004300 / 0.008415 |
| recorders off | 0.140400 / 0.138700–0.141600 / 0.000600 / 0.001000 | 0.179600 / 0.173210–0.195400 / 0.006390 / 0.011595 |

10/10 run 均 valid。on/off 的 p50 median 相差 -0.000150 ms，逐轮范围重叠；p95 也重叠。performance comparison 为 `inconclusive`：当前设计未检测到可从轮间噪声中分离的 recorder 开销，但不能宣称“零开销”。

## r3 失败与 invalid 反例

| run | 进程／terminal | validity | samples／files | 结论 |
| --- | --- | --- | --- | --- |
| `m0-04-r3-prepare-fail-20260904T235500Z` | exit 1／failed，prepare_failed | not_assessed | 0；六文件、无 samples.csv | 采样前失败未伪造样本；summary SHA-256 `652BFC92D30F51B86AA5E9C387F3EB6EB393923DD8CC7D065C5EAAD7C2831659` |
| `m0-04-r3-required-invalid-20260904T235500Z` | exit 3／completed，required_metric_unavailable | invalid | 20；七文件 | invalid 可完整导出但不是 process success；summary SHA-256 `B65B0771CE19CC3024799985F123653A55C073FA54CC7392F6FE67DCCE3A1D06` |

EditMode 28/28 覆盖 fault/terminal/cleanup/export/focus/pause、Release fault 拒绝且保留既有帧率设置，以及四种 measure-trigger fault 越界拒绝；PlayMode 2/2 覆盖 Smoke 生命周期与 Host 正常 run。

## r3 产物集合哈希

每个 hash 对 run 内七文件按文件名排序后的 `filename|file-sha256\n` 计算；复算入口为 `Tools/Benchmarking/Get-XUILabM0CalibrationSummary.ps1`。

| run | artifact-set SHA-256 |
| --- | --- |
| main idle r1 | `54B3E4B04705FA86242C4C478C08936617AAECE656E3EF280EAC199DDBC32042` |
| main idle r2 | `EBDB74CE70E59B5943510CB3041D3AA0BD814451FD1754F9EE869EC9571A99BF` |
| main idle r3 | `62B4C0BF3BE24061CA809C383C3C6F2CE536C6A9BB309EF71576A8E0B5CC625D` |
| main idle r4 | `8488E74649221287A1E9206AE2326876A43B2C2BEA898A5377720CBED78EEAD4` |
| main idle r5 | `9C5322935D666391D1179AD1D5EC1627101825CFB7765B7DD2C1E031F1A50075` |
| main load4m r1 | `6133E59905DD8B1F8EB2AE4EE36938649B44611278344F613D4FC8E855D5C548` |
| main load4m r2 | `9FC0B28554DDEB3A99FF68FF075F65433603CC71F1CACA721F17CC6538602545` |
| main load4m r3 | `5C99476B5A28F60C40A0D0ED66E230BED4A039957F2A69338DEACD6BEAF9404C` |
| main load4m r4 | `233D5AB1FA759D8BD2CBED9F418CECE5E933D8ADF3013BDBD5E7D56DFABA1C28` |
| main load4m r5 | `69647C1EB082B29F14F3444004653252EE628CA450D3BFFDEE6F3A6EFF45A660` |
| overhead on r1 | `B989C9ECB7C642137D3A885F2BAA990489C7EDC5EE4EFB4FF21754BEA0548961` |
| overhead on r2 | `B6809080642E002DEA01737E5300C3D6B22F1B5F196E4C2D25042440D4E584B5` |
| overhead on r3 | `39D2821A32E0F52538D22DD2FFCEC1FBEEAC8F55A99CA7027B34CE3AFF076B88` |
| overhead on r4 | `370798CA4D849BC1E66563DDCC5B770C5CE771CEC16114113E74C61C0E7645D2` |
| overhead on r5 | `4901D3B3F4209EC17EED69F8B842B3E0A5D432F4EA09FC2900076B9FC7D20C7C` |
| overhead off r1 | `A259727B24AE58FCBF27EA6C54AFB72ADC1981E42F97BDE97A30009D562CC2AF` |
| overhead off r2 | `B40E2D9422CA420315CFFC33D1C2F87740655AA05E30E3F0A336200A26685CB8` |
| overhead off r3 | `2D0A21200B028A0BF45D728A65950187BBDF50D84A3EBEEF499AC56EAA90214C` |
| overhead off r4 | `AC67A9B0596828B09FE9DF508132999CA2EED75FFFD6B44FB909ABE9BE86FCA0` |
| overhead off r5 | `0A1F6CCC67EE66B19B29C39A8977D2E1E8DEBEA1C57C7F1CB98F33B44E90DFDC` |

## Superseded 证据与限制

- r1 build/stamps 在自审发现 placeholder identity 与 terminal summary 发布顺序问题后 superseded；原始产物保留，不计入正式聚合。
- r2 candidate 在独立复核发现 Release 设置恢复与 measure-trigger 越界两个缺陷后被判 `rework`；r2 build、20 个 run 与 failure 反例均保留但不作为最终候选。r2 load4m 的双峰仍提示调度敏感性，后续 A/B 必须查看逐轮顺序、IQR，并允许 `inconclusive`。
- r3 曾完成当时合同的重建与完整重跑，但后续 changes request 证明该合同不足；数据保留为 historical，不作为当前出口。
- Frame Interval 包含帧率节拍和整帧等待，不能命名为主线程 CPU 时间；分配字节不等于 GC 回收；System Used Memory 不是存活对象所有权证明；optional counter unavailable 时只能缩小结论。
- M0 得到的是 Development／Mono、本机、当前 dirty candidate 的协议校准，不代表 Release／IL2CPP、其他硬件或未来 UI Case 的正式结果。
- 整个 `Artifacts/` 由根 `.gitignore` 忽略并保持本机未跟踪；迁移本机目录前必须凭本表哈希复核。

## 三层结论

- correctness：20 个 final r5 calibration run 均 pass；32 EditMode／3 PlayMode 与实际 Player fail/invalid 保持可信。r7 完整 summary 编排矩阵为合法 10/10 接受、21/21 负向拒绝；独立 review accept，stage pass。
- measurement validity：20 个 final r5 run 均 valid，并通过严格 JSON 类型／有限性、CSV 重算与完整合同 verifier；optional counters 诚实记录 unavailable，不影响 required Frame Interval。
- performance comparison：idle/known-load 为 `not_assessed`；recorders on/off 为 `inconclusive`。没有发布 UI 优化百分比。
