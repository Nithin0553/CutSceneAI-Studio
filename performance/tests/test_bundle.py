from __future__ import annotations

from dataclasses import replace
import hashlib
from io import BytesIO
import json
from typing import Any
from zipfile import ZIP_BZIP2, ZIP_DEFLATED, ZipFile

import pytest
from cutsceneai_performance import (
    PERFORMANCE_MANIFEST_PATH,
    PERFORMANCE_PLAN_PATH,
    PerformanceBundle,
    PerformanceInputError,
    PerformanceOutputError,
    assemble_performance_bundle,
    load_performance_bundle,
    render_performance_bundle,
    verify_performance_bundle,
)


def assembled(fixture: Any) -> PerformanceBundle:
    return assemble_performance_bundle(
        fixture.plan,
        body_outputs=fixture.body_outputs,
        facial_outputs=fixture.facial_outputs,
        camera_outputs=fixture.camera_outputs,
        audio_outputs=fixture.audio_outputs,
    )


def archive_files(data: bytes) -> dict[str, bytes]:
    with ZipFile(BytesIO(data), "r") as archive:
        return {member.filename: archive.read(member) for member in archive.infolist()}


def render_archive(
    files: dict[str, bytes],
    *,
    compression: int = ZIP_DEFLATED,
) -> bytes:
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        for path, data in files.items():
            archive.writestr(path, data, compress_type=compression)
    return output.getvalue()


def replace_artifact_data(
    bundle: PerformanceBundle,
    *,
    track_kind: str,
    data: bytes,
) -> PerformanceBundle:
    package = bundle.package.model_copy(deep=True)
    tracks = getattr(package, track_kind)
    track = tracks[0]
    reference = track.artifact.model_copy(
        update={
            "sha256": hashlib.sha256(data).hexdigest(),
            "byte_length": len(data),
        }
    )
    tracks[0] = track.model_copy(update={"artifact": reference})
    files = dict(bundle.artifact_files)
    files[reference.relative_path] = data
    return PerformanceBundle(plan=bundle.plan, package=package, artifact_files=files)


def test_assembler_creates_complete_hashed_engine_neutral_bundle(
    performance_fixture: Any,
) -> None:
    bundle = assembled(performance_fixture)

    assert bundle.package.project_id == bundle.plan.project_id
    assert bundle.package.fps == 24
    assert bundle.package.body_tracks[0].sample_count == 4
    assert bundle.package.facial_tracks[0].sample_count == 4
    assert bundle.package.camera_tracks[0].sample_count == 4
    assert bundle.package.audio_tracks[0].start_frame == 1
    assert bundle.package.audio_tracks[0].end_frame == 3
    assert {path.split("/", 1)[0] for path in bundle.artifact_files} == {
        "body",
        "face",
        "camera",
        "audio",
    }
    for track in [
        *bundle.package.body_tracks,
        *bundle.package.facial_tracks,
        *bundle.package.camera_tracks,
        *bundle.package.audio_tracks,
    ]:
        data = bundle.artifact_files[track.artifact.relative_path]
        assert track.artifact.sha256 == hashlib.sha256(data).hexdigest()
        assert track.artifact.byte_length == len(data)
    with pytest.raises(TypeError):
        bundle.artifact_files["body/not-allowed.json"] = b"mutation"  # type: ignore[index]


def test_bundle_zip_is_deterministic_and_round_trips(
    performance_fixture: Any,
) -> None:
    bundle = assembled(performance_fixture)

    first = render_performance_bundle(bundle)
    second = render_performance_bundle(bundle)
    loaded = load_performance_bundle(first)

    assert first == second
    assert loaded == bundle
    assert render_performance_bundle(loaded) == first
    assert set(archive_files(first)) == {
        PERFORMANCE_PLAN_PATH,
        PERFORMANCE_MANIFEST_PATH,
        *bundle.artifact_files,
    }


