# M4 展示数据复现入口

本页把已冻结的 130 次有效运行、离线验收、重新建根目录和图表/媒体复跑分开说明。当前候选是 `m4-final-b017672`，源码提交为 `b0176724d58c7cda86b472340845d239714888d0`，输入清单为 391 项。本文这次只补充复现说明，没有重跑 Unity、Player 或已有矩阵命令。

## 现有数据身份

| 主题 | 运行数 | 计划与门禁 | 原始运行根 | 构建清单 |
| --- | ---: | --- | --- | --- |
| List | 50 | [`list-matrix-plan-r1.json`](../../Artifacts/m4-final-validation/list-matrix-plan-r1.json) / [`list-preflight-r1.json`](../../Artifacts/m4-final-validation/list-preflight-r1.json) | [`m4-list-accepted-r1`](../../Artifacts/m4-list-accepted-r1/) | [`m4-list-build-manifest-r1.json`](../../Artifacts/m4-list-build-manifest-r1.json) |
| Gradient | 80 | [`gradient-matrix-plan-r2.json`](../../Artifacts/m4-final-validation/gradient-matrix-plan-r2.json) / [`gradient-preflight-r1.json`](../../Artifacts/m4-final-validation/gradient-preflight-r1.json) | [`m4-gradient-runs-r2`](../../Artifacts/m4-gradient-runs-r2/) | [`m4-gradient-build-manifest-r2.json`](../../Artifacts/m4-gradient-build-manifest-r2.json) |

列表的 50 次接受根是原始 14 次和恢复 36 次经哈希绑定后的字节副本；原始 timeout 仍在 [`m4-list-runs-r1`](../../Artifacts/m4-list-runs-r1/)。渐变错误入口的三文件失败记录仍在 [`m4-gradient-runs-r1`](../../Artifacts/m4-gradient-runs-r1/)。它们是审计材料，不应复制成成功运行或混入统计。

## 离线验收已有 130 次运行

从仓库根目录执行。`$out` 只放新报告；不要把它指向现有 `Artifacts/m4-final-validation` 或运行根。

```powershell
$out = 'Artifacts/m4-replay-20260910'
@(
  $out,
  "$out/list-verification.json",
  "$out/list-report",
  "$out/gradient-report.json"
) | ForEach-Object { if (Test-Path -LiteralPath $_) { throw "Replay output already exists: $_" } }
New-Item -ItemType Directory $out | Out-Null

python -B Tools/ListLab/refresh_verify.py `
  --plan Artifacts/m4-final-validation/list-matrix-plan-r1.json `
  --runs Artifacts/m4-list-accepted-r1 `
  --gate Artifacts/m4-final-validation/list-preflight-r1.json `
  --build-manifest Artifacts/m4-list-build-manifest-r1.json `
  --output "$out/list-verification.json"

python -B Artifacts/m4-final-validation/list_subset_report.py `
  --plan Artifacts/m4-final-validation/list-matrix-plan-r1.json `
  --runs Artifacts/m4-list-accepted-r1 `
  --gate Artifacts/m4-final-validation/list-preflight-r1.json `
  --build-manifest Artifacts/m4-list-build-manifest-r1.json `
  --output "$out/list-report"

python -B Tools/GradientLab/adaptive_report.py `
  --plan Artifacts/m4-final-validation/gradient-matrix-plan-r2.json `
  --runs Artifacts/m4-gradient-runs-r2 `
  --gate Artifacts/m4-final-validation/gradient-preflight-r1.json `
  --build-manifest Artifacts/m4-gradient-build-manifest-r2.json `
  --policy Artifacts/m4-final-validation/gradient-policy-r2.json `
  --policy-sha256 05812a0d9343503da4032f4f86da51148c5eca11d977f29ebd0145681128282f `
  --output "$out/gradient-report.json"
