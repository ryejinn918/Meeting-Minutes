import importlib.util
import sys
import types
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest


def load_worker_module() -> ModuleType:
    worker_path = Path(__file__).resolve().parents[2] / "gpu_worker" / "worker.py"
    spec = importlib.util.spec_from_file_location("meetflow_gpu_worker", worker_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def worker(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    for name in (
        "HF_TOKEN",
        "PYANNOTE_MODEL_PATH",
        "WHISPERX_ALIGNMENT_CACHE_DIR",
        "WHISPERX_ASR_CACHE_DIR",
        "WHISPERX_LOCAL_FILES_ONLY",
        "WHISPERX_MODEL",
    ):
        monkeypatch.delenv(name, raising=False)
    return load_worker_module()


def test_offline_model_loaders_forward_local_cache_options(
    worker: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    asr_cache = tmp_path / "asr"
    alignment_cache = tmp_path / "alignment"
    pyannote_snapshot = tmp_path / "pyannote"
    asr_cache.mkdir()
    alignment_cache.mkdir()
    pyannote_snapshot.mkdir()
    pyannote_config = pyannote_snapshot / "config.yaml"
    pyannote_config.write_text("pipeline: {}\n", encoding="utf-8")
    monkeypatch.setenv("WHISPERX_ASR_CACHE_DIR", str(asr_cache))
    monkeypatch.setenv("WHISPERX_ALIGNMENT_CACHE_DIR", str(alignment_cache))
    monkeypatch.setenv("PYANNOTE_MODEL_PATH", str(pyannote_snapshot))
    monkeypatch.setenv("WHISPERX_LOCAL_FILES_ONLY", "true")
    monkeypatch.setenv("WHISPERX_MODEL", "large-v3")

    class FakeWhisperX:
        calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

        @classmethod
        def load_model(cls, *args: Any, **kwargs: Any) -> object:
            cls.calls.append(("asr", args, kwargs))
            return object()

        @classmethod
        def load_align_model(cls, *args: Any, **kwargs: Any) -> tuple[object, object]:
            cls.calls.append(("alignment", args, kwargs))
            return object(), object()

    class FakePipeline:
        checkpoint: Path | None = None
        kwargs: dict[str, Any] = {}

        @classmethod
        def from_pretrained(cls, checkpoint: Path, **kwargs: Any) -> object:
            cls.checkpoint = checkpoint
            cls.kwargs = kwargs
            return object()

    worker.load_asr_model(FakeWhisperX, "cuda")
    worker.load_alignment_model(FakeWhisperX, "ko", "cuda")
    worker.load_diarization_pipeline(FakePipeline)

    _, asr_args, asr_kwargs = FakeWhisperX.calls[0]
    assert asr_args == ("large-v3", "cuda")
    assert asr_kwargs["download_root"] == str(asr_cache)
    assert asr_kwargs["local_files_only"] is True
    _, _, alignment_kwargs = FakeWhisperX.calls[1]
    assert alignment_kwargs["model_dir"] == str(alignment_cache)
    assert alignment_kwargs["model_cache_only"] is True
    assert FakePipeline.checkpoint == pyannote_config
    assert FakePipeline.kwargs == {}


def test_offline_mode_requires_each_explicit_cache(
    worker: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WHISPERX_LOCAL_FILES_ONLY", "true")

    with pytest.raises(worker.ModelCacheError, match="WHISPERX_ASR_CACHE_DIR"):
        worker.load_asr_model(object(), "cuda")


def test_missing_pyannote_config_fails_without_network_fallback(
    worker: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("PYANNOTE_MODEL_PATH", str(tmp_path / "missing"))

    with pytest.raises(worker.ModelCacheError, match="pyannote model config"):
        worker.pyannote_checkpoint()


def test_incomplete_offline_asr_cache_has_clear_error(
    worker: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    asr_cache = tmp_path / "asr"
    asr_cache.mkdir()
    monkeypatch.setenv("WHISPERX_ASR_CACHE_DIR", str(asr_cache))
    monkeypatch.setenv("WHISPERX_LOCAL_FILES_ONLY", "true")

    class FailingWhisperX:
        @staticmethod
        def load_model(*args: Any, **kwargs: Any) -> object:
            raise OSError("cache entry missing")

    with pytest.raises(worker.ModelCacheError, match="ASR model is not available offline"):
        worker.load_asr_model(FailingWhisperX, "cuda")


def test_pyannote_diarize_output_is_converted_for_whisperx(
    worker: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeDataFrame:
        def __init__(self, rows: list[dict[str, Any]], columns: list[str] | None = None) -> None:
            self.rows = rows
            self.columns = columns

    monkeypatch.setitem(sys.modules, "pandas", types.SimpleNamespace(DataFrame=FakeDataFrame))

    class Segment:
        def __init__(self, start: float, end: float) -> None:
            self.start = start
            self.end = end

    class Annotation:
        def itertracks(self, *, yield_label: bool) -> list[tuple[Segment, None, str]]:
            assert yield_label is True
            return [(Segment(0.0, 1.25), None, "SPEAKER_00")]

    class DiarizeOutput:
        speaker_diarization = Annotation()

    converted = worker.diarization_to_dataframe(DiarizeOutput())

    assert converted.columns == ["segment", "start", "end", "speaker"]
    assert converted.rows[0]["start"] == 0.0
    assert converted.rows[0]["end"] == 1.25
    assert converted.rows[0]["speaker"] == "SPEAKER_00"


def test_existing_dataframe_is_not_rewrapped(
    worker: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeDataFrame:
        pass

    monkeypatch.setitem(sys.modules, "pandas", types.SimpleNamespace(DataFrame=FakeDataFrame))
    dataframe = FakeDataFrame()

    assert worker.diarization_to_dataframe(dataframe) is dataframe