@pytest.mark.parametrize(
    ("outputs", "message"),
    [
        ((), "missing"),
        ("duplicate", "duplicate"),
        ("unknown", "unknown"),
    ],
)
def test_assembler_requires_exact_provider_output_identities(
    performance_fixture: Any,
    outputs: tuple[()] | str,
    message: str,
) -> None:
    body_output = performance_fixture.body_outputs[0]
    if outputs == "duplicate":
        selected = (body_output, body_output)
    elif outputs == "unknown":
        selected = (replace(body_output, request_semantic_id="body:unknown:request"),)
    else:
        selected = ()

    with pytest.raises(PerformanceOutputError, match=message):
        assemble_performance_bundle(
            performance_fixture.plan,
            body_outputs=selected,
            facial_outputs=performance_fixture.facial_outputs,
            camera_outputs=performance_fixture.camera_outputs,
            audio_outputs=performance_fixture.audio_outputs,
        )


@pytest.mark.parametrize(
    ("outputs", "message"),
    [
        ((), "missing"),
        ("duplicate", "duplicate"),
        ("unknown", "unknown"),
    ],
)
def test_assembler_requires_exact_dialogue_audio_identities(
    performance_fixture: Any,
    outputs: tuple[()] | str,
    message: str,
) -> None:
    audio_output = performance_fixture.audio_outputs[0]
    if outputs == "duplicate":
        selected = (audio_output, audio_output)
    elif outputs == "unknown":
        selected = (replace(audio_output, dialogue_cue_id="dialogue:unknown:cue"),)
    else:
        selected = ()

    with pytest.raises(PerformanceOutputError, match=message):
        assemble_performance_bundle(
            performance_fixture.plan,
            body_outputs=performance_fixture.body_outputs,
            facial_outputs=performance_fixture.facial_outputs,
            camera_outputs=performance_fixture.camera_outputs,
            audio_outputs=selected,
        )


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"actor_binding_id": "actor:other"}, "actor binding"),
        ({"start_frame": 0, "end_frame": 2}, "start frame"),
        ({"end_frame": 4}, "WAV duration"),
        ({"data": b""}, "empty"),
        ({"data": b"not-a-wave"}, "readable WAV"),
        (
            {"data": b"truncated"},
            "readable WAV",
        ),
    ],
)
def test_assembler_rejects_invalid_dialogue_audio(
    performance_fixture: Any,
    change: dict[str, Any],
    message: str,
) -> None:
    audio_output = replace(performance_fixture.audio_outputs[0], **change)

    with pytest.raises(PerformanceOutputError, match=message):
        assemble_performance_bundle(
            performance_fixture.plan,
            body_outputs=performance_fixture.body_outputs,
            facial_outputs=performance_fixture.facial_outputs,
            camera_outputs=performance_fixture.camera_outputs,
            audio_outputs=(audio_output,),
        )


def test_assembler_rejects_dialogue_cue_reused_by_multiple_face_requests(
    performance_fixture: Any,
) -> None:
    plan = performance_fixture.plan.model_copy(deep=True)
    second_request = plan.facial_requests[0].model_copy(
        update={"semantic_id": "face:fixture:second"}
    )
    plan.facial_requests.append(second_request)
    second_output = replace(
        performance_fixture.facial_outputs[0],
        request_semantic_id=second_request.semantic_id,
    )

    with pytest.raises(PerformanceOutputError, match="multiple facial requests"):
        assemble_performance_bundle(
            plan,
            body_outputs=performance_fixture.body_outputs,
            facial_outputs=(*performance_fixture.facial_outputs, second_output),
            camera_outputs=performance_fixture.camera_outputs,
            audio_outputs=performance_fixture.audio_outputs,
        )


def test_assembler_supports_facial_requests_without_dialogue(
    performance_fixture: Any,
) -> None:
    plan = performance_fixture.plan.model_copy(deep=True)
    plan.facial_requests[0] = plan.facial_requests[0].model_copy(
        update={
            "source_dialogue_cue_id": None,
            "dialogue_start_frame": None,
            "dialogue_text": None,
            "lip_sync": False,
        }
    )

    bundle = assemble_performance_bundle(
        plan,
        body_outputs=performance_fixture.body_outputs,
        facial_outputs=performance_fixture.facial_outputs,
        camera_outputs=performance_fixture.camera_outputs,
        audio_outputs=(),
    )

    assert bundle.package.audio_tracks == []
    assert bundle.package.facial_tracks[0].source_dialogue_cue_id is None


