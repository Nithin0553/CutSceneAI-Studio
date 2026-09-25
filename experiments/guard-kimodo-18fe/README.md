# Guard motion comparison: Kimodo candidate

This is a bounded experiment for the guard scene, based on the complete
`18fe3351-83a2-4536-a2f2-233c3d841fde` run. It generates **body motion only**.
It does not replace the accepted CIR, dialogue audio, facial cues, or cameras.
No engine adapter should consume its output until the canonical motion passes
visual review and an explicit SOMA-to-canonical rig mapping is verified.

## Scene constraints

The CIR and generation plan are 12 seconds at 24 fps: walk frames 0–119,
stop 120–138, listen 139–167, turn toward `actor:door` 168–191, and hold
192–287. The audio cue begins at frame 202 (8.42 s). The guard's bound
transform faces world +Z, and the door is at world (2.85, 1.1, 1.0) from a
guard origin at (0, 0, -5). The earlier canonical walk travels about 2.41 m;
its stop travels about 0.21 m. From the stopping position, the door is about
40 degrees to the guard's right.

Kimodo generates at 30 fps, so `meta.json` preserves the 5/2/5-second windows
while `constraints.json` expresses the trajectory relative to its +Z initial
heading. The requested turn begins after 7 seconds and finishes near 8 seconds.
The root and heading constraints are sparse; feet are left to Kimodo's contact
model and enabled post-processing. This is an experiment, not a verified motion.

## Run after installing Kimodo in a separate WSL environment

From the CutSceneAI repository root in WSL, with Kimodo's environment active:

```bash
export HF_HOME=/mnt/e/CutSceneAI-Research/models/huggingface
export TEXT_ENCODER_DEVICE=cpu
kimodo_gen --input_folder experiments/guard-kimodo-18fe \
  --model Kimodo-SOMA-RP-v1.1 \
  --output /mnt/e/CutSceneAI-Research/evidence/kimodo-guard-18fe/guard \
  --bvh --bvh_standard_tpose
```

Leave post-processing enabled. Preserve the generated NPZ, BVH, stdout log,
Kimodo commit, and model revision. Review the native Kimodo motion first for
walk quality, grounded stop, foot placement during turn, and final direction.
Then map the SOMA joint positions, rotations, root, and foot contacts into
CutSceneAI's canonical rig and compare the same 12-second scene. Keep the source
bundle hash `9f34c5cdc2b575756eb39067c89e0eac02370b95e1ef151e1ef1ead32b498fb3`
with the experiment evidence.

The earlier MDM reference choreography still has possible foot slide during
the walk. A deterministic correction of the stop and turn improved contact
metrics but produced an unnatural knee pose; it was not adopted.

## Kaggle GPU notebook for a 16 GiB laptop

The local Kimodo text encoder uses LLM2Vec based on Llama 3 8B in bfloat16.
Moving it to CPU reduces GPU memory demand but requires considerably more
system RAM than a 16 GiB laptop can reliably spare. `kaggle-guard-pilot.ipynb`
contains this exact `meta.json` and `constraints.json` alongside
`kaggle_pilot.py`, so it works even if this repository is private to Kaggle.

In Kaggle Notebooks, select GPU T4 x2, enable Internet, and add a private
Kaggle Secret named `HF_TOKEN` with a Hugging Face access token that can read
`meta-llama/Meta-Llama-3-8B-Instruct`. Grant notebook access to the secret.
Run the notebook and download `guard-kimodo-18fe-evidence.zip` from its
outputs. The notebook keeps model caches outside downloadable outputs and
never prints the token. It first checks CUDA and available system RAM, then
installs the MotionCorrection build prerequisites, pins Kimodo source to
`58e781898b3d7e328a676a75d3e338c45dce3ad9`, and generates a single
candidate. An NPZ or BVH is **evidence to review**, not visual acceptance.
