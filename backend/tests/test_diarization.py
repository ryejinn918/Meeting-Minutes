from app.ai.stt.base import TranscriptSegment
from app.services.diarization import (
    format_diarized_transcript,
    merge_diarized_segments,
    offset_segments,
    speaker_labels,
)


def test_chunk_offsets_and_speaker_ids_are_not_merged_across_chunks() -> None:
    first = offset_segments(
        (TranscriptSegment("A", 0, 4, "일정 확인"),),
        chunk_index=0,
        offset_seconds=0,
    )
    second = offset_segments(
        (TranscriptSegment("A", 1, 5, "다음 안건"),),
        chunk_index=1,
        offset_seconds=600,
    )

    merged = merge_diarized_segments([first, second])
    labels = speaker_labels(merged)

    assert [item.speaker_key for item in merged] == ["chunk-0:A", "chunk-1:A"]
    assert labels == {"chunk-0:A": "화자 1", "chunk-1:A": "화자 2"}
    assert merged[1].start == 601


def test_overlapping_duplicate_segment_is_removed_and_timestamps_formatted() -> None:
    first = offset_segments(
        (TranscriptSegment("A", 598, 602, "중복 발언입니다"),),
        chunk_index=0,
        offset_seconds=0,
    )
    second = offset_segments(
        (TranscriptSegment("B", 0, 4, "중복 발언입니다"),),
        chunk_index=1,
        offset_seconds=600,
    )

    merged = merge_diarized_segments([first, second])
    labels = speaker_labels(merged)

    assert len(merged) == 1
    assert format_diarized_transcript(merged, labels) == (
        "[00:09:58] 화자 1: 중복 발언입니다"
    )
