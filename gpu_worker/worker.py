"""Outbound-only WhisperX worker. It never receives Supabase credentials."""

import asyncio
import logging
import os
import tempfile
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx

logger = logging.getLogger("meetflow.gpu_worker")
_TRUE_VALUES = {"1", "true", "yes", "on"}


class ModelCacheError(RuntimeError):
    """Raised when offline inference cannot use a configured local model cache."""


def required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing environment variable: {name}")
    return value


def local_files_only() -> bool:
    return os.getenv("WHISPERX_LOCAL_FILES_ONLY", "false").strip().lower() in _TRUE_VALUES


def model_cache_dir(name: str) -> Path | None:
    value = os.getenv(name, "").strip()
    if not value:
        if local_files_only():
            raise ModelCacheError(f"{name} is required when WHISPERX_LOCAL_FILES_ONLY=true")
        return None
    path = Path(value).expanduser()
    if not path.is_dir():
        raise ModelCacheError(f"Configured model cache directory does not exist: {name}")
    return path


def pyannote_checkpoint() -> Path | str:
    value = os.getenv("PYANNOTE_MODEL_PATH", "").strip()
    if not value:
        if local_files_only():
            raise ModelCacheError(
                "PYANNOTE_MODEL_PATH is required when WHISPERX_LOCAL_FILES_ONLY=true"
            )
        return "pyannote/speaker-diarization-community-1"

    path = Path(value).expanduser()
    checkpoint = path / "config.yaml" if path.is_dir() else path
    if not checkpoint.is_file():
        raise ModelCacheError("Configured pyannote model config does not exist")
    return checkpoint


def load_asr_model(whisperx: Any, device: str) -> Any:
    cache_dir = model_cache_dir("WHISPERX_ASR_CACHE_DIR")
    try:
        return whisperx.load_model(
            os.getenv("WHISPERX_MODEL", "large-v3"),
            device,
            compute_type="float16",
            language="ko",
            download_root=str(cache_dir) if cache_dir else None,
            local_files_only=local_files_only(),
        )
    except Exception as exc:
        if local_files_only():
            raise ModelCacheError("The WhisperX ASR model is not available offline") from exc
        raise


def load_alignment_model(whisperx: Any, language: str, device: str) -> tuple[Any, Any]:
    cache_dir = model_cache_dir("WHISPERX_ALIGNMENT_CACHE_DIR")
    try:
        return whisperx.load_align_model(
            language_code=language,
            device=device,
            model_dir=str(cache_dir) if cache_dir else None,
            model_cache_only=local_files_only(),
        )
    except Exception as exc:
        if local_files_only():
            raise ModelCacheError(
                f"The WhisperX alignment model for {language} is not available offline"
            ) from exc
        raise


def load_diarization_pipeline(pipeline_type: Any) -> Any:
    checkpoint = pyannote_checkpoint()
    try:
        if isinstance(checkpoint, Path):
            pipeline = pipeline_type.from_pretrained(checkpoint)
        else:
            pipeline = pipeline_type.from_pretrained(checkpoint, token=required("HF_TOKEN"))
    except Exception as exc:
        if local_files_only():
            raise ModelCacheError("The pyannote model is not available offline") from exc
        raise
    if pipeline is None:
        raise ModelCacheError("The pyannote diarization model could not be loaded")
    return pipeline


def diarization_to_dataframe(diarized: Any) -> Any:
    """Convert pyannote 4.x output to the dataframe expected by WhisperX.

    pyannote 4.x returns a ``DiarizeOutput`` wrapper while
    ``whisperx.assign_word_speakers`` expects a pandas dataframe.  Keeping this
    conversion at the worker boundary also preserves compatibility with older
    pyannote/WhisperX combinations that return an Annotation directly.
    """
    import pandas as pd

    if isinstance(diarized, pd.DataFrame):
        return diarized

    annotation = getattr(diarized, "speaker_diarization", diarized)
    itertracks = getattr(annotation, "itertracks", None)
    if not callable(itertracks):
        raise TypeError("Unsupported pyannote diarization output")

    rows: list[dict[str, Any]] = []
    for segment, _, speaker in itertracks(yield_label=True):
        rows.append(
            {
                "segment": segment,
                "start": float(segment.start),
                "end": float(segment.end),
                "speaker": str(speaker),
            }
        )
    return pd.DataFrame(rows, columns=["segment", "start", "end", "speaker"])


