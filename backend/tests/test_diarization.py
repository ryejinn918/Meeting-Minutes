from app.ai.stt.base import TranscriptSegment
from app.services.diarization import (
    format_diarized_transcript,
    merge_diarized_segments,
    offset_segments,
    parse_labeled_transcript,
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
    assert format_diarized_transcript(merged, labels) == ("[00:09:58] 화자 1: 중복 발언입니다")


def test_labeled_txt_transcript_creates_editable_speakers_and_ordered_offsets() -> None:
    segments, labels = parse_labeled_transcript(
        "참석자 1: 프로젝트 범위를 확인합니다.\n"
        "세부 범위는 다음 회의에서 확정합니다.\n"
        "참석자 2: 일정은 다음 주까지 검토가 필요합니다."
    )

    assert labels == {"txt:참석자 1": "참석자 1", "txt:참석자 2": "참석자 2"}
    assert [segment.speaker_key for segment in segments] == ["txt:참석자 1", "txt:참석자 2"]
    assert segments[0].text.endswith("확정합니다.")
    assert segments[0].end <= segments[1].start
