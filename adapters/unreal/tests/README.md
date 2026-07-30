# Unreal Adapter Tests

The suite covers coordinate conversion, CIR-to-Sequencer compilation, public-schema drift,
generated Python behavior, portable Dialogue ZIP mapping, exact manifest timing, deterministic
Unreal import packages, WAV checksum enforcement, and non-destructive asset-conflict preflight.

Run from the repository root:

```powershell
python -m pytest adapters\unreal\tests -q
```

The generated importer is exercised against small Unreal API fakes in CI. Persistence, Sequencer
playback, and Movie Render Queue remain real-engine acceptance checks documented under
`docs/acceptance`.
