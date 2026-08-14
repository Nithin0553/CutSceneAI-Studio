# Generated-performance experiment v0.1 acceptance

This gate measures first-pass reliability, deterministic repeatability, cross-engine portability,
and native realization without allowing missing or failed attempts to disappear from the result.
It is an evidence ledger and verifier; it does not claim that synthetic fixtures are model or engine
results.

## Fixed paper design

Paper mode requires:

- exactly 10 planned scenes;
- exactly 5 unique seeds, producing 50 first-pass attempts;
- no manual repair in an attempt counted as successful;
- three clean runs for every selected repeatability case;
- one unchanged Generated Performance bundle supplied to Unreal Engine 5.8 and Unity 6;
- body, facial, generated-camera, and audio realization in both engines;
- save, editor restart, native readback, and a complete render in both engines;
- strict parity with both engines required, all four modalities required, zero errors, and zero
  missing-realization warnings.

The plan records minimum rates before evidence is evaluated. Defaults are 100% for first-pass
reliability, repeatability, portability, and native realization. Lower targets must be an explicit
predeclared research choice; they do not change the measured counts.

## Attempt accounting

The required first-pass key space is the Cartesian product of every planned scene and seed at
`repeat_index: 1`. Each selected repeatability case adds `repeat_index: 2` and `3`; run 1 is reused
as the first of its three comparisons.

A failed generation is still a valid observation when it carries a failure code. It receives no
artifact, portability, native-realization, or reliability credit and remains in every applicable
denominator. Duplicate, missing, unexpected, wrong-scene, or wrong-CIR records make the evidence
set incomplete.

## Evidence invariants

Every completed attempt records deterministic SHA-256 digests for the source bundle, generation
plan, package manifest, body artifacts, facial artifacts, camera artifacts, and audio artifacts.
Each engine record must preserve the same source-bundle digest and retain mapping, editor log,
readback, canonical timeline, and render-manifest digests.

Native realization succeeds only when both engine records prove:

- import, save, restart, readback, and render completion;
- the exact expected rendered frame count;
- no editor errors and no missing-realization warnings;
- exact expected section counts for body, facial, camera, and audio;
- zero placeholder sections;
- source artifact digests equal to the package digests;
- one retained native target reference per expected section.

Portability succeeds only when both engines consume the same bundle and the nested parity report
requires Unreal and Unity plus all four modalities, uses the planned frame tolerance, preserves the
planned CIR fingerprint, and has zero errors and warnings.

Repeatability succeeds only when all three clean same-seed runs pass native realization and
portability, produce identical package artifact digests, and preserve each engine's mapping and
canonical timeline fingerprints.

## Run the verifier

Create JSON documents that validate against the committed plan and attempt schemas, then supply
every attempt explicitly:

```powershell
python -m cutsceneai_parity experiment-verify `
  .\evidence\experiment.plan.json `
  --attempt .\evidence\scene-01-seed-01-run-1.evidence.json `
  --attempt .\evidence\scene-01-seed-01-run-2.evidence.json `
  --attempt .\evidence\scene-01-seed-01-run-3.evidence.json `
  --output .\evidence\experiment.report.json
```

Repeat `--attempt` for the complete planned key space. Exit code `0` means the declared rate targets
and structural gates passed. The report contains the planned, observed, and passed count for each
metric so the denominator is auditable.

## Harness mode versus paper mode

Use `mode: harness` for small synthetic fixtures and CI. A successful harness report proves that
schemas, accounting, hashing comparisons, failure handling, and aggregation work, but always emits
`publishable: false`.

Use `mode: paper` only for retained real inference and real editor evidence. Paper mode rejects
`evidence_origin: synthetic` and cannot pass unless all 50 first-pass records and selected repeat
runs are present. Changing a label from synthetic to real is not evidence; the referenced bundles,
logs, readbacks, native targets, render manifests, and their digests must be retained for audit.

## External-SSD boundary

The contracts, schemas, aggregator, synthetic fixtures, and native editor automation can be built
without the external SSD. Running the paper plan requires the deferred model runtime, checkpoints,
SMPL assets, and retained inference outputs, so it remains blocked until the verified external SSD
is available.
