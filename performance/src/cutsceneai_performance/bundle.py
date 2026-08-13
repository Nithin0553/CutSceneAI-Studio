from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
from io import BytesIO
import json
from pathlib import PurePosixPath
from types import MappingProxyType
from typing import TypeVar
import wave
from zipfile import BadZipFile, ZIP_DEFLATED, ZIP_STORED, ZipFile, ZipInfo

from pydantic import BaseModel, ValidationError

from .camera import CameraCurveArtifact
from .errors import PerformanceInputError, PerformanceOutputError
from .facial import ARKIT_52_CURVES, FacialCurveArtifact
from .models import (
    ArtifactFormat,
    ArtifactKind,
    ArtifactReference,
    BodyMotionTrack,
    CameraAnimationTrack,
    DialogueAudioTrack,
    FacialAnimationTrack,
    FacialGenerationRequest,
    GeneratedPerformancePackage,
    GenerationRequest,
    ModelProvenance,
    PerformanceGenerationPlan,
)
from .motion import CANONICAL_HUMANOID_JOINTS, BodyMotionArtifact
from .providers import (
    ProviderArtifact,
    normalize_body_output,
    normalize_camera_output,
    normalize_facial_output,
)
from .serialization import (
    render_body_motion,
    render_camera_curves,
    render_facial_curves,
    render_generation_plan,
    render_performance_package,
)

PERFORMANCE_PLAN_PATH = "generation.plan.json"
PERFORMANCE_MANIFEST_PATH = "performance.package.json"
MAX_PERFORMANCE_BUNDLE_BYTES = 512 * 1024 * 1024
MAX_PERFORMANCE_BUNDLE_ENTRIES = 4096
MAX_PERFORMANCE_BUNDLE_UNCOMPRESSED_BYTES = 512 * 1024 * 1024
_SUPPORTED_COMPRESSION = frozenset({ZIP_STORED, ZIP_DEFLATED})
_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)

ArtifactT = TypeVar("ArtifactT")
ModelT = TypeVar("ModelT", bound=BaseModel)


@dataclass(frozen=True, slots=True)
class DialogueAudioArtifact:
    """Verified dialogue bytes and their exact placement in the CIR timeline."""

    dialogue_cue_id: str
    actor_binding_id: str
    start_frame: int
    end_frame: int
    data: bytes


@dataclass(frozen=True, slots=True)
class PerformanceBundle:
    """One generation plan, one package manifest, and exactly its referenced artifacts."""

    plan: PerformanceGenerationPlan
    package: GeneratedPerformancePackage
    artifact_files: Mapping[str, bytes]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "artifact_files",
            MappingProxyType(dict(self.artifact_files)),
        )


@dataclass(frozen=True, slots=True)
class DecodedPerformanceBundle:
    """Typed canonical artifacts from one already verified performance bundle."""

    body_artifacts: Mapping[str, BodyMotionArtifact]
    facial_artifacts: Mapping[str, FacialCurveArtifact]
    camera_artifacts: Mapping[str, CameraCurveArtifact]
    audio_artifacts: Mapping[str, bytes]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _artifact_path(directory: str, semantic_id: str, suffix: str) -> str:
    identity = hashlib.sha256(semantic_id.encode("utf-8")).hexdigest()
    return f"{directory}/{identity}.{suffix}"


def _artifact_reference(
    *,
    kind: ArtifactKind,
    format: ArtifactFormat,
    relative_path: str,
    data: bytes,
) -> ArtifactReference:
    return ArtifactReference(
        kind=kind,
        format=format,
        relative_path=relative_path,
        sha256=_sha256(data),
        byte_length=len(data),
    )


