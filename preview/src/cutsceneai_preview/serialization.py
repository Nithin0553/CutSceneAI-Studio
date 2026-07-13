import json

from .models import PreviewManifest


def render_preview_manifest(manifest: PreviewManifest) -> str:
    return json.dumps(manifest.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