```

`refresh_verify.py` 检查 List 收据、raw 文件、运行控制哈希和冻结的 build/gate。`list_subset_report.py` 在生成 JSON/Markdown/CSV 前再次调用 List verifier。`adaptive_report.py` 检查全部 80 个 Gradient 收据和 raw run，包括质量与拓扑路径，再重建报告。预期结果是 List `status=pass`、50 runs；Gradient `status=pass`、80 runs。这些命令只读取已有文件，不启动 Player。 `refresh_acceptance.py` 是面向旧 v1 收据的补充入口，当前 M4 v2 收据不使用它。

如果离线审计需要一个新的 List 聚合根，使用仓库的字节复制合并工具。它会先核对原始 14-run 前缀和恢复 36-run 后缀，再写入新根；不会创建新的 run identity：

```powershell
python -B Artifacts/m4-final-validation/list_recovery_merge.py `
  --plan Artifacts/m4-final-validation/list-matrix-plan-r1.json `
  --gate Artifacts/m4-final-validation/list-preflight-r1.json `
  --build-manifest Artifacts/m4-list-build-manifest-r1.json `
  --original-runs Artifacts/m4-list-runs-r1 `
  --recovery-runs Artifacts/m4-list-runs-recovery-r1 `
  --recovery-policy Artifacts/m4-final-validation/list-recovery-policy-r1.json `
  --recovery-policy-sha256 fbd5fee1257faee294475cf64c188d94cd91f1a8e46bf43cd86969904a49b40e `
  --output-runs Artifacts/m4-replay-20260910/list-accepted-r2 `
  --output Artifacts/m4-replay-20260910/list-merge-r2.json
```

Gradient 的 receipt 和 launch command 把 `--xuilab-output-root` 绑定到原始绝对 run root。因此直接复制 `m4-gradient-runs-r2` 不是 `adaptive_report.py` 可接受的新 root；离线验证应继续使用原 root，或者用新的 plan、build 和 run root 真正开启新 campaign。

## 新建构建、计划和运行根目录

只有确实要启动新的 Player campaign 时才使用这条路径。新的 `buildId` 不只是换一个标签：新构建必须对应新的 Unity 构建操作和新的 Player 目录，并且清单中的文件哈希、源码输入、候选身份、源码修订版和日志哈希必须全部一致。现有的 `prepare_campaign.py` 和 `prepare_gradient_r2.py` 是绑定冻结身份的 campaign 专用准备脚本；不要原地修改旧清单，也不要复用旧构建操作。

新的 Development 构建、门禁证据和清单准备好后，再生成新的冻结计划。List CLI 接受选定的 `normal`/`virtual` 与 `high`/`batch` 组，并生成 50 次运行：

```powershell
python -B Tools/ListLab/refresh_plan.py `
  --output Artifacts/m4-replay/list-matrix-plan-r2.json `
  --plan-id m4-list-replay-r2 `
  --candidate <new-candidate-id> `
  --build <new-list-build-id> `
  --source <new-source-revision> `
  --dirty false `
  --gate Artifacts/m4-replay/list-preflight-r2.json `
  --build-manifest Artifacts/m4-replay/m4-list-build-manifest-r2.json `
  --backend normal virtual `
  --profile high batch
```

Gradient CLI 生成完整的 80 次 fixed32/adaptive64 矩阵：

```powershell
python -B Tools/GradientLab/adaptive_plan.py `
  --output Artifacts/m4-replay/gradient-matrix-plan-r3.json `
  --plan-id m4-gradient-replay-r3 `
  --candidate <new-candidate-id> `
  --build <new-gradient-build-id> `
  --source <new-source-revision> `
  --dirty false `
  --gate Artifacts/m4-replay/gradient-preflight-r2.json `
  --build-manifest Artifacts/m4-replay/m4-gradient-build-manifest-r3.json `
  --contract Docs/Experiments/GRADIENT_CONTRACT.md `
  --protocol Docs/Experiments/GRADIENT_ADAPTIVE_PROTOCOL-r1.md
```