def _index_provider_outputs(
    expected_requests: Sequence[GenerationRequest],
    outputs: Sequence[ProviderArtifact[ArtifactT]],
    *,
    label: str,
) -> dict[str, ProviderArtifact[ArtifactT]]:
    output_ids = [output.request_semantic_id for output in outputs]
    duplicates = sorted(
        semantic_id for semantic_id, count in Counter(output_ids).items() if count > 1
    )
    expected_ids = {request.semantic_id for request in expected_requests}
    supplied_ids = set(output_ids)
    missing = sorted(expected_ids - supplied_ids)
    unknown = sorted(supplied_ids - expected_ids)
    if duplicates or missing or unknown:
        details: list[str] = []
        if duplicates:
            details.append("duplicate: " + ", ".join(duplicates))
        if missing:
            details.append("missing: " + ", ".join(missing))
        if unknown:
            details.append("unknown: " + ", ".join(unknown))
        raise PerformanceOutputError(
            f"{label} provider outputs do not exactly match the generation plan ("
            + "; ".join(details)
            + ")."
        )
    return {output.request_semantic_id: output for output in outputs}


def _dialogue_requests(
    plan: PerformanceGenerationPlan,
) -> dict[str, FacialGenerationRequest]:
    requests: dict[str, FacialGenerationRequest] = {}
    for request in plan.facial_requests:
        cue_id = request.source_dialogue_cue_id
        if cue_id is None:
            continue
        if cue_id in requests:
            raise PerformanceOutputError(
                f"Dialogue cue '{cue_id}' is referenced by multiple facial requests."
            )
        requests[cue_id] = request
    return requests


def _index_audio_outputs(
    plan: PerformanceGenerationPlan,
    outputs: Sequence[DialogueAudioArtifact],
) -> dict[str, DialogueAudioArtifact]:
    expected = _dialogue_requests(plan)
    output_ids = [output.dialogue_cue_id for output in outputs]
    duplicates = sorted(
        cue_id for cue_id, count in Counter(output_ids).items() if count > 1
    )
    supplied = set(output_ids)
    missing = sorted(set(expected) - supplied)
    unknown = sorted(supplied - set(expected))
    if duplicates or missing or unknown:
        details: list[str] = []
        if duplicates:
            details.append("duplicate: " + ", ".join(duplicates))
        if missing:
            details.append("missing: " + ", ".join(missing))
        if unknown:
            details.append("unknown: " + ", ".join(unknown))
        raise PerformanceOutputError(
            "Dialogue audio outputs do not exactly match facial dialogue references ("
            + "; ".join(details)
            + ")."
        )
    return {output.dialogue_cue_id: output for output in outputs}


def _wav_duration_frames(data: bytes, *, fps: int, label: str) -> int:
    if not data:
        raise PerformanceOutputError(f"Dialogue audio '{label}' is empty.")
    try:
        with wave.open(BytesIO(data), "rb") as audio:
            channels = audio.getnchannels()
            sample_width = audio.getsampwidth()
            sample_rate = audio.getframerate()
            frame_count = audio.getnframes()
            compression = audio.getcomptype()
            pcm_data = audio.readframes(frame_count)
    except (EOFError, wave.Error) as exc:
        raise PerformanceOutputError(
            f"Dialogue audio '{label}' is not a readable WAV file."
        ) from exc
    if compression != "NONE":
        raise PerformanceOutputError(f"Dialogue audio '{label}' must be PCM WAV.")
    if not 1 <= channels <= 2 or not 1 <= sample_width <= 4:
        raise PerformanceOutputError(
            f"Dialogue audio '{label}' uses unsupported PCM channel or sample width metadata."
        )
    if sample_rate <= 0 or frame_count <= 0:
        raise PerformanceOutputError(
            f"Dialogue audio '{label}' must contain positive-rate PCM samples."
        )
    expected_byte_length = frame_count * channels * sample_width
    if len(pcm_data) != expected_byte_length:
        raise PerformanceOutputError(
            f"Dialogue audio '{label}' contains truncated or frame-misaligned PCM data."
        )
    return (frame_count * fps + sample_rate - 1) // sample_rate