class FakeWave:
    def __init__(
        self,
        *,
        channels: int = 1,
        sample_width: int = 2,
        sample_rate: int = 48000,
        frame_count: int = 4000,
        compression: str = "NONE",
    ) -> None:
        self.channels = channels
        self.sample_width = sample_width
        self.sample_rate = sample_rate
        self.frame_count = frame_count
        self.compression = compression

    def __enter__(self) -> FakeWave:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def getnchannels(self) -> int:
        return self.channels

    def getsampwidth(self) -> int:
        return self.sample_width

    def getframerate(self) -> int:
        return self.sample_rate

    def getnframes(self) -> int:
        return self.frame_count

    def getcomptype(self) -> str:
        return self.compression

    def readframes(self, frame_count: int) -> bytes:
        return b"\x00" * frame_count * self.channels * self.sample_width


@pytest.mark.parametrize(
    ("metadata", "message"),
    [
        ({"compression": "ULAW"}, "PCM WAV"),
        ({"channels": 3}, "channel or sample width"),
        ({"sample_width": 5}, "channel or sample width"),
        ({"sample_rate": 0}, "positive-rate PCM samples"),
        ({"frame_count": 0}, "positive-rate PCM samples"),
    ],
)
def test_assembler_rejects_unsupported_wav_metadata(
    performance_fixture: Any,
    monkeypatch: pytest.MonkeyPatch,
    metadata: dict[str, Any],
    message: str,
) -> None:
    fake = FakeWave(**metadata)
    monkeypatch.setattr(
        "cutsceneai_performance.bundle.wave.open",
        lambda *_args, **_kwargs: fake,
    )

    with pytest.raises(PerformanceOutputError, match=message):
        assembled(performance_fixture)


def test_assembler_rejects_truncated_pcm_payload(
    performance_fixture: Any,
) -> None:
    audio = performance_fixture.audio_outputs[0]
    truncated = replace(audio, data=audio.data[:-2])

    with pytest.raises(PerformanceOutputError, match="truncated or frame-misaligned"):
        assemble_performance_bundle(
            performance_fixture.plan,
            body_outputs=performance_fixture.body_outputs,
            facial_outputs=performance_fixture.facial_outputs,
            camera_outputs=performance_fixture.camera_outputs,
            audio_outputs=(truncated,),
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("package_identity", "identity or timeline"),
        ("extra_file", "files do not exactly match"),
        ("unsafe_path", "unsafe artifact path"),
        ("body_identity", "body-track identities"),
        ("body_track", "Body track"),
        ("facial_identity", "facial-track identities"),
        ("facial_track", "Facial track"),
        ("camera_identity", "camera-track identities"),
        ("camera_track", "Camera track"),
        ("audio_identity", "audio-track identities"),
        ("audio_track", "Audio track"),
        ("hash", "SHA-256"),
    ],
)
def test_bundle_verifier_rejects_manifest_and_file_relationship_drift(
    performance_fixture: Any,
    mutation: str,
    message: str,
) -> None:
    original = assembled(performance_fixture)
    package = original.package.model_copy(deep=True)
    files = dict(original.artifact_files)

    if mutation == "package_identity":
        package = package.model_copy(update={"project_id": "other-project"})
    elif mutation == "extra_file":
        files["body/unexpected.motion.json"] = b"extra"
    elif mutation == "unsafe_path":
        track = package.body_tracks[0]
        safe_path = track.artifact.relative_path
        unsafe_path = "../escape.motion.json"
        package.body_tracks[0] = track.model_copy(
            update={
                "artifact": track.artifact.model_copy(
                    update={"relative_path": unsafe_path}
                )
            }
        )
        files[unsafe_path] = files.pop(safe_path)
    elif mutation == "body_identity":
        package.body_tracks[0] = package.body_tracks[0].model_copy(
            update={"semantic_id": "body:other:identity"}
        )
    elif mutation == "body_track":
        package.body_tracks[0] = package.body_tracks[0].model_copy(
            update={"actor_binding_id": "actor:other"}
        )
    elif mutation == "facial_identity":
        package.facial_tracks[0] = package.facial_tracks[0].model_copy(
            update={"semantic_id": "face:other:identity"}
        )
    elif mutation == "facial_track":
        package.facial_tracks[0] = package.facial_tracks[0].model_copy(
            update={"actor_binding_id": "actor:other"}
        )
    elif mutation == "camera_identity":
        package.camera_tracks[0] = package.camera_tracks[0].model_copy(
            update={"semantic_id": "camera-motion:other:identity"}
        )
    elif mutation == "camera_track":
        package.camera_tracks[0] = package.camera_tracks[0].model_copy(
            update={"camera_binding_id": "camera:other"}
        )
    elif mutation == "audio_identity":
        package.audio_tracks[0] = package.audio_tracks[0].model_copy(
            update={"dialogue_cue_id": "dialogue:other:identity"}
        )
    elif mutation == "audio_track":
        package.audio_tracks[0] = package.audio_tracks[0].model_copy(
            update={"actor_binding_id": "actor:other"}
        )
    elif mutation == "hash":
        path = package.body_tracks[0].artifact.relative_path
        files[path] += b"tampered"

    bundle = PerformanceBundle(
        plan=original.plan, package=package, artifact_files=files
    )
    with pytest.raises(PerformanceOutputError, match=message):
        verify_performance_bundle(bundle)


