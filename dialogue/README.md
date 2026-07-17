# Dialogue Engine v0.1

Dialogue Engine turns CIR dialogue into deterministic WAV bundles without coupling the cinematic
contract to one speech provider. It can bind recorded PCM WAV files or call a pluggable speech
backend, measures the resulting audio exactly, records provenance, and updates a copy of the CIR
project with stable `cutsceneai://dialogue/...` audio URIs.

## Contract

Every bundle contains:

- `project.cir.json` — a validated CIR copy with each dialogue `audio_uri` updated
- `dialogue.manifest.json` — exact start/end seconds and frames, WAV metadata, SHA-256 hashes,
  source provenance, and timing warnings
- `audio/*.wav` — one PCM WAV file per dialogue cue
- `AI_VOICE_DISCLOSURE.txt` — included whenever speech was generated

ZIP timestamps, JSON ordering, cue IDs, filenames, and entry ordering are fixed, so identical
inputs produce byte-for-byte identical recorded-audio bundles. Generated speech is deterministic
at the packaging layer; provider audio bytes can still vary between calls.

CIR 0.1 stores dialogue start offsets and audio URIs but has no audio-duration field. Dialogue
Engine therefore preserves exact duration and end-frame timing in the manifest rather than
silently changing beat or shot boundaries. Promoting that duration into the core contract belongs
to CIR 0.2.

## Plan dialogue

From the repository root:

```powershell
python -m cutsceneai_dialogue plan `
  .\cir\examples\office-dialogue.cir.json `
  --output .\office-dialogue.dialogue-plan.json
```

The office fixture produces two stable cues at frames `120` and `216`.

## Bundle recorded WAV files

Use the cue IDs printed by `plan`:

```powershell
python -m cutsceneai_dialogue bundle-recorded `
  .\cir\examples\office-dialogue.cir.json `
  --recording "dialogue-scene-meeting-beat-confrontation-mina-1=.\mina.wav" `
  --recording "dialogue-scene-meeting-beat-confrontation-arjun-2=.\arjun.wav" `
  --output .\office-dialogue.recorded.zip
```

Version 0.1 accepts uncompressed PCM WAV, mono or stereo, with one-to-four-byte samples and a
25 MiB limit per cue. A recording is required for every planned cue, and unknown cue IDs fail the
request instead of being ignored.

## Generate speech through the API

Set `OPENAI_API_KEY` only in the backend process environment. The default OpenAI speech model is
`gpt-4o-mini-tts`; override it with `CUTSCENEAI_TTS_MODEL` when needed. Model, voice, format, and
disclosure behavior follow the official
[OpenAI text-to-speech guide](https://developers.openai.com/api/docs/guides/text-to-speech).

```powershell
$project = Get-Content .\cir\examples\office-dialogue.cir.json -Raw | ConvertFrom-Json
$request = @{
    project = $project
    default_voice = @{
        voice = "cedar"
        instructions = "Natural office dialogue with restrained emotion."
    }
    voices = @{
        mina = @{
            voice = "marin"
            instructions = "Firm, controlled, and frustrated."
        }
    }
} | ConvertTo-Json -Depth 30

Invoke-WebRequest `
  -Uri http://127.0.0.1:8000/api/v1/dialogue/synthesize `
  -Method Post `
  -ContentType "application/json" `
  -Body $request `
  -OutFile .\office-dialogue.tts.zip
```

This endpoint performs billable provider calls. Automated tests use fake providers and never call
the live API. Products using generated speech must clearly disclose to end users that the voice is
AI-generated and not a human voice; the generated bundle includes that notice. The development API
does not yet implement authentication or quotas, so keep it bound to localhost and never expose a
billing-enabled instance to an untrusted network.

## Generated artifacts

The public plan and manifest schemas plus the golden plan are committed under `schemas/` and
`examples/`. Regenerate and verify them with:

```powershell
python dialogue\scripts\export_artifacts.py
python dialogue\scripts\export_artifacts.py --check
```

## v0.1 boundaries

This package does not import WAV files into an engine, map portable URIs to Unreal `/Game/...`
assets, clone voices, generate facial animation, or change scene pacing automatically. Those are
explicit later adapter, facial-performance, and editorial milestones.