def assemble_performance_bundle(
    plan: PerformanceGenerationPlan,
    *,
    body_outputs: Sequence[ProviderArtifact[BodyMotionArtifact]],
    facial_outputs: Sequence[ProviderArtifact[FacialCurveArtifact]],
    camera_outputs: Sequence[ProviderArtifact[CameraCurveArtifact]],
    audio_outputs: Sequence[DialogueAudioArtifact],
) -> PerformanceBundle:
    """Normalize complete provider output and assemble one engine-neutral bundle."""

    body_by_id = _index_provider_outputs(
        plan.body_requests,
        body_outputs,
        label="Body",
    )
    facial_by_id = _index_provider_outputs(
        plan.facial_requests,
        facial_outputs,
        label="Facial",
    )
    camera_by_id = _index_provider_outputs(
        plan.camera_requests,
        camera_outputs,
        label="Camera",
    )
    audio_by_id = _index_audio_outputs(plan, audio_outputs)

    artifact_files: dict[str, bytes] = {}
    body_tracks: list[BodyMotionTrack] = []
    for body_request in plan.body_requests:
        normalized_body = normalize_body_output(
            body_request,
            body_by_id[body_request.semantic_id],
            target_fps=plan.fps,
        )
        body_data = render_body_motion(normalized_body.artifact).encode("utf-8")
        body_path = _artifact_path("body", body_request.semantic_id, "motion.json")
        artifact_files[body_path] = body_data
        body_tracks.append(
            BodyMotionTrack(
                semantic_id=body_request.semantic_id,
                actor_binding_id=body_request.actor_binding_id,
                source_performance_cue_id=body_request.source_performance_cue_id,
                start_frame=body_request.start_frame,
                end_frame=body_request.end_frame,
                skeleton_profile=body_request.skeleton_profile,
                joint_count=len(CANONICAL_HUMANOID_JOINTS),
                sample_count=normalized_body.artifact.frame_count,
                artifact=_artifact_reference(
                    kind=ArtifactKind.BODY_MOTION,
                    format=ArtifactFormat.CUTSCENEAI_MOTION_JSON,
                    relative_path=body_path,
                    data=body_data,
                ),
                provenance=normalized_body.provenance,
            )
        )

    facial_tracks: list[FacialAnimationTrack] = []
    for facial_request in plan.facial_requests:
        normalized_facial = normalize_facial_output(
            facial_request,
            facial_by_id[facial_request.semantic_id],
            target_fps=plan.fps,
        )
        facial_data = render_facial_curves(normalized_facial.artifact).encode("utf-8")
        facial_path = _artifact_path("face", facial_request.semantic_id, "face.json")
        artifact_files[facial_path] = facial_data
        facial_tracks.append(
            FacialAnimationTrack(
                semantic_id=facial_request.semantic_id,
                actor_binding_id=facial_request.actor_binding_id,
                source_performance_cue_id=facial_request.source_performance_cue_id,
                source_dialogue_cue_id=facial_request.source_dialogue_cue_id,
                start_frame=facial_request.start_frame,
                end_frame=facial_request.end_frame,
                curve_profile=facial_request.curve_profile,
                curve_count=len(ARKIT_52_CURVES),
                sample_count=normalized_facial.artifact.frame_count,
                artifact=_artifact_reference(
                    kind=ArtifactKind.FACIAL_CURVES,
                    format=ArtifactFormat.CUTSCENEAI_FACE_JSON,
                    relative_path=facial_path,
                    data=facial_data,
                ),
                provenance=normalized_facial.provenance,
            )
        )

    camera_tracks: list[CameraAnimationTrack] = []
    for camera_request in plan.camera_requests:
        normalized_camera = normalize_camera_output(
            camera_request,
            camera_by_id[camera_request.semantic_id],
            target_fps=plan.fps,
        )
        camera_data = render_camera_curves(normalized_camera.artifact).encode("utf-8")
        camera_path = _artifact_path(
            "camera", camera_request.semantic_id, "camera.json"
        )
        artifact_files[camera_path] = camera_data
        camera_tracks.append(
            CameraAnimationTrack(
                semantic_id=camera_request.semantic_id,
                camera_binding_id=camera_request.camera_binding_id,
                source_camera_cut_id=camera_request.source_camera_cut_id,
                start_frame=camera_request.start_frame,
                end_frame=camera_request.end_frame,
                sample_count=normalized_camera.artifact.frame_count,
                artifact=_artifact_reference(
                    kind=ArtifactKind.CAMERA_CURVES,
                    format=ArtifactFormat.CUTSCENEAI_CAMERA_JSON,
                    relative_path=camera_path,
                    data=camera_data,
                ),
                provenance=normalized_camera.provenance,
            )
        )

    dialogue_requests = _dialogue_requests(plan)
    audio_tracks: list[DialogueAudioTrack] = []
    for cue_id, facial_request in dialogue_requests.items():
        audio_output = audio_by_id[cue_id]
        if audio_output.actor_binding_id != facial_request.actor_binding_id:
            raise PerformanceOutputError(
                f"Dialogue audio '{cue_id}' actor binding does not match its facial request."
            )
        if audio_output.start_frame != facial_request.dialogue_start_frame:
            raise PerformanceOutputError(
                f"Dialogue audio '{cue_id}' start frame does not match its facial request."
            )
        duration_frames = _wav_duration_frames(
            audio_output.data, fps=plan.fps, label=cue_id
        )
        if audio_output.end_frame != audio_output.start_frame + duration_frames:
            raise PerformanceOutputError(
                f"Dialogue audio '{cue_id}' frame window does not match its WAV duration."
            )
        audio_path = _artifact_path("audio", cue_id, "wav")
        artifact_files[audio_path] = audio_output.data
        audio_tracks.append(
            DialogueAudioTrack(
                dialogue_cue_id=cue_id,
                actor_binding_id=audio_output.actor_binding_id,
                start_frame=audio_output.start_frame,
                end_frame=audio_output.end_frame,
                artifact=_artifact_reference(
                    kind=ArtifactKind.DIALOGUE_AUDIO,
                    format=ArtifactFormat.WAV_PCM,
                    relative_path=audio_path,
                    data=audio_output.data,
                ),
            )
        )

    package = GeneratedPerformancePackage(
        project_id=plan.project_id,
        cir_fingerprint_sha256=plan.cir_fingerprint_sha256,
        fps=plan.fps,
        duration_frames=plan.duration_frames,
        body_tracks=body_tracks,
        facial_tracks=facial_tracks,
        camera_tracks=camera_tracks,
        audio_tracks=audio_tracks,
    )
    bundle = PerformanceBundle(
        plan=plan.model_copy(deep=True),
        package=package,
        artifact_files=artifact_files,
    )
    verify_performance_bundle(bundle)
    return bundle


