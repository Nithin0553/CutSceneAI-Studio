# Dialogue Engine v0.1 Acceptance

Target: Windows PowerShell, Python 3.12, and the office-dialogue CIR fixture.

Status: complete on 2026-07-17 and merged in pull request #15. The live OpenAI speech gate produced
two audible WAV files with no manifest warnings: Mina used `marin` at frames `120-178`, Arjun used
`cedar` at `216-302`, both portable URIs were present, provenance and request metadata were retained,
and the AI-voice disclosure was included. No server errors or secret output were observed.

Run every command from the repository root. The checks below make live OpenAI speech calls only in
the explicitly marked synthesis step; all automated tests use fake providers.

## 1. Install the branch

```powershell
python -m pip install -e ".\cir[dev]" -e ".\preview[dev]" -e ".\dialogue[dev]" -e ".\adapters\unreal[dev]" -e ".\backend[dev]"
```

## 2. Run the automated gate

```powershell
python -m ruff check dialogue\src dialogue\scripts dialogue\tests backend\app backend\tests
python -m ruff format --check dialogue\src dialogue\scripts dialogue\tests backend\app backend\tests
python -m mypy cir\src dialogue\src backend\app
python dialogue\scripts\export_artifacts.py --check
python -m pytest dialogue\tests backend\tests\test_dialogue_api.py -q
```

## 3. Verify provider-free planning

Start the API in terminal A. The configured key stays in the process environment and is never sent
to the planning endpoint.

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In terminal B:

```powershell
$body = Get-Content .\cir\examples\office-dialogue.cir.json -Raw
$plan = Invoke-RestMethod `
    -Uri http://127.0.0.1:8000/api/v1/dialogue/plan `
    -Method Post `
    -ContentType "application/json" `
    -Body $body

$plan.dialogue_version
$plan.cues | Select-Object cue_id, character_id, start_seconds, start_frame, output_filename
```

Expected: version `0.1.0`, two cues, Mina at `5` seconds/frame `120`, and Arjun at `9`
seconds/frame `216`.

## 4. Generate the speech bundle — live, billable step

```powershell
$project = $body | ConvertFrom-Json
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
        arjun = @{
            voice = "cedar"
            instructions = "Uneasy, defensive, and natural."
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

Do not paste or print `OPENAI_API_KEY`. A missing key should produce HTTP 503 with
`speech_not_configured`; provider failures should produce a structured HTTP 502 response.

## 5. Inspect the deterministic contract

```powershell
$output = Join-Path $PWD "office-dialogue.tts"
Expand-Archive .\office-dialogue.tts.zip -DestinationPath $output -Force
$manifest = Get-Content "$output\dialogue.manifest.json" -Raw | ConvertFrom-Json
$updated = Get-Content "$output\project.cir.json" -Raw | ConvertFrom-Json

$manifest.manifest_version
$manifest.ai_voice_disclosure_required
$manifest.clips | Select-Object cue_id, start_seconds, end_seconds, start_frame, end_frame, fits_within_beat
$manifest.clips | ForEach-Object { $_.provenance } | Select-Object source, provider, model, voice, ai_generated, request_id
Get-ChildItem "$output\audio" -Filter *.wav | Select-Object Name, Length
Test-Path "$output\AI_VOICE_DISCLOSURE.txt"
$updated.scenes[0].beats[1].performances | ForEach-Object { $_.dialogue.audio_uri }
```

Acceptance requires:

- two non-empty WAV files that play correctly;
- stable Mina and Arjun start frames `120` and `216`;
- positive measured durations and exclusive end frames after their start frames;
- `source=tts`, `provider=openai`, the configured voices, request metadata when provided, and
  `ai_generated=True` for both clips;
- `fits_within_beat=True` for both fixture lines, or an explicit `audio_exceeds_beat` warning;
- two portable `cutsceneai://dialogue/office-dialogue/...` URIs in the updated CIR;
- the generated-voice disclosure file; and
- no server tracebacks or plaintext secret output.

## 6. Report the result

Record these values in the pull request before merge:

```text
Automated dialogue tests passed:
Plan version:
Cue count:
Mina start/end frames:
Arjun start/end frames:
WAV count:
Both WAV files audible:
Portable CIR URIs present:
TTS provenance present:
Disclosure file present:
Timing warnings:
Output-log errors:
```

The v0.1 gate ends at a portable bundle. Unreal Adapter v0.6 now verifies that bundle again, maps
its portable URIs to deterministic `/Game/...` Sound Waves, imports the WAV files without
replacement, and uses the manifest's exact end frames. Continue with
[`unreal-adapter-v0.6.md`](unreal-adapter-v0.6.md).
