# Cross-engine timeline parity v0.1

`cutsceneai-parity` proves that saved Unreal Sequencer and Unity Timeline assets preserve the
same engine-neutral cinematic meaning as one CIR 0.1 input.

The comparison contract covers:

- the canonical SHA-256 fingerprint of the complete validated CIR;
- scene duration and integer display rate;
- entity identity and kind;
- performance actor, timing, motion-intent hash, and look-at target;
- dialogue actor, timing window, language, and text hash;
- camera order, timing, purpose, framing, angle, movement, lens, subjects, and targets;
- native animation and audio section timing when those assets are realized.

Engine asset paths are evidence, not semantic equality keys. Dialogue end frames are compared
directly between engines because CIR 0.1 intentionally does not contain audio duration.

## Compile one CIR for both engines

From the repository root:

```bash
python scripts/compile_cross_engine.py \
  cir/examples/office-dialogue.cir.json \
  --output-dir build/cross-engine
```

The compiler records the source-file hash, checks that the CIR file did not change during the
build, and emits both engine plans and scripts from the same in-memory `Project` and canonical
semantic fingerprint.

## Verify saved engine assets

After running the generated import and readback scripts in Unity and Unreal:

```bash
python -m cutsceneai_parity verify \
  cir/examples/office-dialogue.cir.json \
  --readback /path/to/office-dialogue.unreal.readback.json \
  --readback /path/to/office-dialogue.unity.readback.json \
  --require-both-engines \
  --tolerance-frames 1 \
  --output build/cross-engine/parity-report.json
```

Exit code `0` means there are no semantic errors. Missing production animation or audio is a
warning by default. Add `--require-animation` and `--require-audio` for the production-realization
gate; empty Unity placeholder clips do not satisfy strict animation coverage.

Public JSON Schemas live in `parity/schemas/`. Regenerate or verify them with:

```bash
python parity/scripts/export_artifacts.py
python parity/scripts/export_artifacts.py --check
```