def _provenance_matches(
    request: GenerationRequest,
    provenance: ModelProvenance,
) -> bool:
    return (
        provenance.provider == request.provider
        and provenance.model == request.model
        and provenance.model_revision == request.model_revision
        and provenance.prompt_sha256 == request.prompt_sha256
        and provenance.configuration_sha256 == request.configuration_sha256
        and provenance.seed == request.seed
        and provenance.generated_at_inference
        and not provenance.retrieved_pre_authored_clip
    )


def _require_exact_identities(
    expected: set[str],
    actual: Sequence[str],
    *,
    label: str,
) -> None:
    if len(actual) != len(set(actual)) or set(actual) != expected:
        raise PerformanceOutputError(
            f"Performance package {label} identities do not exactly match its generation plan."
        )


def _artifact_data(bundle: PerformanceBundle, reference: ArtifactReference) -> bytes:
    data = bundle.artifact_files[reference.relative_path]
    if len(data) != reference.byte_length or _sha256(data) != reference.sha256:
        raise PerformanceOutputError(
            f"Artifact '{reference.relative_path}' byte length or SHA-256 is invalid."
        )
    return data


def _parse_json_model(data: bytes, *, label: str, model: type[ModelT]) -> ModelT:
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PerformanceOutputError(f"{label} is not valid UTF-8 JSON.") from exc
    if not isinstance(value, dict):
        raise PerformanceOutputError(f"{label} must contain a JSON object.")
    try:
        return model.model_validate(value)
    except ValidationError as exc:
        raise PerformanceOutputError(
            f"{label} contract validation failed: {exc}"
        ) from exc


