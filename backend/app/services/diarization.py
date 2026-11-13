import re
from dataclasses import dataclass

from app.ai.stt.base import TranscriptSegment


@dataclass(frozen=True)
class DiarizedSegment:
    speaker_key: str
    provider_speaker: str
    start: float
    end: float
    text: str


def offset_segments(
    segments: tuple[TranscriptSegment, ...],
    *,
    chunk_index: int,
    offset_seconds: float,
) -> list[DiarizedSegment]:
    return [
        DiarizedSegment(
            speaker_key=f"chunk-{chunk_index}:{segment.speaker}",
            provider_speaker=segment.speaker,
            start=round(offset_seconds + segment.start, 3),
            end=round(offset_seconds + segment.end, 3),
            text=segment.text.strip(),
        )
        for segment in segments
        if segment.text.strip()
    ]


def merge_diarized_segments(
    chunks: list[list[DiarizedSegment]],
) -> list[DiarizedSegment]:
    merged: list[DiarizedSegment] = []
    for chunk in chunks:
        for candidate in chunk:
            if _is_duplicate_overlap(candidate, merged[-12:]):
                continue
            merged.append(candidate)
    return sorted(merged, key=lambda item: (item.start, item.end))


def speaker_labels(
    segments: list[DiarizedSegment],
) -> dict[str, str]:
    labels: dict[str, str] = {}
    regular = 0
    unknown = 0
    for segment in segments:
        if segment.speaker_key in labels:
            continue
        if segment.provider_speaker.casefold() == "unknown":
            unknown += 1
            labels[segment.speaker_key] = f"알 수 없는 화자 {unknown}"
        else:
            regular += 1
            labels[segment.speaker_key] = f"화자 {regular}"
    return labels


def format_diarized_transcript(
    segments: list[DiarizedSegment],
    labels: dict[str, str],
) -> str:
    return "\n\n".join(
        f"[{format_timestamp(segment.start)}] {labels[segment.speaker_key]}: {segment.text}"
        for segment in segments
    )


def serialize_segments(
    segments: list[DiarizedSegment],
) -> list[dict[str, object]]:
    return [
        {
            "speaker_key": item.speaker_key,
            "provider_speaker": item.provider_speaker,
            "start": item.start,
            "end": item.end,
            "text": item.text,
        }
        for item in segments
    ]


def deserialize_segments(value: object) -> list[DiarizedSegment]:
    if not isinstance(value, list):
        return []
    parsed: list[DiarizedSegment] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        try:
            speaker_key = str(item["speaker_key"])
            provider_speaker = str(item["provider_speaker"])
            start = float(item["start"])
            end = float(item["end"])
            text = str(item["text"]).strip()
        except (KeyError, TypeError, ValueError):
            continue
        if text and start >= 0 and end > start:
            parsed.append(
                DiarizedSegment(
                    speaker_key=speaker_key,
                    provider_speaker=provider_speaker,
                    start=start,
                    end=end,
                    text=text,
                )
            )
    return parsed


def format_timestamp(seconds: float) -> str:
    total = max(0, int(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _is_duplicate_overlap(
    candidate: DiarizedSegment,
    previous: list[DiarizedSegment],
) -> bool:
    candidate_text = _normalize_text(candidate.text)
    if not candidate_text:
        return False
    for existing in reversed(previous):
        if existing.end < candidate.start:
            break
        existing_text = _normalize_text(existing.text)
        if candidate_text == existing_text or (
            min(len(candidate_text), len(existing_text)) >= 12
            and (candidate_text in existing_text or existing_text in candidate_text)
        ):
            return True
    return False


def _normalize_text(value: str) -> str:
    return re.sub(r"[^\w가-힣]+", "", value.casefold())
