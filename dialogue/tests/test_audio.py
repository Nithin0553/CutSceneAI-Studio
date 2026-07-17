from __future__ import annotations

from contextlib import nullcontext

import pytest
from cutsceneai_dialogue import DialogueAudioError, inspect_wav

from dialogue.tests.helpers import make_wav


def test_inspect_wav_returns_exact_timing_and_digest() -> None:
    data = make_wav(duration_seconds=1.25, sample_rate=8_000, channels=2)

    metadata = inspect_wav(data)

    assert metadata.duration_seconds == 1.25
    assert metadata.frame_count == 10_000
    assert metadata.sample_rate_hz == 8_000
    assert metadata.channels == 2
    assert metadata.sample_width_bytes == 2
    assert metadata.byte_length == len(data)
    assert len(metadata.sha256) == 64


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (b"", "empty"),
        (b"not-a-wave", "readable PCM WAV"),
    ],
)
def test_inspect_wav_rejects_missing_or_invalid_audio(data: bytes, message: str) -> None:
    with pytest.raises(DialogueAudioError, match=message):
        inspect_wav(data)


def test_inspect_wav_enforces_size_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("cutsceneai_dialogue.audio.MAX_WAV_BYTES", 1)
    with pytest.raises(DialogueAudioError, match="exceeds"):
        inspect_wav(make_wav())


def test_inspect_wav_rejects_truncated_frame_data() -> None:
    with pytest.raises(DialogueAudioError, match="truncated"):
        inspect_wav(make_wav()[:-10])


class FakeWav:
    def __init__(
        self,
        *,
        compression: str = "NONE",
        channels: int = 1,
        sample_width: int = 2,
        sample_rate: int = 8_000,
        frames: int = 8_000,
    ) -> None:
        self.compression = compression
        self.channels = channels
        self.sample_width = sample_width
        self.sample_rate = sample_rate
        self.frames = frames

    def getnchannels(self) -> int:
        return self.channels

    def getsampwidth(self) -> int:
        return self.sample_width

    def getframerate(self) -> int:
        return self.sample_rate

    def getnframes(self) -> int:
        return self.frames

    def getcomptype(self) -> str:
        return self.compression

    def readframes(self, frame_count: int) -> bytes:
        return b"\0" * frame_count * self.channels * self.sample_width


@pytest.mark.parametrize(
    ("wav", "message"),
    [
        (FakeWav(compression="ULAW"), "uncompressed"),
        (FakeWav(channels=3), "one or two channels"),
        (FakeWav(sample_width=5), "between one and four bytes"),
        (FakeWav(sample_rate=0), "valid sample rate"),
        (FakeWav(frames=0), "at least one frame"),
    ],
)
def test_inspect_wav_rejects_unsupported_wave_metadata(
    monkeypatch: pytest.MonkeyPatch, wav: FakeWav, message: str
) -> None:
    monkeypatch.setattr(
        "cutsceneai_dialogue.audio.wave.open", lambda *_args, **_kwargs: nullcontext(wav)
    )
    with pytest.raises(DialogueAudioError, match=message):
        inspect_wav(b"fake-wave")
