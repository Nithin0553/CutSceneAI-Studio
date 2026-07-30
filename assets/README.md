# Asset Resolver v0.1

The Asset Resolver turns CIR environment intent plus a project-specific Asset Index into a
deterministic, explainable resolution plan. It is engine-neutral: the index declares its target
engine and carries engine-specific asset URIs, while matching and evidence remain portable.

Version 0.1 resolves only:

- CIR environment objects to `environment_prop` assets
- CIR scene locations to `environment_set` assets

Explicit CIR environment `asset_uri` values remain authoritative. Otherwise, the resolver uses
normalized IDs, names, aliases, descriptions, keywords, and location terms. It records the score,
matched terms, curated priority, selected asset, fallback reason, and SHA-256 of the exact index.
No LLM, embedding, network service, or nondeterministic search is involved.

## Resolve the office fixture

```powershell
@'
import json
from pathlib import Path

from cutsceneai_assets import AssetIndex, render_asset_resolution_plan, resolve_project
from cutsceneai_cir import validate_project

project = validate_project(json.loads(
    Path("cir/examples/office-dialogue.cir.json").read_text(encoding="utf-8")
))
index = AssetIndex.model_validate(json.loads(
    Path("assets/examples/unreal-project.asset-index.json").read_text(encoding="utf-8")
))
print(render_asset_resolution_plan(resolve_project(project, index)))
'@ | python -
```

The committed example resolves the contract, conference table, and conference-room set. The
outdoor example resolves a boulder, trail marker, and pine-forest set. Missing candidates produce
explicit fallback results rather than guessed assets.

## Resolve through the API

With the backend running, send both contracts in one request:

```powershell
$project = Get-Content .\cir\examples\office-dialogue.cir.json -Raw |
  ConvertFrom-Json
$index = Get-Content .\assets\examples\unreal-project.asset-index.json -Raw |
  ConvertFrom-Json
$body = @{project = $project; asset_index = $index} |
  ConvertTo-Json -Depth 40

Invoke-RestMethod `
  -Uri http://127.0.0.1:8000/api/v1/assets/resolve `
  -Method Post `
  -ContentType "application/json" `
  -Body $body | ConvertTo-Json -Depth 20
```

The response embeds the target engine, selected record metadata, evidence, fallbacks, warnings,
and SHA-256 of the canonical index. Unreal Adapter v0.7 also exposes a read-only project indexer at
`GET /api/v1/adapters/unreal/asset-indexer.py`.

## Generate committed artifacts

```powershell
python assets\scripts\export_artifacts.py
python assets\scripts\export_artifacts.py --check
```

Generated products:

- `schemas/asset-index-v0.1.schema.json`
- `schemas/asset-resolution-v0.1.schema.json`
- `examples/office-dialogue.asset-resolution.json`
- `examples/outdoor-action.asset-resolution.json`

## Boundary

The v0.1 index does not download assets, infer skeleton compatibility, generate geometry, classify
images, create shots, or mutate an engine project. The resolver does not use an LLM, embedding
service, or network search. Unreal Adapter v0.7 consumes the verified plan and retains visible
fallbacks for unresolved props and sets.
