# Gradient Lab offline benchmark tooling

This directory contains the offline part of the Gradient Lab experiment. It
does not implement GradientEffect, TransitionController, mesh generation, or a
gradient evaluation function. Those remain an M2-01 Unity contract and must be
frozen by the owning task before Player evidence is accepted.

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

The tools use only the Python standard library. They never start Unity or a
Player and do not write analysis output. JSON input rejects duplicate object
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
