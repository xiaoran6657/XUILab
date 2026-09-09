# Gradient Lab offline benchmark tooling

Tools/GradientLab contains generic offline contracts and the M2-04 Player execution/verification adapters. Unity implements GradientEffect, TransitionController and mesh generation; current acceptance is recorded in Docs/PM/Tasks/M2-04. The raw verifier independently recomputes the frozen Schlick quality curve.

## Files and commands

- Tools/GradientLab/gradient_experiment.py validates a plan, computes the
  declared wall-clock budget, validates explicit expected/actual RGBA samples,
  computes fixed percentiles and dispersion, and gates comparisons.
- Tools/GradientLab/gradient_recovery.py performs a read-only inspection of a
  frozen plan and classifies each run as completed, failed, pending,
  interrupted, or invalid.
- Tools/GradientLab/test_gradient_tools.py contains targeted offline regression
  tests.

Run the tests from the repository root:

    python -B -m unittest discover -s Tools/GradientLab -p "test_*.py" -v

Inspect a plan and optional evidence:

    python -B Tools/GradientLab/gradient_experiment.py --plan plan.json --require-frozen --quality quality.json --results results.json

Inspect run directories without changing them:

    python -B Tools/GradientLab/gradient_recovery.py --root Artifacts/gradient-plan --plan plan.json

The two generic tools above use only the Python standard library. They never start Unity or a Player and do not write analysis output. The separate Player adapters below have explicit execution/output behavior and additional dependencies. JSON input rejects duplicate object
keys, non-finite constants, path reparse points, and unsafe identifiers.

## Plan contract

A plan has schema xuilab.gradient.plan/v1 and protocol
xuilab.benchmark.protocol/v1. Its top-level fields are:

    schemaVersion, status, planId, experimentId, protocolVersion,
    contractId, contractSha256, candidateId, buildId, sourceRevision, dirty,
    evidenceKind, budget, quality, comparison, artifacts, runs

status is draft or frozen. A draft is useful for structure and budget review
but cannot pass a quality or result gate. A frozen plan must carry an opaque,
non-empty contractId and a 64-character contractSha256; this module never
invents either value or interprets the hash.

evidenceKind is either fixture or windows-development-player. Fixture results
are useful for deterministic tool checks and remain separate from Windows
Player results. dirty remains part of candidate identity.

Each run declares a safe runId, groupId, caseId, variant, runIndex,
plannedRepeatCount, warmupFrames, measureFrames, sampleCapacity,
frameBudgetMs, timeoutSeconds, and an opaque JSON parameters object. Group
indexes must be exactly 1..plannedRepeatCount and all runs in a group must
carry the same case, variant, repeat count, and parameter digest.
totalWallClockSeconds must cover every declared timeout. identity.json and
summary.json are required artifact names because recovery needs them.

The optional comparison rule is deliberately explicit:

    rule = "disjoint_range_and_mad"

For the chosen metric, two groups are inconclusive unless their min/max ranges
are disjoint and the median difference is greater than the sum of their MADs.
The rule is descriptive and exploratory; it is not a significance test.

## Quality contract

A quality document has schema xuilab.gradient.quality/v1 and stores explicit
reference samples:

    t, expectedRgba, actualRgba

t is strictly increasing in [0, 1]. RGBA channels are finite normalized values
in [0, 1]. colorSpace and alphaMode are required metadata. The implemented
metrics are rgba.max_abs, rgba.mean_abs, and rgba.rmse.
quality_metrics reports pass, quality_limited, not_ready, or not_assessed. A
pass requires a frozen contract identity and a matching plan. No color is
generated or evaluated by this tool; values must come from an approved fixture
or Runner adapter.

## Results and analysis gates

A results document has schema xuilab.gradient.results/v1 and one result for
every planned run. Its four identity fields must exactly match the plan.
frameIntervalMs is a non-empty finite array. Optional cost metrics are
provided as finite scalar or array values.

A run enters the analysis comparison only when state=completed,
correctness=pass, measurementValidity=valid, and qualityStatus=pass. Every
repeat in every comparison group must pass. Statistics use the fixed
percentile interpolation (n - 1) * p; each run is summarized first, then group
medians/minimums/maximums/MAD/IQR are computed. Frame samples from different
processes are never concatenated.

Missing optional cost metrics stay visible as
availability.costMetrics=unavailable with a reason. They are never replaced
with zero. Required metric or identity failures yield invalid or not_ready,
and comparisons are omitted.

The analysis output always sets executionEvidence=not_assessed. A successful
offline analysis does not grant a publishable or M2/M3 release conclusion:
Runner-native correctness, measurement validity, environment, build identity,
and quality evidence must be supplied by a future adapter and reviewed under
the Player benchmark protocol.

## Recovery classification

Recovery is inspect-only. For each frozen plan run, the root may contain a
directory named exactly by runId and the artifact names declared by the plan.
Unknown prefixed remnants, duplicate sidecars, malformed JSON, missing
artifacts, identity mismatches, and summary gate failures are invalid and
remain visible.