def verify_performance_bundle(bundle: PerformanceBundle) -> None:
    """Verify every plan, manifest, provenance, hash, path, and artifact relationship."""

    plan = bundle.plan
    package = bundle.package
    if (
        package.cir_schema_version != plan.cir_schema_version
        or package.project_id != plan.project_id
        or package.cir_fingerprint_sha256 != plan.cir_fingerprint_sha256
        or package.fps != plan.fps
        or package.duration_frames != plan.duration_frames
    ):
        raise PerformanceOutputError(
            "Performance package identity or timeline does not match its generation plan."
        )

    expected_paths = {
        *(track.artifact.relative_path for track in package.body_tracks),
        *(track.artifact.relative_path for track in package.facial_tracks),
        *(track.artifact.relative_path for track in package.camera_tracks),
        *(track.artifact.relative_path for track in package.audio_tracks),
    }
    if set(bundle.artifact_files) != expected_paths:
        raise PerformanceOutputError(
            "Performance bundle files do not exactly match its manifest artifact paths."
        )
    if any(not _safe_member_name(path) for path in bundle.artifact_files):
        raise PerformanceOutputError(
            "Performance bundle contains an unsafe artifact path."
        )

    body_requests = {request.semantic_id: request for request in plan.body_requests}
    _require_exact_identities(
        set(body_requests),
        [track.semantic_id for track in package.body_tracks],
        label="body-track",
    )
    for body_track in package.body_tracks:
        body_request = body_requests[body_track.semantic_id]
        if (
            body_track.actor_binding_id != body_request.actor_binding_id
            or body_track.source_performance_cue_id
            != body_request.source_performance_cue_id
            or body_track.start_frame != body_request.start_frame
            or body_track.end_frame != body_request.end_frame
            or body_track.skeleton_profile != body_request.skeleton_profile
            or body_track.joint_count != len(CANONICAL_HUMANOID_JOINTS)
            or body_track.sample_count
            != body_request.end_frame - body_request.start_frame
            or not _provenance_matches(body_request, body_track.provenance)
        ):
            raise PerformanceOutputError(
                f"Body track '{body_track.semantic_id}' does not match its generation request."
            )
        body_artifact = _parse_json_model(
            _artifact_data(bundle, body_track.artifact),
            label=body_track.artifact.relative_path,
            model=BodyMotionArtifact,
        )
        if (
            body_artifact.fps != package.fps
            or body_artifact.frame_count != body_track.sample_count
            or body_artifact.skeleton_profile != body_track.skeleton_profile
            or body_artifact.coordinate_space != package.coordinate_space
        ):
            raise PerformanceOutputError(
                f"Body artifact '{body_track.artifact.relative_path}' does not match its track."
            )

    facial_requests = {request.semantic_id: request for request in plan.facial_requests}
    _require_exact_identities(
        set(facial_requests),
        [track.semantic_id for track in package.facial_tracks],
        label="facial-track",
    )
    for facial_track in package.facial_tracks:
        facial_request = facial_requests[facial_track.semantic_id]
        if (
            facial_track.actor_binding_id != facial_request.actor_binding_id
            or facial_track.source_performance_cue_id
            != facial_request.source_performance_cue_id
            or facial_track.source_dialogue_cue_id
            != facial_request.source_dialogue_cue_id
            or facial_track.start_frame != facial_request.start_frame
            or facial_track.end_frame != facial_request.end_frame
            or facial_track.curve_profile != facial_request.curve_profile
            or facial_track.curve_count != len(ARKIT_52_CURVES)
            or facial_track.sample_count
            != facial_request.end_frame - facial_request.start_frame
            or not _provenance_matches(facial_request, facial_track.provenance)
        ):
            raise PerformanceOutputError(
                f"Facial track '{facial_track.semantic_id}' does not match its generation request."
            )
        facial_artifact = _parse_json_model(
            _artifact_data(bundle, facial_track.artifact),
            label=facial_track.artifact.relative_path,
            model=FacialCurveArtifact,
        )
        if (
            facial_artifact.fps != package.fps
            or facial_artifact.frame_count != facial_track.sample_count
            or facial_artifact.curve_profile != facial_track.curve_profile
            or len(facial_artifact.curve_names) != facial_track.curve_count
        ):
            raise PerformanceOutputError(
                f"Facial artifact '{facial_track.artifact.relative_path}' does not match its track."
            )

    camera_requests = {request.semantic_id: request for request in plan.camera_requests}
    _require_exact_identities(
        set(camera_requests),
        [track.semantic_id for track in package.camera_tracks],
        label="camera-track",
    )
    for camera_track in package.camera_tracks:
        camera_request = camera_requests[camera_track.semantic_id]
        if (
            camera_track.camera_binding_id != camera_request.camera_binding_id
            or camera_track.source_camera_cut_id != camera_request.source_camera_cut_id
            or camera_track.start_frame != camera_request.start_frame
            or camera_track.end_frame != camera_request.end_frame
            or camera_track.sample_count
            != camera_request.end_frame - camera_request.start_frame
            or not _provenance_matches(camera_request, camera_track.provenance)
        ):
            raise PerformanceOutputError(
                f"Camera track '{camera_track.semantic_id}' does not match its generation request."
            )
        camera_artifact = _parse_json_model(
            _artifact_data(bundle, camera_track.artifact),
            label=camera_track.artifact.relative_path,
            model=CameraCurveArtifact,
        )
        if (
            camera_artifact.fps != package.fps
            or camera_artifact.frame_count != camera_track.sample_count
            or camera_artifact.coordinate_space != package.coordinate_space
        ):
            raise PerformanceOutputError(
                f"Camera artifact '{camera_track.artifact.relative_path}' does not match its track."
            )

    dialogue_requests = _dialogue_requests(plan)
    _require_exact_identities(
        set(dialogue_requests),
        [track.dialogue_cue_id for track in package.audio_tracks],
        label="audio-track",
    )
    for audio_track in package.audio_tracks:
        facial_request = dialogue_requests[audio_track.dialogue_cue_id]
        if (
            audio_track.actor_binding_id != facial_request.actor_binding_id
            or audio_track.start_frame != facial_request.dialogue_start_frame
        ):
            raise PerformanceOutputError(
                f"Audio track '{audio_track.dialogue_cue_id}' does not match its facial request."
            )
        audio_data = _artifact_data(bundle, audio_track.artifact)
        audio_duration_frames = _wav_duration_frames(
            audio_data,
            fps=package.fps,
            label=audio_track.dialogue_cue_id,
        )
        if audio_track.end_frame != audio_track.start_frame + audio_duration_frames:
            raise PerformanceOutputError(
                f"Audio track '{audio_track.dialogue_cue_id}' does not match its WAV duration."
            )