@pytest.mark.parametrize(
    ("track_kind", "field", "value", "message"),
    [
        ("body_tracks", "fps", 12, "Body artifact"),
        ("facial_tracks", "fps", 12, "Facial artifact"),
        ("camera_tracks", "fps", 12, "Camera artifact"),
    ],
)
def test_bundle_verifier_rejects_artifact_track_mismatch(
    performance_fixture: Any,
    track_kind: str,
    field: str,
    value: Any,
    message: str,
) -> None:
    bundle = assembled(performance_fixture)
    package = bundle.package
    track = getattr(package, track_kind)[0]
    payload = json.loads(bundle.artifact_files[track.artifact.relative_path])
    payload[field] = value
    data = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    changed = replace_artifact_data(bundle, track_kind=track_kind, data=data)

    with pytest.raises(PerformanceOutputError, match=message):
        verify_performance_bundle(changed)


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (b"not-json", "not valid UTF-8 JSON"),
        (b"[]", "must contain a JSON object"),
        (b"{}", "contract validation failed"),
    ],
)
def test_bundle_verifier_rejects_invalid_artifact_json(
    performance_fixture: Any,
    data: bytes,
    message: str,
) -> None:
    bundle = replace_artifact_data(
        assembled(performance_fixture),
        track_kind="body_tracks",
        data=data,
    )

    with pytest.raises(PerformanceOutputError, match=message):
        verify_performance_bundle(bundle)


def test_bundle_verifier_rejects_audio_duration_drift(
    performance_fixture: Any,
) -> None:
    bundle = assembled(performance_fixture)
    package = bundle.package.model_copy(deep=True)
    package.audio_tracks[0] = package.audio_tracks[0].model_copy(
        update={"end_frame": 4}
    )

    with pytest.raises(PerformanceOutputError, match="WAV duration"):
        verify_performance_bundle(
            PerformanceBundle(
                plan=bundle.plan,
                package=package,
                artifact_files=bundle.artifact_files,
            )
        )


def test_renderer_rejects_oversized_uncompressed_bundle(
    performance_fixture: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "cutsceneai_performance.bundle.MAX_PERFORMANCE_BUNDLE_UNCOMPRESSED_BYTES",
        1,
    )

    with pytest.raises(PerformanceOutputError, match="uncompressed-size"):
        render_performance_bundle(assembled(performance_fixture))


@pytest.mark.parametrize(
    "path",
    ["../escape.json", "/absolute.json", "nested\\windows.json", "./dot.json"],
)
def test_loader_rejects_unsafe_archive_paths(path: str) -> None:
    data = render_archive({path: b"unsafe"})

    with pytest.raises(PerformanceInputError, match="unsafe archive path"):
        load_performance_bundle(data)


def test_loader_rejects_directory_entries() -> None:
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        archive.writestr("directory/", b"")

    with pytest.raises(PerformanceInputError, match="unsafe archive path"):
        load_performance_bundle(output.getvalue())