def transcribe(path: Path) -> dict[str, Any]:
    import torch
    import whisperx
    from pyannote.audio import Pipeline

    device = "cuda"
    model = load_asr_model(whisperx, device)
    audio = whisperx.load_audio(str(path))
    result = model.transcribe(audio, batch_size=int(os.getenv("WHISPERX_BATCH_SIZE", "8")))
    align_model, metadata = load_alignment_model(whisperx, result["language"], device)
    result = whisperx.align(
        result["segments"], align_model, metadata, audio, device, return_char_alignments=False
    )
    pipeline = load_diarization_pipeline(Pipeline)
    pipeline.to(torch.device(device))
    diarized = pipeline({"waveform": torch.from_numpy(audio).unsqueeze(0), "sample_rate": 16000})
    result = whisperx.assign_word_speakers(diarization_to_dataframe(diarized), result)
    segments = [
        {
            "speaker": str(item.get("speaker", "UNKNOWN")),
            "start": float(item["start"]),
            "end": float(item["end"]),
            "text": str(item["text"]).strip(),
        }
        for item in result["segments"]
        if str(item.get("text", "")).strip()
    ]
    return {
        "text": "\n".join(item["text"] for item in segments),
        "language": result.get("language"),
        "model": os.getenv("WHISPERX_MODEL", "large-v3"),
        "segments": segments,
        "usage": {"segment_count": len(segments)},
    }


async def main() -> None:
    base, token = required("MEETFLOW_API_BASE_URL").rstrip("/"), required("MEETFLOW_WORKER_TOKEN")
    worker_id, name = (
        UUID(required("MEETFLOW_WORKER_ID")),
        os.getenv("MEETFLOW_WORKER_NAME", "RTX 4090"),
    )
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(headers=headers, timeout=60) as client:
        while True:
            claimed = (
                (
                    await client.post(
                        f"{base}/api/v1/workers/claim",
                        json={"worker_id": str(worker_id), "worker_name": name},
                    )
                )
                .json()
                .get("job")
            )
            if not claimed:
                await asyncio.sleep(10)
                continue
            job_id = claimed["job_id"]
            stop_heartbeat = asyncio.Event()

            async def heartbeat(current_job_id: str, stop_event: asyncio.Event) -> None:
                while not stop_event.is_set():
                    await asyncio.sleep(45)
                    response = await client.post(
                        f"{base}/api/v1/workers/jobs/{current_job_id}/heartbeat",
                        json={"worker_id": str(worker_id)},
                    )
                    response.raise_for_status()

            heartbeat_task = asyncio.create_task(heartbeat(job_id, stop_heartbeat))
            try:
                with tempfile.TemporaryDirectory(prefix="meetflow-whisperx-") as directory:
                    path = Path(directory) / Path(claimed["original_name"]).name
                    async with client.stream(
                        "GET", claimed["download_url"], headers={}
                    ) as response:
                        response.raise_for_status()
                        with path.open("wb") as handle:
                            async for chunk in response.aiter_bytes(1024 * 1024):
                                handle.write(chunk)
                    result = await asyncio.to_thread(transcribe, path)
                result["worker_id"] = str(worker_id)
                response = await client.post(
                    f"{base}/api/v1/workers/jobs/{job_id}/complete", json=result
                )
                response.raise_for_status()
            except Exception as exc:  # noqa: BLE001 - worker must fail jobs safely
                if isinstance(exc, ModelCacheError):
                    logger.error("WhisperX model cache error: %s", exc)
                else:
                    logger.error(
                        "GPU transcription failed job_id=%s error_type=%s",
                        job_id,
                        type(exc).__name__,
                    )
                await client.post(
                    f"{base}/api/v1/workers/jobs/{job_id}/fail",
                    json={
                        "worker_id": str(worker_id),
                        "error_code": "WHISPERX_FAILED",
                        "message": "GPU 전사 작업을 완료하지 못했습니다.",
                    },
                )
            finally:
                stop_heartbeat.set()
                heartbeat_task.cancel()


if __name__ == "__main__":
    asyncio.run(main())
