from __future__ import annotations

from hashlib import sha256
from io import BytesIO
from struct import pack_into
import wave

from .errors import DialogueAudioError
from .models import WavMetadata


MAX_WAV_BYTES = 25 * 1024 * 1024
_STREAMING_SIZE_SENTINELS = frozenset({0x7FFFFFFF, 0xFFFFFFFF})


def _validate_wav_size(data: bytes) -> None:
    if not data:
        raise DialogueAudioError("WAV audio is empty.")
    if len(data) > MAX_WAV_BYTES:
        raise DialogueAudioError(f"WAV audio exceeds the {MAX_WAV_BYTES}-byte v0.1 limit.")


def normalize_wav(data: bytes) -> bytes:
    """Replace streaming WAV length sentinels with exact, finite chunk sizes.

    Some speech providers cannot know a WAV stream's final length when they emit its header. They
    use a maximum 32-bit value for the RIFF and data sizes, followed by complete PCM data through
    end-of-file. Downstream WAV readers interpret that sentinel as an enormous declared frame
    count, so canonicalize only those known sentinel values from the actual byte length. Ordinary
    finite chunk sizes are left untouched so :func:`inspect_wav` still rejects genuine truncation.
    """

    _validate_wav_size(data)
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        return data

    riff_size = int.from_bytes(data[4:8], "little")
    block_align: int | None = None
    offset = 12
    while offset + 8 <= len(data):
        chunk_id = data[offset : offset + 4]
        chunk_size = int.from_bytes(data[offset + 4 : offset + 8], "little")
        payload_start = offset + 8

        if chunk_id == b"data" and chunk_size in _STREAMING_SIZE_SENTINELS:
            payload_size = len(data) - payload_start
            if block_align is None or block_align <= 0 or payload_size % block_align:
                raise DialogueAudioError("WAV audio data is truncated.")
            normalized = bytearray(data)
            pack_into("<I", normalized, offset + 4, payload_size)
            pack_into("<I", normalized, 4, len(normalized) - 8)
            return bytes(normalized)

        if chunk_size in _STREAMING_SIZE_SENTINELS:
            return data
        payload_end = payload_start + chunk_size
        if payload_end > len(data):
            return data
        if chunk_id == b"fmt " and chunk_size >= 16:
            block_align = int.from_bytes(data[payload_start + 12 : payload_start + 14], "little")
        offset = payload_end + (chunk_size % 2)

    if riff_size in _STREAMING_SIZE_SENTINELS:
        normalized = bytearray(data)
        pack_into("<I", normalized, 4, len(normalized) - 8)
        return bytes(normalized)
    return data


def inspect_wav(data: bytes) -> WavMetadata:
    """Validate PCM WAV bytes and return deterministic metadata used for timing."""

    _validate_wav_size(data)

    try:
        with wave.open(BytesIO(data), "rb") as wav_file:
            channels = wav_file.getnchannels()
            sample_width = wav_file.getsampwidth()
            sample_rate = wav_file.getframerate()
            frame_count = wav_file.getnframes()
            compression = wav_file.getcomptype()
            frame_data = wav_file.readframes(frame_count)
    except (EOFError, wave.Error) as exc:
        raise DialogueAudioError("Audio is not a readable PCM WAV file.") from exc

    if compression != "NONE":
        raise DialogueAudioError("Only uncompressed PCM WAV audio is supported in v0.1.")
    if channels not in (1, 2):
        raise DialogueAudioError("WAV audio must contain one or two channels.")
    if sample_width not in (1, 2, 3, 4):
        raise DialogueAudioError("WAV sample width must be between one and four bytes.")
    if sample_rate <= 0 or frame_count <= 0:
        raise DialogueAudioError(
            "WAV audio must contain at least one frame at a valid sample rate."
        )
    expected_frame_bytes = frame_count * channels * sample_width
    if len(frame_data) != expected_frame_bytes:
        raise DialogueAudioError("WAV audio data is truncated.")

    return WavMetadata(
        sha256=sha256(data).hexdigest(),
        byte_length=len(data),
        frame_count=frame_count,
        sample_rate_hz=sample_rate,
        channels=channels,
        sample_width_bytes=sample_width,
        duration_seconds=frame_count / sample_rate,
    )
