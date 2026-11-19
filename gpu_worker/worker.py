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


def load_embedding_model(device: str) -> Any:
    """Load the optional pyannote speaker-embedding model from the worker cache."""
    import torch
    from pyannote.audio import Inference, Model

    configured = os.getenv("PYANNOTE_EMBEDDING_MODEL_PATH", "").strip()
    cache_dir = model_cache_dir("PYANNOTE_EMBEDDING_CACHE_DIR")
    checkpoint: str | Path = Path(configured).expanduser() if configured else "pyannote/embedding"
    if isinstance(checkpoint, Path):
        config = checkpoint / "config.yaml" if checkpoint.is_dir() else checkpoint
        if not config.is_file():
            raise ModelCacheError("Configured pyannote embedding model does not exist")
        model = Model.from_pretrained(config)
    else:
        kwargs: dict[str, Any] = {"token": required("HF_TOKEN")}
        if cache_dir:
            kwargs["cache_dir"] = str(cache_dir)
        model = Model.from_pretrained(checkpoint, **kwargs)
    if model is None:
        raise ModelCacheError("The pyannote embedding model could not be loaded")
    return Inference(model, window="whole", device=torch.device(device))


def _embedding(inference: Any, samples: Any) -> Any:
    import numpy as np
    import torch

    if samples is None or len(samples) < 1600:
        return None
    value = inference({"waveform": torch.from_numpy(np.asarray(samples, dtype=np.float32)).reshape(1, -1), "sample_rate": 16000})
    vector = np.asarray(value, dtype=np.float32).reshape(-1)
    norm = float(np.linalg.norm(vector))
    return vector / norm if norm else None


def match_voice_profiles(
    audio: Any, segments: list[dict[str, Any]], profiles: list[dict[str, Any]], inference: Any
) -> list[dict[str, Any]]:
    """Return only unambiguous candidates; confidence stays in the backend payload."""
    import numpy as np

    profile_vectors: list[tuple[dict[str, Any], Any]] = []
    import whisperx

    for profile in profiles:
        path = profile.get("_local_path")
        if not path:
            continue
        try:
            profile_audio = whisperx.load_audio(str(path))
            vector = _embedding(inference, profile_audio)
            if vector is not None:
                profile_vectors.append((profile, vector))
        except Exception as exc:  # noqa: BLE001 - one bad sample must not fail STT
            logger.warning("voice profile embedding skipped profile_id=%s error_type=%s", profile.get("profile_id"), type(exc).__name__)
    by_speaker: dict[str, list[tuple[float, float, float]]] = {}
    for segment in segments:
        by_speaker.setdefault(segment["speaker"], []).append((segment["start"], segment["end"], 0.0))
    threshold = float(os.getenv("WHISPERX_SPEAKER_MATCH_THRESHOLD", "0.65"))
    margin = float(os.getenv("WHISPERX_SPEAKER_MATCH_MARGIN", "0.08"))
    matches: list[dict[str, Any]] = []
    for speaker, ranges in by_speaker.items():
        chunks = [audio[max(0, int(start * 16000)) : min(len(audio), int(end * 16000))] for start, end, _ in ranges]
        sample = np.concatenate(chunks)[: 30 * 16000] if chunks else None
        vector = _embedding(inference, sample)
        if vector is None:
            continue
        ranked = sorted(((float(np.dot(vector, candidate)), profile) for profile, candidate in profile_vectors), reverse=True, key=lambda item: item[0])
        if not ranked or ranked[0][0] < threshold or (len(ranked) > 1 and ranked[0][0] - ranked[1][0] < margin):
            continue
        matches.append({"speaker": speaker, "candidate_user_id": ranked[0][1]["user_id"], "confidence": max(0.0, min(1.0, ranked[0][0])), "reason": "voice_embedding"})
    return matches


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


def transcribe(path: Path, profiles: list[dict[str, Any]] | None = None) -> dict[str, Any]:
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
    candidates: list[dict[str, Any]] = []
    if profiles:
        try:
            inference = load_embedding_model(device)
            candidates = match_voice_profiles(audio, segments, profiles, inference)
        except ModelCacheError as exc:
            logger.warning("voice profile matching unavailable: %s", exc)
        except Exception as exc:  # noqa: BLE001 - matching is optional enrichment
            logger.warning("voice profile matching skipped error_type=%s", type(exc).__name__)
    return {
        "text": "\n".join(item["text"] for item in segments),
        "language": result.get("language"),
        "model": os.getenv("WHISPERX_MODEL", "large-v3"),
        "segments": segments,
        "usage": {"segment_count": len(segments)},
        "speaker_candidates": candidates,
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
                    profiles = claimed.get("voice_profiles") or []
                    for profile in profiles:
                        profile_path = Path(directory) / f"voice-{profile['profile_id']}{Path(profile.get('mime_type', '')).suffix or '.audio'}"
                        async with client.stream("GET", profile["download_url"], headers={}) as profile_response:
                            profile_response.raise_for_status()
                            with profile_path.open("wb") as handle:
                                async for chunk in profile_response.aiter_bytes(1024 * 1024):
                                    handle.write(chunk)
                        profile["_local_path"] = str(profile_path)
                    result = await asyncio.to_thread(transcribe, path, profiles)
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
