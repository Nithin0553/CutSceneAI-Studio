# Generated Performance external-SSD gate

## Status

The external SSD became the mandatory next-step dependency on 2026-08-14. Contract, validation,
adapter, packaging, native-realization harness, evidence-collector, and experiment-ledger work is
complete. The next phase installs the large-model runtime and retains real inference outputs, so it
must not begin until the external SSD is connected and its explicit target path is verified.

This boundary prevents placeholder samples, pre-authored animation, or dry-run output from being
reported as generated-performance evidence.

## Non-SSD progress

| Work item | Status |
| --- | --- |
| Generated Performance Package contract | Complete |
| Deterministic CIR-to-generation-plan compiler | Complete |
| Canonical 22-joint body-motion contract and resampler | Complete |
| Canonical ARKit-52 facial/lip-sync contract and resampler | Complete |
| Canonical transform, filmback, and focal-length camera contract and resampler | Complete |
| Provider interfaces and canonical output normalization | Complete |
| Package assembly, hash/provenance verification, and archive/path safety | Complete |
| Unreal 5.8 and Unity 6 generated-artifact mappings | Complete |
| Four-modality strict readback and parity evidence contract | Complete |
| Reliability, repeatability, and portability experiment ledger and aggregator | Complete |
| Native Unreal/Unity realization, restart/readback, render, and evidence harnesses | Complete |

The non-SSD implementation gate is complete. Synthetic tests validate deterministic native harness
generation and the experiment aggregator only; they are permanently ineligible for paper evidence
and are not a substitute for retained editor or inference output.

## Work completed without the SSD

- Generated Performance Package and deterministic generation-plan contracts.
- Canonical body, facial, camera, and audio artifact schemas and validators.
- Exact-frame deterministic resampling and coordinate conversion.
- Provider interfaces, command construction, output parsing, and failure classification tested
  with small synthetic fixtures.
- Package assembly, file hashing, provenance checks, and archive/path safety.
- Unreal 5.8 and Unity 6 adapter compilation against canonical artifacts without changing CIR.
- Native Unity and Unreal import/save/restart/readback/render automation with strict target
  manifests, no-replacement preflight, and hash-anchored evidence collection.
- Reliability, repeatability, portability, and native-realization experiment harnesses.
- Documentation, CI, static analysis, schema drift checks, and automated unit/integration tests.

## Work blocked by the SSD

- Installing the full CUDA/PyTorch model environment and retaining its caches outside the system
  drive.
- Downloading and storing the selected official MDM checkpoint, HumanML3D-derived dependencies,
  and required SMPL conversion assets.
- Retaining real body, facial/lip-sync, and camera inference outputs for all experiment scenes and
  seeds.
- Running the final inference-backed package assembly, native engine import, restart/readback,
  render, reliability, repeatability, and portability evidence gates.

## Mandatory trigger

This trigger has been reached. Every non-SSD item above has an automated passing repository gate,
and the next work is to install/download the selected model runtime and execute retained real model
inference. Work stops before any checkpoint download until the user connects and prepares the
external SSD.

After the SSD is available, its explicit drive/path, free space, filesystem, and write access must
be verified before model installation. Checkpoints, caches, model assets, and inference outputs
must be directed to that verified path; no broad or inferred drive target is permitted.

## Evidence rule

Until the blocked work runs, repository artifacts may be described as contracts, plans, schemas,
fixtures, dry runs, or harnesses only. They are not evidence that generative animation inference,
native realization, or the paper's final experiment has passed.
