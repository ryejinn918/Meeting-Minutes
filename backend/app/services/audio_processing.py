import asyncio
import math
import re
from dataclasses import dataclass
from pathlib import Path

from app.core.errors import AppError

_DURATION_PATTERN = re.compile(
    r"Duration:\s*(?P<hours>\d{2}):(?P<minutes>\d{2}):(?P<seconds>\d{2}(?:\.\d+)?)"
)


@dataclass(frozen=True)
class AudioChunk:
    index: int
    path: Path
    start_seconds: float
    end_seconds: float


@dataclass(frozen=True)
class AudioSplitResult:
    chunks: list[AudioChunk]
    duration_seconds: float


async def split_audio_file(
    source: Path,
    output_dir: Path,
    *,
    chunk_seconds: int,
    overlap_seconds: int,
    max_chunks: int,
    max_audio_seconds: int,
    max_chunk_bytes: int,
    ffmpeg_executable: str | None = None,
) -> AudioSplitResult:
    executable = ffmpeg_executable or _get_ffmpeg_executable()
    duration = await _probe_duration(source, executable)
    if duration > max_audio_seconds:
        raise AppError(
            413,
            "AUDIO_DURATION_TOO_LONG",
            "음성 길이가 너무 깁니다. 4시간 이하의 파일을 업로드해 주세요.",
        )
    chunk_count = math.ceil(duration / chunk_seconds)
    if chunk_count > max_chunks:
        raise AppError(
            413,
            "AUDIO_TOO_MANY_CHUNKS",
            "음성 길이가 처리 가능한 범위를 초과했습니다.",
        )

    chunks: list[AudioChunk] = []
    for index in range(chunk_count):
        start = float(index * chunk_seconds)
        end = min(duration, start + chunk_seconds + overlap_seconds)
        output = output_dir / f"chunk-{index:03d}.mp3"
        process = await asyncio.create_subprocess_exec(
            executable,
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            f"{start:.3f}",
            "-i",
            str(source),
            "-t",
            f"{end - start:.3f}",
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-b:a",
            "48k",
            "-threads",
            "1",
            "-map_metadata",
            "-1",
            "-y",
            str(output),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await process.communicate()
        if process.returncode != 0 or not output.exists() or output.stat().st_size == 0:
            raise AppError(
                422,
                "AUDIO_TRANSCODE_FAILED",
                "음성파일을 전사할 수 있는 형식으로 변환하지 못했습니다.",
                details={"ffmpeg_exit_code": process.returncode},
            )
        if output.stat().st_size > max_chunk_bytes:
            raise AppError(
                413,
                "AUDIO_CHUNK_TOO_LARGE",
                "음성 구간의 크기가 전사 한도를 초과했습니다.",
            )
        del stderr
        chunks.append(
            AudioChunk(
                index=index,
                path=output,
                start_seconds=start,
                end_seconds=end,
            )
        )
    return AudioSplitResult(chunks=chunks, duration_seconds=duration)


def merge_transcript_chunks(parts: list[str], *, max_overlap_words: int = 80) -> str:
    normalized = [" ".join(part.split()) for part in parts if part.strip()]
    if not normalized:
        return ""
    merged_words = normalized[0].split()
    for part in normalized[1:]:
        words = part.split()
        overlap = 0
        upper = min(max_overlap_words, len(merged_words), len(words))
        for size in range(upper, 2, -1):
            left = [word.casefold() for word in merged_words[-size:]]
            right = [word.casefold() for word in words[:size]]
            if left == right:
                overlap = size
                break
        merged_words.extend(words[overlap:])
    return " ".join(merged_words).strip()


def _get_ffmpeg_executable() -> str:
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:
        raise AppError(
            503,
            "FFMPEG_NOT_AVAILABLE",
            "서버의 음성 처리 도구를 사용할 수 없습니다.",
        ) from exc


async def _probe_duration(source: Path, executable: str) -> float:
    process = await asyncio.create_subprocess_exec(
        executable,
        "-nostdin",
        "-hide_banner",
        "-i",
        str(source),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await process.communicate()
    match = _DURATION_PATTERN.search(stderr.decode("utf-8", errors="replace"))
    if match is None:
        raise AppError(
            422,
            "AUDIO_DURATION_UNAVAILABLE",
            "음성파일의 재생 시간을 확인하지 못했습니다.",
        )
    duration = (
        int(match.group("hours")) * 3600
        + int(match.group("minutes")) * 60
        + float(match.group("seconds"))
    )
    if duration <= 0:
        raise AppError(422, "AUDIO_EMPTY", "음성파일에 재생할 내용이 없습니다.")
    return duration
