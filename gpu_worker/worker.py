"""Outbound-only WhisperX worker. It never receives Supabase credentials."""
import asyncio
import os
import tempfile
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx


def required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing environment variable: {name}")
    return value


def transcribe(path: Path) -> dict[str, Any]:
    import torch
    import whisperx
    from pyannote.audio import Pipeline

    device = "cuda"
    model = whisperx.load_model(os.getenv("WHISPERX_MODEL", "large-v3"), device, compute_type="float16", language="ko")
    audio = whisperx.load_audio(str(path))
    result = model.transcribe(audio, batch_size=int(os.getenv("WHISPERX_BATCH_SIZE", "8")))
    align_model, metadata = whisperx.load_align_model(language_code=result["language"], device=device)
    result = whisperx.align(result["segments"], align_model, metadata, audio, device, return_char_alignments=False)
    pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization-community-1", token=required("HF_TOKEN"))
    pipeline.to(torch.device(device))
    diarized = pipeline({"waveform": torch.from_numpy(audio).unsqueeze(0), "sample_rate": 16000})
    result = whisperx.assign_word_speakers(diarized, result)
    segments = [{"speaker": str(item.get("speaker", "UNKNOWN")), "start": float(item["start"]),
                 "end": float(item["end"]), "text": str(item["text"]).strip()}
                for item in result["segments"] if str(item.get("text", "")).strip()]
    return {"text": "\n".join(item["text"] for item in segments), "language": result.get("language"),
            "model": os.getenv("WHISPERX_MODEL", "large-v3"), "segments": segments,
            "usage": {"segment_count": len(segments)}}


async def main() -> None:
    base, token = required("MEETFLOW_API_BASE_URL").rstrip("/"), required("MEETFLOW_WORKER_TOKEN")
    worker_id, name = UUID(required("MEETFLOW_WORKER_ID")), os.getenv("MEETFLOW_WORKER_NAME", "RTX 4090")
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(headers=headers, timeout=60) as client:
        while True:
            claimed = (await client.post(f"{base}/api/v1/workers/claim", json={"worker_id": str(worker_id), "worker_name": name})).json().get("job")
            if not claimed:
                await asyncio.sleep(10); continue
            job_id = claimed["job_id"]
            stop_heartbeat = asyncio.Event()
            async def heartbeat() -> None:
                while not stop_heartbeat.is_set():
                    await asyncio.sleep(45)
                    response = await client.post(
                        f"{base}/api/v1/workers/jobs/{job_id}/heartbeat",
                        json={"worker_id": str(worker_id)},
                    )
                    response.raise_for_status()
            heartbeat_task = asyncio.create_task(heartbeat())
            try:
                with tempfile.TemporaryDirectory(prefix="meetflow-whisperx-") as directory:
                    path = Path(directory) / Path(claimed["original_name"]).name
                    async with client.stream("GET", claimed["download_url"], headers={}) as response:
                        response.raise_for_status()
                        with path.open("wb") as handle:
                            async for chunk in response.aiter_bytes(1024 * 1024): handle.write(chunk)
                    result = await asyncio.to_thread(transcribe, path)
                result["worker_id"] = str(worker_id)
                response = await client.post(f"{base}/api/v1/workers/jobs/{job_id}/complete", json=result)
                response.raise_for_status()
            except Exception as exc:
                await client.post(f"{base}/api/v1/workers/jobs/{job_id}/fail", json={"worker_id": str(worker_id), "error_code": "WHISPERX_FAILED", "message": "GPU 전사 작업을 완료하지 못했습니다."})
            finally:
                stop_heartbeat.set()
                heartbeat_task.cancel()


if __name__ == "__main__":
    asyncio.run(main())