A valid failure sidecar (<runId>-failure.json or
<runId>-orchestration-failure.json) records a non-empty reason and produces
failed only when no run directory conflicts with it. An intent marker
(<runId>-intent.json or <runId>-resume-intent.json) produces interrupted and is
never auto-unlocked. No marker and no run directory is pending.

A completed run must contain identity fields matching planId, contractId,
contractSha256, evidenceKind, candidateId, buildId, and sourceRevision, plus
at least one complete artifact integrity proof:

- artifactSetSha256 is a digest of the canonical map of every declared
  non-identity artifact name to its SHA-256; or
- artifactSha256 maps every declared non-identity artifact name to its
  SHA-256.

The identity proof is checked against bytes on disk. Identity itself is
excluded from the map to avoid a self-referential hash. This is an offline
integrity check, not a signature or proof that the Unity run was valid.

The recovery report is safe to pass to a reviewer when it has no invalid or
interrupted runs. Failed runs remain failed; the tool does not retry, delete,
rewrite, or launch anything. A later execution adapter must use a new run
identity and the frozen plan.

## M2-04 Player adapters

- player_plan.py freezes all run IDs, geometry/actions, quality contract, preflight and build-manifest hashes before execution. The generic plan validator requires all Windows Player runs to share a valid buildManifestSha256.
- player_launch.py dispatches serial owned Player processes, with a repository-wide Artifacts/gradient-player.lock, durable intent, exit-code receipt, raw verification and no automatic redispatch of retained failures.
- player_verify.py independently validates the complete original all-pass matrix. It requires complete files, current run quality identity, real mesh topology, valid/correct terminal states, process success, raw statistics and all receipts. It does not convert missing or failed runs into pass. NumPy 2.3.5 was used for dense scans in M2-04.
- player_resume.py is a separately frozen orchestration addendum for the interrupted matrix. A policy binds the script SHA, recovery protocol SHA, original plan and build. It never retries a failed run or unresolved intent; verified timeouts defer subsequent repetitions of the same case. Other original run IDs continue in their original order. See [recovery rules](../Experiments/GRADIENT_MATRIX_RECOVERY-r1.md).
- player_matrix_report.py audits this partial matrix, retaining completed/timeout/deferred/not_run separately. Only groups with every originally planned repetition completed enter group statistics. The complete-plan status remains partial if any planned run timed out or was deferred. CLI exit 0 requires the whole matrix to be complete; a partial report is still written but returns exit 1. Read status/counts and the task review.

Example new-run dispatch (paths are repository-relative):

    python Tools/GradientLab/player_launch.py --plan Artifacts/gradient-player-r5/matrix-plan.json --runs Artifacts/gradient-player-r5/matrix-runs --gate Artifacts/gradient-validation/preflight-r5.json --player Artifacts/gradient-player-r5/build/XUILab-Gradient.exe --build-manifest Artifacts/gradient-player-r5/build-manifest.json --repo .

For a confirmed interrupted matrix use player_resume.py with the same arguments plus --policy <frozen-policy.json>; first inspect retained markers and PM. Do not use this example to redispatch an active or uncertain job. For reports use player_matrix_report.py with --plan/--runs/--gate/--build-manifest/--repo/--policy, a new --output directory, and optional --plot.

### Plot dependencies

The optional plot path uses Matplotlib 3.10.6. In this run, missing plotting packages were installed only under Artifacts/gradient-report-deps using the pinned requirements below and --no-deps; existing bundled NumPy/Pillow/packaging/python-dateutil/six were reused. No global Python installation was changed. Add that directory to the reporting process Python path only. Runtime sampling does not import Matplotlib.

    python -m pip install --target Artifacts/gradient-report-deps --no-deps -r Tools/GradientLab/requirements-plot.txt

A fresh environment must also provide NumPy, Pillow, packaging, python-dateutil and six. Exact actual dependency versions are saved with the generated report. Charts are SVG and PNG artifacts; visual inspection runs after all sampling.

## 历史M2基线

进入M3前使用freeze_baseline.py将原272项输入和Gradient证据冻结到新的Artifacts/baselines目录；该入口只适用于明确的M2 r5集合，不是任意候选打包器。它先执行当前source/build/gate检查，拒绝已有输出、活动Player锁和reparse，原始文件按字节复制后复核。

搬迁后使用归档自身的historical_verify.py，Python -B，输出在归档外新文件；先从可信交接核对baseline-manifest.json SHA。它验证原始绝对路径与记录中的repoRoot，使用归档的相对文件重新算raw质量/网格/帧时与跨轮统计，不访问原机器绝对路径、不改写journal、不重派Player，也不把partial改成全通过。详见[M2保全记录](../PM/Tasks/M2-04/BASELINE_PRESERVATION-r3.md)。

    python -B <archive>/Tools/GradientLab/historical_verify.py --archive <archive> --manifest-sha256 <trusted-manifest-sha256> --output <new-path-outside-archive.json>

原player_launch/player_verify的当前源码门禁保持严格；M3修改源码后不能用它们证明旧M2候选。历史核验退出0表示所声明的历史partial证据完整且可复算，须同时读matrixStatus/counts；不等于所有计划run都完成。
