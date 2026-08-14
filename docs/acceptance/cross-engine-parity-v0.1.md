# Cross-engine timeline parity v0.1 acceptance

This gate compiles one unchanged CIR 0.1 project into Unreal Engine 5.8.0 and Unity 6000.0, reads
the saved native timeline assets after restart, and automatically verifies that both preserve the
same cinematic semantics.

The automated repository tests validate contracts, deterministic generation, a simulated Unreal
saved-sequence readback, and mismatch detection. Final acceptance additionally requires the two real
editors because neither engine runtime is available in ordinary Python CI.

## Acceptance fixture

Use `cir/examples/office-dialogue.cir.json` without editing it:

- 18 seconds at 24 fps;
- playback frames `0-431`, represented by the half-open range `[0, 432)`;
- four performance cues;
- two dialogue starts at frames `120` and `216`;
- four camera cuts covering `[0,96)`, `[96,144)`, `[144,336)`, and `[336,432)`.

The compiler manifest must record the same CIR source-file SHA-256 before and after both exports and
one shared canonical CIR fingerprint.

## 1. Prepare the Python toolchain

From the repository root, create a clean Python 3.12 environment and install the local packages:

```bash
python3.12 -m venv .venv3.12
source .venv3.12/bin/activate
python -m pip install --upgrade pip
python -m pip install \
  -e "./cir[dev]" \
  -e "./preview[dev]" \
  -e "./dialogue[dev]" \
  -e "./parity[dev]" \
  -e "./adapters/unreal[dev]" \
  -e "./adapters/unity[dev]"
```

On Windows, activate with `.venv3.12\Scripts\Activate.ps1` and use `py -3.12` to create the
environment.

## 2. Compile the unchanged CIR once

```bash
python scripts/compile_cross_engine.py \
  cir/examples/office-dialogue.cir.json \
  --output-dir build/cross-engine
```

Expected files:

| File | Purpose |
| --- | --- |
| `cross-engine.manifest.json` | Source byte hash, canonical CIR hash, and engine versions |
| `expected.semantics.json` | Engine-neutral comparison contract |
| `CutSceneAISemanticMarker.cs` | Unity importer plus readback exporter; exact filename required by Unity marker serialization |
| `unity.plan.json` | Typed Unity compilation plan |
| `cutsceneai-unreal-import.py` | Unreal Sequencer importer |
| `cutsceneai-unreal-readback.py` | Unreal saved-asset readback exporter |
| `cutsceneai-unreal-upgrade-markers.py` | Guarded metadata-only upgrade for a validated legacy sequence |
| `unreal.plan.json` | Typed Unreal compilation plan |

Do not modify the CIR between this step and verification. A separate Unity asset map may be supplied
for a production-assets pass; it is not part of the CIR and does not change its fingerprint.

## 3. Unity 6000.0 pass

1. Create or open a Unity 6000.0 project.
2. In Package Manager, confirm Timeline 1.8.12 (`com.unity.timeline`) is installed.
3. Copy `build/cross-engine/CutSceneAISemanticMarker.cs` to `Assets/Editor/`. Preserve this exact
   filename because the serialized `CutSceneAISemanticMarker` type must match its script filename.
4. Wait for script compilation and resolve every compile error before continuing.
5. Select **CutSceneAI > Import Generated Timeline**.
6. Confirm `TL_SceneMeeting.playable`, `TL_SceneMeeting.semantics.json`, and
   `SC_SceneMeeting.unity` exist under `Assets/CutSceneAI/`.
7. Open the Timeline and confirm four performance clips and four non-overlapping camera activation
   clips span frame 0 through frame 432.
8. Save, close the editor, reopen the same project, and select
   **CutSceneAI > Export Generated Timeline Readback**.
9. Collect `CutSceneAIReadbacks/office-dialogue.unity.readback.json` from the Unity project root.

