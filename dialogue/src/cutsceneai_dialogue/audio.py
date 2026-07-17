from __future__ import annotations

from hashlib import sha256
from io import BytesIO
import wave

from .errors import DialogueAudioError
from .models import WavMetadata


MAX_WAV_BYTES = 25 * 1024 * 1024


def inspect_wav(data: bytes) -> WavMetadata:
    """Validate PCM WAV bytes and return deterministic metadata used for timing."""

    if not data:
        raise DialogueAudioError("WAV audio is empty.")
    if len(data) > MAX_WAV_BYTES:
        raise DialogueAudioError(f"WAV audio exceeds the {MAX_WAV_BYTES}-byte v0.1 limit.")

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