def decode_performance_bundle(bundle: PerformanceBundle) -> DecodedPerformanceBundle:
    """Verify a bundle and expose its artifacts as immutable typed mappings."""

    verify_performance_bundle(bundle)
    package = bundle.package
    return DecodedPerformanceBundle(
        body_artifacts=MappingProxyType(
            {
                track.semantic_id: _parse_json_model(
                    _artifact_data(bundle, track.artifact),
                    label=track.artifact.relative_path,
                    model=BodyMotionArtifact,
                )
                for track in package.body_tracks
            }
        ),
        facial_artifacts=MappingProxyType(
            {
                track.semantic_id: _parse_json_model(
                    _artifact_data(bundle, track.artifact),
                    label=track.artifact.relative_path,
                    model=FacialCurveArtifact,
                )
                for track in package.facial_tracks
            }
        ),
        camera_artifacts=MappingProxyType(
            {
                track.semantic_id: _parse_json_model(
                    _artifact_data(bundle, track.artifact),
                    label=track.artifact.relative_path,
                    model=CameraCurveArtifact,
                )
                for track in package.camera_tracks
            }
        ),
        audio_artifacts=MappingProxyType(
            {
                track.dialogue_cue_id: _artifact_data(bundle, track.artifact)
                for track in package.audio_tracks
            }
        ),
    )


def _write_entry(archive: ZipFile, path: str, data: bytes) -> None:
    entry = ZipInfo(path, date_time=_ZIP_TIMESTAMP)
    entry.compress_type = ZIP_DEFLATED
    entry.external_attr = 0o644 << 16
    archive.writestr(entry, data)