只有新计划通过各自的 validator 后，才能把新的根目录交给 launcher。启动命令是 `Tools/ListLab/refresh_launch_v2.py` 和 `Tools/GradientLab/adaptive_launch.py`；两者都需要 `--plan`、`--runs`、`--gate`、`--player`、`--build-manifest`、`--repo`，Gradient 还需要 `--policy` 和 `--policy-sha256`。示例根目录为 `Artifacts/m4-replay/list-runs-r2` 和 `Artifacts/m4-replay/gradient-runs-r3`。这些根目录必须是新的、没有 reparse point 的目录，不能保留其他计划留下的 intent、failure、receipt 或 log。启动任一命令都属于 Player 操作，不在上文离线复现范围内。

## 重建图表和媒体

当前图表和媒体脚本是已经审阅过的入口，但没有提供输出路径参数；输入根目录和输出根目录都写在脚本常量中：

- [`generate_graphics_r2.py`](../../Artifacts/m4-final-validation/generate_graphics_r2.py) 读取冻结的 List/Gradient 报告和三张 Release smoke PNG，然后写入 `Artifacts/m4-final-media/graphics-r2`；它以 `exist_ok=False` 创建输出目录。该 Python 图形脚本需要 Matplotlib。
- [`render_graphics_r3.cjs`](../../Artifacts/m4-final-validation/render_graphics_r3.cjs) 读取 `graphics-r2/*.svg` 并写入 `graphics-r2/rendered-r1`；如果整个输出根目录已经存在，它会直接抛错。该 Node 脚本需要 Sharp。
- [`encode_media_r1.py`](../../Artifacts/m4-final-validation/encode_media_r1.py) 读取现有的三个 `*-video-r1` 帧目录并写入 `videos-r1`；FFmpeg 使用 `-n`，因此不会替换已有 MP4。这是已有 PNG 帧时的纯媒体复现；[`capture_release.py`](../../Artifacts/m4-final-validation/capture_release.py) 是单独的 Player 捕获入口。
- [`media_contact_r1.cjs`](../../Artifacts/m4-final-validation/media_contact_r1.cjs) 读取视频帧目录，并在 `videos-r1` 下写入 contact sheet；重复执行时使用新的 base/output 根目录。

这些脚本当前使用机器本地的依赖路径。把脚本移到另一台机器或另一个仓库位置时，必须相应调整这些路径；Python 图形脚本需要可用的 Matplotlib，Node 脚本需要可用的 Sharp。

要根据新生成的离线报告复现图表，请把相关脚本复制到新的版本化位置，并同时修改输入报告路径、截图路径和输出根目录。复制后的 Python 脚本使用 `python -B` 运行，复制后的 renderer 使用 `node` 运行。保持原有的 `graphics-r2`、`rendered-r1`、`videos-r1` 和清单不变。新的图表清单必须记录复制后 generator 的哈希和精确的报告哈希；新的视频清单必须记录帧 receipt 哈希和完整解码结果。

## 输出冲突与身份规则

每次复现输出都使用新的后缀，例如 `m4-replay-20260910`，并在开始前检查所有目标路径：

```powershell
@(
  'Artifacts/m4-replay-20260910',
  'Artifacts/m4-replay-20260910/list-verification.json',
  'Artifacts/m4-replay-20260910/list-report',
  'Artifacts/m4-replay-20260910/gradient-report.json'
) | ForEach-Object { if (Test-Path -LiteralPath $_) { throw "Replay output already exists: $_" } }
```

Python 证据写入器使用排他式文件创建或 `exist_ok=False`；launcher 会拒绝不完整或属于其他计划的 run 条目；媒体/打包脚本使用固定根目录，其中一些还启用了防覆盖参数。不要删除旧根目录来容纳复现，不要让新计划指向旧 run ID，也不要在任何 receipt 产生后修改 plan/build/gate。新的构建身份必须对应新的构建操作、清单、计划、policy 和运行根目录；原有 130 次运行证据继续作为对照记录。

最终生成的离线报告应从新的 review record 链接，并记录其 SHA-256 值。当前已发布的数字及其边界仍以 [RESULTS](RESULTS.md)、[EvidenceIndex](EvidenceIndex.md) 和 [RUN_INDEX](RUN_INDEX.md) 为准。
