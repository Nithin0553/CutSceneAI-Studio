from html import escape

from .models import PreviewManifest, PreviewScene


_PURPOSE_COLORS = {
    "establishing": "#2D9CDB",
    "environment_detail": "#9B51E0",
    "dialogue": "#27AE60",
    "reaction": "#F2994A",
    "action": "#EB5757",
    "transition": "#56CCF2",
}


def _short(value: str, limit: int) -> str:
    return value if len(value) <= limit else value[: limit - 1] + "…"


def _fit_label(value: str, width: float) -> str:
    return _short(value, max(2, int((width - 14) / 6.4)))


def _scene_height(scene: PreviewScene) -> int:
    characters = {cue.character_id for cue in scene.performance_cues}
    return 146 + max(1, len(characters)) * 48


def render_storyboard_svg(manifest: PreviewManifest) -> str:
    """Render a portable SVG timeline from a preview manifest."""

    width = 1200
    plot_x = 170
    plot_width = 990
    height = 88 + sum(_scene_height(scene) for scene in manifest.scenes)
    entity_names = {entity.id: entity.name for entity in manifest.entities}
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="Storyboard timeline for {escape(manifest.project_name, quote=True)}">',
        "<style>",
        "text{font-family:Inter,Segoe UI,Arial,sans-serif;fill:#EAF0F6}",
        ".muted{fill:#98A6B8}.label{font-size:13px}.small{font-size:11px}",
        ".title{font-size:24px;font-weight:700}.scene{font-size:17px;font-weight:600}",
        "</style>",
        f'<rect width="{width}" height="{height}" fill="#101722"/>',
        f'<text x="40" y="40" class="title">{escape(manifest.project_name)}</text>',
        f'<text x="40" y="64" class="label muted">Preview {manifest.preview_version} · '
        f"{manifest.settings.fps} fps · {len(manifest.scenes)} scene(s)</text>",
    ]

    y = 96
    for scene_index, scene in enumerate(manifest.scenes):
        scene_height = _scene_height(scene)
        parts.extend(
            [
                f'<rect x="24" y="{y - 20}" width="1152" height="{scene_height - 12}" '
                'rx="12" fill="#172230" stroke="#2A3B4F"/>',
                f'<text x="40" y="{y + 8}" class="scene">{escape(scene.title)}</text>',
                f'<text x="40" y="{y + 28}" class="small muted">{escape(scene.location)} · '
                f"{scene.duration_frames} frames</text>",
            ]
        )

        axis_y = y + 48
        for tick in range(5):
            fraction = tick / 4
            x = plot_x + plot_width * fraction
            frame = round(scene.duration_frames * fraction)
            parts.append(
                f'<line x1="{x:.1f}" y1="{axis_y}" x2="{x:.1f}" '
                f'y2="{y + scene_height - 44}" stroke="#26384B"/>'
            )
            parts.append(
                f'<text x="{x:.1f}" y="{axis_y - 6}" text-anchor="middle" '
                f'class="small muted">{frame}f</text>'
            )

        camera_y = axis_y + 12
        parts.append(f'<text x="40" y="{camera_y + 23}" class="label">Camera</text>')
        for cut_index, cut in enumerate(scene.camera_cuts):
            x = plot_x + plot_width * cut.start_frame / scene.duration_frames
            block_width = max(
                3.0,
                plot_width * (cut.end_frame - cut.start_frame) / scene.duration_frames,
            )
            purpose = cut.purpose.value
            label = _fit_label(
                f"{cut.shot_id} · {cut.framing.value} · {cut.lens_mm:g}mm",
                block_width,
            )
            clip_id = f"cut-{scene_index}-{cut_index}"
            parts.extend(
                [
                    f'<defs><clipPath id="{clip_id}"><rect x="{x:.1f}" y="{camera_y}" '
                    f'width="{block_width:.1f}" height="36" rx="5"/></clipPath></defs>',
                    f'<rect x="{x:.1f}" y="{camera_y}" width="{block_width:.1f}" height="36" '
                    f'rx="5" fill="{_PURPOSE_COLORS[purpose]}" opacity="0.88">'
                    f"<title>{escape(cut.description)}</title></rect>",
                    f'<text x="{x + 7:.1f}" y="{camera_y + 23}" class="small" '
                    f'clip-path="url(#{clip_id})">{escape(label)}</text>',
                ]
            )

        lane_y = camera_y + 48
        character_ids = sorted({cue.character_id for cue in scene.performance_cues})
        if not character_ids:
            parts.append(
                f'<text x="40" y="{lane_y + 23}" class="label muted">No performance cues</text>'
            )
        for character_id in character_ids:
            name = entity_names.get(character_id, character_id)
            parts.append(
                f'<text x="40" y="{lane_y + 23}" class="label">{escape(name)}</text>'
            )
            for cue_index, cue in enumerate(scene.performance_cues):
                if cue.character_id != character_id:
                    continue
                x = plot_x + plot_width * cue.start_frame / scene.duration_frames
                block_width = max(
                    3.0,
                    plot_width
                    * (cue.end_frame - cue.start_frame)
                    / scene.duration_frames,
                )
                cue_text = cue.dialogue or cue.motion_prompt
                label = _fit_label(f"{cue.emotion}: {cue_text}", block_width)
                clip_id = f"cue-{scene_index}-{cue_index}"
                parts.extend(
                    [
                        f'<defs><clipPath id="{clip_id}"><rect x="{x:.1f}" y="{lane_y}" '
                        f'width="{block_width:.1f}" height="36" rx="5"/></clipPath></defs>',
                        f'<rect x="{x:.1f}" y="{lane_y}" width="{block_width:.1f}" height="36" '
                        'rx="5" fill="#364B63">'
                        f"<title>{escape(cue.motion_prompt)}</title></rect>",
                        f'<text x="{x + 7:.1f}" y="{lane_y + 23}" class="small" '
                        f'clip-path="url(#{clip_id})">{escape(label)}</text>',
                    ]
                )
            lane_y += 48
        y += scene_height

    parts.append("</svg>")
    return "".join(parts)