def render_performance_bundle(bundle: PerformanceBundle) -> bytes:
    """Render a byte-for-byte deterministic, portable Generated Performance ZIP."""

    verify_performance_bundle(bundle)
    contracts = {
        PERFORMANCE_PLAN_PATH: render_generation_plan(bundle.plan).encode("utf-8"),
        PERFORMANCE_MANIFEST_PATH: render_performance_package(bundle.package).encode(
            "utf-8"
        ),
    }
    total_size = sum(len(data) for data in contracts.values()) + sum(
        len(data) for data in bundle.artifact_files.values()
    )
    if total_size > MAX_PERFORMANCE_BUNDLE_UNCOMPRESSED_BYTES:
        raise PerformanceOutputError(
            "Performance bundle exceeds the v0.1 uncompressed-size limit."
        )

    output = BytesIO()
    with ZipFile(output, "w") as archive:
        for path, data in contracts.items():
            _write_entry(archive, path, data)
        for path, data in sorted(bundle.artifact_files.items()):
            _write_entry(archive, path, data)
    return output.getvalue()


def _safe_member_name(name: str) -> bool:
    path = PurePosixPath(name)
    return (
        bool(name)
        and "\\" not in name
        and not path.is_absolute()
        and path.as_posix() == name
        and all(part not in {"", ".", ".."} for part in path.parts)
    )


def _archive_files(data: bytes) -> dict[str, bytes]:
    if not data:
        raise PerformanceInputError("Performance bundle is empty.")
    if len(data) > MAX_PERFORMANCE_BUNDLE_BYTES:
        raise PerformanceInputError(
            f"Performance bundle exceeds the {MAX_PERFORMANCE_BUNDLE_BYTES}-byte v0.1 limit."
        )
    try:
        with ZipFile(BytesIO(data), "r") as archive:
            members = archive.infolist()
            if len(members) > MAX_PERFORMANCE_BUNDLE_ENTRIES:
                raise PerformanceInputError(
                    "Performance bundle contains too many archive entries."
                )
            total_size = 0
            names: list[str] = []
            for member in members:
                raw_name = member.orig_filename
                if (
                    member.is_dir()
                    or member.filename != raw_name
                    or not _safe_member_name(raw_name)
                ):
                    raise PerformanceInputError(
                        f"Performance bundle contains an unsafe archive path: {raw_name!r}."
                    )
                if member.flag_bits & 0x1:
                    raise PerformanceInputError(
                        "Encrypted performance bundle entries are not supported."
                    )
                if member.compress_type not in _SUPPORTED_COMPRESSION:
                    raise PerformanceInputError(
                        "Performance bundle uses an unsupported ZIP compression method."
                    )
                total_size += member.file_size
                if total_size > MAX_PERFORMANCE_BUNDLE_UNCOMPRESSED_BYTES:
                    raise PerformanceInputError(
                        "Performance bundle expands beyond the v0.1 uncompressed-size limit."
                    )
                names.append(member.filename)
            if len(set(names)) != len(names):
                raise PerformanceInputError(
                    "Performance bundle contains duplicate archive paths."
                )
            return {member.filename: archive.read(member) for member in members}
    except PerformanceInputError:
        raise
    except (
        BadZipFile,
        EOFError,
        NotImplementedError,
        OSError,
        RuntimeError,
        ValueError,
    ) as exc:
        raise PerformanceInputError(
            "Performance bundle is not a readable ZIP archive."
        ) from exc


def load_performance_bundle(data: bytes) -> PerformanceBundle:
    """Load and verify a Generated Performance ZIP as untrusted input."""

    files = _archive_files(data)
    required = {PERFORMANCE_PLAN_PATH, PERFORMANCE_MANIFEST_PATH}
    if not required.issubset(files):
        missing = ", ".join(sorted(required - set(files)))
        raise PerformanceInputError(
            f"Performance bundle is missing required entries: {missing}."
        )
    try:
        plan = _parse_json_model(
            files[PERFORMANCE_PLAN_PATH],
            label=PERFORMANCE_PLAN_PATH,
            model=PerformanceGenerationPlan,
        )
        package = _parse_json_model(
            files[PERFORMANCE_MANIFEST_PATH],
            label=PERFORMANCE_MANIFEST_PATH,
            model=GeneratedPerformancePackage,
        )
        artifact_files = {
            path: content for path, content in files.items() if path not in required
        }
        bundle = PerformanceBundle(
            plan=plan,
            package=package,
            artifact_files=artifact_files,
        )
        verify_performance_bundle(bundle)
    except PerformanceOutputError as exc:
        raise PerformanceInputError(
            f"Performance bundle verification failed: {exc}"
        ) from exc
    return bundle