The importer refuses to overwrite an existing generated Scene or Timeline. For a clean rerun, delete
only those known generated assets intentionally inside Unity first.

## 4. Unreal Engine 5.8.0 pass

1. Open an Unreal Engine 5.8.0 project.
2. Enable Python Editor Script Plugin, Editor Scripting Utilities, and Sequencer Scripting.
3. Execute `build/cross-engine/cutsceneai-unreal-import.py` with
   **File > Execute Python Script**.
4. Confirm `/Game/CutSceneAI/Sequences/LS_SceneMeeting` contains four camera cuts and the
   CutSceneAI semantic markers.
5. Save all, close the editor, and reopen the project.
6. Execute `build/cross-engine/cutsceneai-unreal-readback.py`.
7. Collect
   `Saved/CutSceneAI/Readbacks/office-dialogue.unreal.readback.json`.

The importer refuses to replace an existing Level Sequence. Resolve that exact target explicitly
before a clean rerun.

If the sequence was created before canonical `CSA|...` parity markers existed, the readback reports
`Expected one timeline semantic marker, found 0`. Preserve that sequence and execute
`cutsceneai-unreal-upgrade-markers.py` once. The script adds markers only after validating its
legacy cue metadata, expected bindings, 24 fps display rate, `[0,432)` playback range, and all four
native camera-cut ranges. Save, restart Unreal, and then execute the ordinary readback exporter.
A divergent or partially tagged sequence is rejected instead of being relabeled.

## 5. Automatic parity gate

```bash
python -m cutsceneai_parity verify \
  cir/examples/office-dialogue.cir.json \
  --readback /path/to/office-dialogue.unreal.readback.json \
  --readback /path/to/office-dialogue.unity.readback.json \
  --require-both-engines \
  --tolerance-frames 1 \
  --output build/cross-engine/parity-report.json
```

The semantic pilot passes when:

- the command exits `0`;
- `equivalent` is `true`;
- `error_count` is `0`;
- both readback summaries are present;
- the report carries the same canonical CIR fingerprint as the compiler manifest.

Warnings about missing production animation or audio are expected in the placeholder-safe pilot.
They do not hide semantic mismatches: entity, performance, dialogue, or camera differences remain
errors.

## 6. Production-realization gate

After both engines contain mapped production body animation, facial curves, generated camera
curves, and the same measured dialogue clips, rerun:

```bash
python -m cutsceneai_parity verify \
  cir/examples/office-dialogue.cir.json \
  --readback /path/to/office-dialogue.unreal.readback.json \
  --readback /path/to/office-dialogue.unity.readback.json \
  --require-both-engines \
  --require-animation \
  --require-facial \
  --require-camera \
  --require-audio \
  --tolerance-frames 1 \
  --output build/cross-engine/parity-report.strict.json
```

Strict acceptance requires zero errors and zero missing-realization warnings. Placeholder body,
facial, or camera sections do not count as production realization. Because CIR 0.1 does not encode
audio duration, the verifier compares actual audio end frames directly between Unreal and Unity;
for the accepted office dialogue those ends are frames `178` and `302`.

Artist-filled native sections are supported after the initial metadata-safe import. In Unity,
replace each generated empty `AnimationClip` and retain the `CSA|...` track and clip names, or compile
a clean target with the separate Unity asset map. In Unreal, add skeletal-animation sections to the
generated actor bindings; readback associates them with that actor's canonical cues in timeline
order. Dialogue audio tracks must retain the generated `CutSceneAI Dialogue - <actor>` display name
so saved sections can be associated with the correct canonical dialogue cues.

## Evidence to retain

- `cross-engine.manifest.json`;
- both engine readback JSON files;
- `parity-report.json` and, when applicable, `parity-report.strict.json`;
- editor versions and Timeline package version;
- screenshots of both reopened native timelines;
- any editor log warnings or errors.

Do not mark the milestone accepted until the readbacks were produced after an editor restart and the
automatic report passes.
