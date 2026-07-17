from __future__ import annotations

from io import BytesIO
from pathlib import Path
from struct import pack_into
import wave


FIXTURE = Path(__file__).parents[2] / "cir" / "examples" / "office-dialogue.cir.json"


def make_wav(
    *,
    duration_seconds: float = 1.0,
    sample_rate: int = 8_000,
    channels: int = 1,
    sample_width: int = 2,
) -> bytes:
    frame_count = round(duration_seconds * sample_rate)
    output = BytesIO()
    with wave.open(output, "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b"\0" * frame_count * channels * sample_width)
    return output.getvalue()


def make_streaming_wav(*, size_sentinel: int = 0xFFFFFFFF) -> bytes:
    data = bytearray(make_wav())
    data_chunk_offset = data.index(b"data", 12)
    pack_into("<I", data, 4, size_sentinel)
    pack_into("<I", data, data_chunk_offset + 4, size_sentinel)
    return bytes(data)
