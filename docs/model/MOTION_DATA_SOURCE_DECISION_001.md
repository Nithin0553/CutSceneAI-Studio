# CutSceneAI Motion Data Source Decision 001 — AMASS Research Pilot

**Date:** 2026-09-28  
**Decision:** Use AMASS as the first **research-only** human-motion source for the target-conditioned-turn baseline.

## Why AMASS first

AMASS is technically well matched to the CutSceneAI training foundation:

- SMPL-family pose representation;
- root translation and global orientation;
- large motion diversity;
- source frame-rate metadata;
- direct compatibility with the new CutSceneAI SMPL/SMPL-X canonicalizer;
- no need to reconstruct training targets from lossy text-to-motion features.

This choice is for the first research experiment, not the final production-data strategy.

## Official license finding

Primary source:

https://amass.is.tue.mpg.de/license.html

The AMASS license grants use for non-commercial scientific research, non-commercial education, and
non-commercial artistic projects. It prohibits commercial use and explicitly prohibits using the
dataset to train methods/algorithms/neural networks for commercial use.

Therefore CutSceneAI classifies AMASS as:

```text
rights_status: research_only
training_use_status: allowed        # non-commercial research baseline only
redistribution_status: not_allowed
model_distribution_status: unclear
review_status: allowed              # reviewed for the research pool
usage_pool: research
```

No AMASS-derived sample may enter `production_candidate`.

No AMASS-derived checkpoint may be represented as production-cleared.

## BABEL

Primary license:

https://babel.is.tue.mpg.de/license.html

BABEL is also restricted to non-commercial scientific research/education/artistic uses and
prohibits commercial model training. BABEL may later be useful for temporal/action labels, but it
does not solve the production-rights problem and is not needed for the first geometry-driven turn
miner.

Decision: defer BABEL until the Temporal Director/action-label stage.

## HumanML3D

Official project:

https://github.com/EricGuo5513/HumanML3D

HumanML3D is derived from HumanAct12 and AMASS. The project explicitly states that it cannot
redistribute the original AMASS data and instead provides scripts to reproduce HumanML3D after the
user obtains AMASS.

Decision: do not treat the HumanML3D repository's software license as a license grant over the
underlying AMASS motions. HumanML3D may later be used in the research pool after per-source rights
are carried through.

## KIT Motion-Language

Official dataset page:

https://motion-annotation.humanoids.kit.edu/dataset/

The page describes the dataset as open/downloadable and identifies source motion from KIT and CMU,
but the reviewed page does not provide a sufficiently explicit dataset-wide commercial/model-weight
license for CutSceneAI's production-candidate policy.

Decision: do not mark KIT-ML as production-cleared without a separate rights review.

## Pilot scope

The first AMASS pilot should be deliberately small:

1. user obtains AMASS under their own accepted license;
2. select a small number of source files;
3. ingest them locally with `cutsceneai-ingest-smpl` or the batch pilot importer;
4. canonicalize to 30 fps with explicit root orientation;
5. mine target-turn candidates;
6. materialize scene-conditioned turn candidates;
7. run dataset QA and visual review;
8. train only a research baseline checkpoint.

## Data handling

AMASS source files and derived motion artifacts must not be committed to the public Git repository.

Git stores only:

- ingestion/mining code;
- schema/contracts;
- hashes/provenance;
- aggregate metrics that do not redistribute source motion.

Local dataset roots should remain ignored/untracked.

## Exit criterion

The AMASS research pilot is successful when a small real-human-motion turn dataset passes:

- canonical schema validation;
- source-family leakage checks;
- facing-target checks;
- motion continuity checks;
- human visual review;

and is usable to train the first target-conditioned-turn research baseline.

Production data remains a separate workstream requiring owned, commercially licensed, or otherwise
explicitly permissive motion rights.
