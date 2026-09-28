# CutSceneAI AMASS Research Pilot Runbook

Purpose: run the first real-human-motion target-turn pilot locally without committing AMASS data.

Important: AMASS is used only in the CutSceneAI `research` pool. Obtain it yourself under the current AMASS license before running this workflow.

## 1. Update the repository

```powershell
git checkout agent/cross-engine-parity-v0.1
git pull origin agent/cross-engine-parity-v0.1
```

## 2. Install the isolated training package

```powershell
python -m pip install -e ".\training[dev]"
```

## 3. Put AMASS outside Git

Recommended local layout:

```text
D:\Research\CutSceneAI-TrainingData\AMASS\
    CMU\...
    KIT\...
    ...
```

Do not copy source AMASS files into the repository. CutSceneAI also ignores `.cutsceneai-training-data/` if you prefer a repository-adjacent local working directory.

## 4. Start with a very small pilot

```powershell
cutsceneai-amass-turn-pilot "D:\Research\CutSceneAI-TrainingData\AMASS" ".\.cutsceneai-training-data\amass-turn-pilot-v0.1" --limit 10 --confirm-amass-license
```

The confirmation flag means only that you obtained AMASS yourself and accepted the applicable AMASS license. CutSceneAI does not download AMASS, accept its license, or promote it to production-cleared data.

## 5. What the command does

```text
AMASS source
→ source SHA-256 + family identity
→ SMPL canonicalization
→ 30 fps
→ explicit root orientation
→ 22-joint canonical local rotation deltas
→ turn mining
→ scene-conditioned target proxy
→ automated QA
```

Outputs remain local. Important files include `amass-turn-pilot-manifest.json`, `turn-candidates/qa-report.json`, per-source `record.json`, `turn_candidates.json`, and per-sample `example.json` files.

## 6. Read the pilot summary

The CLI reports source files processed, turns mined, scene-conditioned samples materialized, automated QA passes, and training-ready count. On the first run, `training_ready_count` should normally remain zero because human review has not been completed. That is expected.

## 7. Automated QA

```powershell
cutsceneai-qa-turn-dataset ".\.cutsceneai-training-data\amass-turn-pilot-v0.1\turn-candidates"
```

QA verifies artifact hashes and sizes, tensor shapes, finite values, valid 6D rotations, target-facing constraints, continuity statistics, rights-pool consistency, and family split leakage.

Automated QA passing does not mean cinematic motion is human-approved.

## 8. Human-review requirement

Every real-motion sample remains `human_review_status = not_reviewed` and `training_ready = false` until reviewed. Do not train the first baseline merely because automated QA is green.

## 9. Current model scope

The first baseline learns only the first reusable capability:

```text
current pose + target geometry + turn choreography
→ natural target-conditioned body turn
```

It is not the final CutSceneAI model. The same canonical representation later expands to locomotion/stopping, reactions, interaction, multi-actor behavior, camera, face/dialogue, and long-horizon cinematic composition.

## 10. Do not commit generated motion data

Before any commit:

```powershell
git status
```

AMASS source files and derived canonical motion arrays should not appear as files to commit. Only code, contracts, aggregate non-redistributive metrics, and documentation belong in Git.