def test_loader_rejects_duplicate_archive_paths() -> None:
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        archive.writestr("duplicate.json", b"first")
        with pytest.warns(UserWarning, match="Duplicate name"):
            archive.writestr("duplicate.json", b"second")

    with pytest.raises(PerformanceInputError, match="duplicate archive paths"):
        load_performance_bundle(output.getvalue())


def test_loader_rejects_unsupported_compression() -> None:
    data = render_archive({"unsupported.json": b"data"}, compression=ZIP_BZIP2)

    with pytest.raises(PerformanceInputError, match="unsupported ZIP compression"):
        load_performance_bundle(data)


def test_loader_rejects_encrypted_archive_entries() -> None:
    payload = bytearray(render_archive({"encrypted.json": b"data"}))
    for signature, flag_offset in ((b"PK\x03\x04", 6), (b"PK\x01\x02", 8)):
        position = payload.index(signature)
        flags = int.from_bytes(
            payload[position + flag_offset : position + flag_offset + 2]
        )
        payload[position + flag_offset : position + flag_offset + 2] = (
            flags | 0x1
        ).to_bytes(2, "little")

    with pytest.raises(PerformanceInputError, match="Encrypted"):
        load_performance_bundle(bytes(payload))


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (b"", "empty"),
        (b"not-a-zip", "not a readable ZIP"),
    ],
)
def test_loader_rejects_empty_or_unreadable_archives(data: bytes, message: str) -> None:
    with pytest.raises(PerformanceInputError, match=message):
        load_performance_bundle(data)


def test_loader_enforces_archive_size_and_entry_limits(
    performance_fixture: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = render_performance_bundle(assembled(performance_fixture))
    monkeypatch.setattr(
        "cutsceneai_performance.bundle.MAX_PERFORMANCE_BUNDLE_BYTES",
        1,
    )
    with pytest.raises(PerformanceInputError, match="byte v0.1 limit"):
        load_performance_bundle(data)

    monkeypatch.setattr(
        "cutsceneai_performance.bundle.MAX_PERFORMANCE_BUNDLE_BYTES",
        len(data) + 1,
    )
    monkeypatch.setattr(
        "cutsceneai_performance.bundle.MAX_PERFORMANCE_BUNDLE_ENTRIES",
        1,
    )
    with pytest.raises(PerformanceInputError, match="too many archive entries"):
        load_performance_bundle(data)


def test_loader_enforces_expanded_size_limit(
    performance_fixture: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = render_performance_bundle(assembled(performance_fixture))
    monkeypatch.setattr(
        "cutsceneai_performance.bundle.MAX_PERFORMANCE_BUNDLE_UNCOMPRESSED_BYTES",
        1,
    )

    with pytest.raises(PerformanceInputError, match="expands beyond"):
        load_performance_bundle(data)


def test_loader_requires_both_contract_entries(
    performance_fixture: Any,
) -> None:
    data = render_performance_bundle(assembled(performance_fixture))
    files = archive_files(data)
    files.pop(PERFORMANCE_PLAN_PATH)

    with pytest.raises(PerformanceInputError, match="missing required entries"):
        load_performance_bundle(render_archive(files))


@pytest.mark.parametrize(
    ("path", "data", "message"),
    [
        (PERFORMANCE_PLAN_PATH, b"not-json", "not valid UTF-8 JSON"),
        (PERFORMANCE_MANIFEST_PATH, b"[]", "must contain a JSON object"),
        (PERFORMANCE_MANIFEST_PATH, b"{}", "contract validation failed"),
    ],
)
def test_loader_rejects_invalid_contract_json(
    performance_fixture: Any,
    path: str,
    data: bytes,
    message: str,
) -> None:
    files = archive_files(render_performance_bundle(assembled(performance_fixture)))
    files[path] = data

    with pytest.raises(PerformanceInputError, match=message):
        load_performance_bundle(render_archive(files))


def test_loader_rejects_tampered_artifact(
    performance_fixture: Any,
) -> None:
    bundle = assembled(performance_fixture)
    files = archive_files(render_performance_bundle(bundle))
    path = bundle.package.body_tracks[0].artifact.relative_path
    files[path] += b"tampered"

    with pytest.raises(PerformanceInputError, match="SHA-256"):
        load_performance_bundle(render_archive(files))
