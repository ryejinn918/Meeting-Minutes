import math
import wave
from pathlib import Path

import pytest

from app.services.audio_processing import merge_transcript_chunks, split_audio_file


def _write_silent_wav(path: Path, *, seconds: int = 3, sample_rate: int = 8000) -> None:
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(b"\x00\x00" * sample_rate * seconds)


@pytest.mark.asyncio
async def test_ffmpeg_splits_audio_into_small_overlapping_chunks(tmp_path: Path) -> None:
    source = tmp_path / "long.wav"
    _write_silent_wav(source)

    result = await split_audio_file(
        source,
        tmp_path,
        chunk_seconds=1,
        overlap_seconds=1,
        max_chunks=4,
        max_audio_seconds=10,
        max_chunk_bytes=1_000_000,
    )

    assert len(result.chunks) == 3
    assert math.isclose(result.duration_seconds, 3.0, abs_tol=0.1)
    assert result.chunks[0].start_seconds == 0
    assert result.chunks[0].end_seconds == 2
    assert all(chunk.path.stat().st_size < 1_000_000 for chunk in result.chunks)


def test_merge_transcript_chunks_removes_exact_overlap() -> None:
    merged = merge_transcript_chunks(
        [
            "오늘 회의에서 로그인 기능 일정을 논의했습니다",
            "로그인 기능 일정을 논의했습니다 모바일 검토도 진행합니다",
            "모바일 검토도 진행합니다 다음 회의에서 확인합니다",
        ]
    )

    assert merged == (
        "오늘 회의에서 로그인 기능 일정을 논의했습니다 "
        "모바일 검토도 진행합니다 다음 회의에서 확인합니다"
    )
