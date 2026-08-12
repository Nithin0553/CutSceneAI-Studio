from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from cutsceneai_cir import validate_project
from cutsceneai_parity import compile_semantics, render_timeline_semantics
from cutsceneai_unity import (
    UNITY_EDITOR_SCRIPT_FILENAME,
    UnityAssetMap,
    render_unity_editor_script,
    render_unity_plan,
)
from cutsceneai_unity import (
    compile_project as compile_unity,
)
from cutsceneai_unreal import (
    compile_project as compile_unreal,
)
from cutsceneai_unreal import (
    render_unreal_import_script,
    render_unreal_marker_upgrade_script,
    render_unreal_plan,
    render_unreal_readback_script,
)


def _read_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def _write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")
    print(f"Wrote {path}")


def compile_bundle(
    cir_path: Path,
    output_directory: Path,
    *,
    unity_asset_map_path: Path | None = None,
    unreal_package_path: str = "/Game/CutSceneAI/Sequences",
) -> None:
    source_bytes = cir_path.read_bytes()
    source_sha256 = hashlib.sha256(source_bytes).hexdigest()
    project = validate_project(_read_object(cir_path))
    semantics = compile_semantics(project)
    unity_asset_map = (
        None
        if unity_asset_map_path is None
        else UnityAssetMap.model_validate(_read_object(unity_asset_map_path))
    )

    unity_plan = compile_unity(project, asset_map=unity_asset_map)
    unreal_plan = compile_unreal(project, package_path=unreal_package_path)
    if cir_path.read_bytes() != source_bytes:
        raise RuntimeError(
            "Source CIR changed while compiling the cross-engine bundle."
        )
    if unity_plan.semantics.cir_fingerprint_sha256 != semantics.cir_fingerprint_sha256:
        raise RuntimeError("Unity and canonical CIR fingerprints differ.")

    manifest = {
        "pipeline_version": "0.1.0",
        "project_id": project.id,
        "cir_source_file": cir_path.name,
        "cir_source_file_sha256": source_sha256,
        "cir_canonical_sha256": semantics.cir_fingerprint_sha256,
        "cir_schema_version": project.schema_version,
        "fps": project.settings.fps,
        "unity": {
            "adapter_version": unity_plan.adapter_version,
            "engine_version": unity_plan.target_engine_version,
            "timeline_package_version": unity_plan.timeline_package_version,
            "asset_map": (
                None if unity_asset_map_path is None else unity_asset_map_path.name
            ),
        },
        "unreal": {
            "adapter_version": unreal_plan.adapter_version,
            "engine_version": unreal_plan.target_engine_version,
            "package_path": unreal_package_path,
        },
    }

    _write(
        output_directory / "cross-engine.manifest.json",
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
    )
    _write(
        output_directory / "expected.semantics.json",
        render_timeline_semantics(semantics),
    )
    _write(output_directory / "unity.plan.json", render_unity_plan(unity_plan))
    _write(
        output_directory / UNITY_EDITOR_SCRIPT_FILENAME,
        render_unity_editor_script(unity_plan),
    )
    _write(output_directory / "unreal.plan.json", render_unreal_plan(unreal_plan))
    _write(
        output_directory / "cutsceneai-unreal-import.py",
        render_unreal_import_script(unreal_plan, semantics),
    )
    _write(
        output_directory / "cutsceneai-unreal-readback.py",
        render_unreal_readback_script(unreal_plan, semantics),
    )
    _write(
        output_directory / "cutsceneai-unreal-upgrade-markers.py",
        render_unreal_marker_upgrade_script(unreal_plan, semantics),
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compile one unchanged CIR into Unity and Unreal acceptance artifacts."
    )
    parser.add_argument("cir", type=Path)
    parser.add_argument("--output-dir", "-o", type=Path, required=True)
    parser.add_argument("--unity-asset-map", type=Path)
    parser.add_argument("--unreal-package-path", default="/Game/CutSceneAI/Sequences")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    compile_bundle(
        args.cir,
        args.output_dir,
        unity_asset_map_path=args.unity_asset_map,
        unreal_package_path=args.unreal_package_path,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
