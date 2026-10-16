import subprocess
import sys
import types
from pathlib import Path

from app.core.config import settings
from app.workers.processors import speech


def test_enrich_result_with_speech_skips_images(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "media_root", str(tmp_path / "media"))

    result = {
        "media_type": "image",
        "assets": [
            {
                "type": "image",
                "mime_type": "image/jpeg",
                "local_url": "/media/link_assets/task/image_1.jpg",
            }
        ],
    }

    enriched = speech.enrich_result_with_speech(result)

    assert enriched["speech_status"] == "skipped"
    assert enriched["speech_text"] == ""
    assert enriched["speech_message"] == "当前作品无需提取口播文案"


def test_enrich_result_with_speech_transcribes_video(monkeypatch, tmp_path):
    media_root = tmp_path / "media"
    video_path = media_root / "link_assets" / "task" / "video_1.mp4"
    video_path.parent.mkdir(parents=True)
    video_path.write_bytes(b"fake mp4")
    monkeypatch.setattr(settings, "media_root", str(media_root))

    calls = {}

    def fake_extract_audio(source: Path, target: Path) -> Path:
        calls["source"] = source
        calls["target"] = target
        target.write_bytes(b"fake wav")
        return target

    monkeypatch.setattr(speech, "_extract_audio", fake_extract_audio)
    monkeypatch.setattr(speech, "_transcribe_audio", lambda audio_path: "这是一段口播文案")

    result = {
        "media_type": "video",
        "assets": [
            {
                "type": "video",
                "mime_type": "video/mp4",
                "local_url": "/media/link_assets/task/video_1.mp4",
            }
        ],
    }

    enriched = speech.enrich_result_with_speech(result)

    assert calls["source"] == video_path
    assert calls["target"] == video_path.with_suffix(".wav")
    assert enriched["speech_status"] == "success"
    assert enriched["speech_text"] == "这是一段口播文案"
    assert enriched["speech_message"] == ""


def test_enrich_result_with_speech_handles_asr_failure(monkeypatch, tmp_path):
    media_root = tmp_path / "media"
    video_path = media_root / "link_assets" / "task" / "video_1.mp4"
    video_path.parent.mkdir(parents=True)
    video_path.write_bytes(b"fake mp4")
    monkeypatch.setattr(settings, "media_root", str(media_root))

    monkeypatch.setattr(speech, "_extract_audio", lambda source, target: target)

    def raise_asr_failure(audio_path: Path) -> str:
        raise RuntimeError("ASR failed")

    monkeypatch.setattr(speech, "_transcribe_audio", raise_asr_failure)

    result = {
        "media_type": "video",
        "assets": [
            {
                "type": "video",
                "mime_type": "video/mp4",
                "local_url": "/media/link_assets/task/video_1.mp4",
            }
        ],
    }

    enriched = speech.enrich_result_with_speech(result)

    assert enriched["speech_status"] == "failed"
    assert enriched["speech_text"] == ""
    assert enriched["speech_message"] == "口播识别失败"


def test_enrich_result_with_speech_returns_empty_for_blank_transcript(monkeypatch, tmp_path):
    media_root = tmp_path / "media"
    video_path = media_root / "link_assets" / "task" / "video_1.mp4"
    video_path.parent.mkdir(parents=True)
    video_path.write_bytes(b"fake mp4")
    monkeypatch.setattr(settings, "media_root", str(media_root))

    monkeypatch.setattr(speech, "_extract_audio", lambda source, target: target)
    monkeypatch.setattr(speech, "_transcribe_audio", lambda audio_path: "  ")

    result = {
        "media_type": "video",
        "assets": [
            {
                "type": "video",
                "mime_type": "video/mp4",
                "local_url": "/media/link_assets/task/video_1.mp4",
            }
        ],
    }

    enriched = speech.enrich_result_with_speech(result)

    assert enriched["speech_status"] == "empty"
    assert enriched["speech_text"] == ""
    assert enriched["speech_message"] == "未识别到有效口播内容"


def test_enrich_result_with_speech_deletes_intermediate_wav(monkeypatch, tmp_path):
    media_root = tmp_path / "media"
    video_path = media_root / "link_assets" / "task" / "video_1.mp4"
    video_path.parent.mkdir(parents=True)
    video_path.write_bytes(b"fake mp4")
    monkeypatch.setattr(settings, "media_root", str(media_root))

    def fake_extract_audio(source: Path, target: Path) -> Path:
        target.write_bytes(b"fake wav")
        return target

    monkeypatch.setattr(speech, "_extract_audio", fake_extract_audio)
    monkeypatch.setattr(speech, "_transcribe_audio", lambda audio_path: "这是一段口播文案")

    result = {
        "media_type": "video",
        "assets": [
            {
                "type": "video",
                "mime_type": "video/mp4",
                "local_url": "/media/link_assets/task/video_1.mp4",
            }
        ],
    }

    enriched = speech.enrich_result_with_speech(result)

    assert enriched["speech_status"] == "success"
    assert not video_path.with_suffix(".wav").exists()


def test_enrich_result_with_speech_deletes_intermediate_wav_after_asr_failure(monkeypatch, tmp_path):
    media_root = tmp_path / "media"
    video_path = media_root / "link_assets" / "task" / "video_1.mp4"
    video_path.parent.mkdir(parents=True)
    video_path.write_bytes(b"fake mp4")
    monkeypatch.setattr(settings, "media_root", str(media_root))

    def fake_extract_audio(source: Path, target: Path) -> Path:
        target.write_bytes(b"fake wav")
        return target

    def raise_asr_failure(audio_path: Path) -> str:
        raise RuntimeError("ASR failed with /tmp/video_1.wav")

    monkeypatch.setattr(speech, "_extract_audio", fake_extract_audio)
    monkeypatch.setattr(speech, "_transcribe_audio", raise_asr_failure)

    result = {
        "media_type": "video",
        "assets": [
            {
                "type": "video",
                "mime_type": "video/mp4",
                "local_url": "/media/link_assets/task/video_1.mp4",
            }
        ],
    }

    enriched = speech.enrich_result_with_speech(result)

    assert enriched["speech_status"] == "failed"
    assert enriched["speech_message"] == "口播识别失败"
    assert not video_path.with_suffix(".wav").exists()


def test_first_local_mp4_strictly_skips_non_mp4_mime(monkeypatch, tmp_path):
    media_root = tmp_path / "media"
    video_path = media_root / "link_assets" / "task" / "video_1.mp4"
    video_path.parent.mkdir(parents=True)
    video_path.write_bytes(b"fake mp4")
    monkeypatch.setattr(settings, "media_root", str(media_root))
    monkeypatch.setattr(speech, "_extract_audio", lambda source, target: (_ for _ in ()).throw(AssertionError("should skip")))

    enriched = speech.enrich_result_with_speech(
        {
            "assets": [
                {
                    "type": "video",
                    "mime_type": "video/quicktime",
                    "local_url": "/media/link_assets/task/video_1.mp4",
                }
            ],
        }
    )

    assert enriched["speech_status"] == "skipped"
    assert enriched["speech_text"] == ""
    assert enriched["speech_message"] == "当前作品无需提取口播文案"


def test_first_local_mp4_strictly_skips_non_public_prefix(monkeypatch, tmp_path):
    media_root = tmp_path / "media"
    video_path = tmp_path / "video_1.mp4"
    video_path.write_bytes(b"fake mp4")
    monkeypatch.setattr(settings, "media_root", str(media_root))
    monkeypatch.setattr(speech, "_extract_audio", lambda source, target: (_ for _ in ()).throw(AssertionError("should skip")))

    enriched = speech.enrich_result_with_speech(
        {
            "assets": [
                {
                    "type": "video",
                    "mime_type": "video/mp4",
                    "local_url": str(video_path),
                }
            ],
        }
    )

    assert enriched["speech_status"] == "skipped"
    assert enriched["speech_text"] == ""
    assert enriched["speech_message"] == "当前作品无需提取口播文案"


def test_first_local_mp4_strictly_skips_path_escape(monkeypatch, tmp_path):
    media_root = tmp_path / "media"
    escaped_path = tmp_path / "outside" / "video_1.mp4"
    escaped_path.parent.mkdir(parents=True)
    escaped_path.write_bytes(b"fake mp4")
    monkeypatch.setattr(settings, "media_root", str(media_root))
    monkeypatch.setattr(speech, "_extract_audio", lambda source, target: (_ for _ in ()).throw(AssertionError("should skip")))

    enriched = speech.enrich_result_with_speech(
        {
            "assets": [
                {
                    "type": "video",
                    "mime_type": "video/mp4",
                    "local_url": "/media/../outside/video_1.mp4",
                }
            ],
        }
    )

    assert enriched["speech_status"] == "skipped"
    assert enriched["speech_text"] == ""
    assert enriched["speech_message"] == "当前作品无需提取口播文案"


def test_first_local_mp4_strictly_skips_non_mp4_suffix(monkeypatch, tmp_path):
    media_root = tmp_path / "media"
    video_path = media_root / "link_assets" / "task" / "video_1.mov"
    video_path.parent.mkdir(parents=True)
    video_path.write_bytes(b"fake mp4")
    monkeypatch.setattr(settings, "media_root", str(media_root))
    monkeypatch.setattr(speech, "_extract_audio", lambda source, target: (_ for _ in ()).throw(AssertionError("should skip")))

    enriched = speech.enrich_result_with_speech(
        {
            "assets": [
                {
                    "type": "video",
                    "mime_type": "video/mp4",
                    "local_url": "/media/link_assets/task/video_1.mov",
                }
            ],
        }
    )

    assert enriched["speech_status"] == "skipped"
    assert enriched["speech_text"] == ""
    assert enriched["speech_message"] == "当前作品无需提取口播文案"


def test_first_local_mp4_strictly_skips_missing_file(monkeypatch, tmp_path):
    media_root = tmp_path / "media"
    monkeypatch.setattr(settings, "media_root", str(media_root))
    monkeypatch.setattr(speech, "_extract_audio", lambda source, target: (_ for _ in ()).throw(AssertionError("should skip")))

    enriched = speech.enrich_result_with_speech(
        {
            "assets": [
                {
                    "type": "video",
                    "mime_type": "video/mp4",
                    "local_url": "/media/link_assets/task/video_1.mp4",
                }
            ],
        }
    )

    assert enriched["speech_status"] == "skipped"
    assert enriched["speech_text"] == ""
    assert enriched["speech_message"] == "当前作品无需提取口播文案"


def test_transcribe_audio_uses_chinese_vad_options(monkeypatch, tmp_path):
    calls = {}

    class FakeSegment:
        text = "  中文口播  "

    class FakeWhisperModel:
        def __init__(self, *args, **kwargs):
            pass

        def transcribe(self, path: str, **kwargs):
            calls["path"] = path
            calls["kwargs"] = kwargs
            return [FakeSegment()], None

    fake_module = types.SimpleNamespace(WhisperModel=FakeWhisperModel)
    monkeypatch.setitem(sys.modules, "faster_whisper", fake_module)

    audio_path = tmp_path / "video_1.wav"

    assert speech._transcribe_audio(audio_path) == "中文口播"
    assert calls == {
        "path": str(audio_path),
        "kwargs": {"language": "zh", "vad_filter": True},
    }


def test_extract_audio_uses_nostdin_timeout_and_bounded_output(monkeypatch, tmp_path):
    calls = {}

    class CompletedProcess:
        returncode = 0

    def fake_run(command, **kwargs):
        calls["command"] = command
        calls["kwargs"] = kwargs
        return CompletedProcess()

    monkeypatch.setattr(speech.subprocess, "run", fake_run)

    video_path = tmp_path / "video_1.mp4"
    audio_path = tmp_path / "video_1.wav"

    assert speech._extract_audio(video_path, audio_path) == audio_path
    assert "-nostdin" in calls["command"]
    assert calls["kwargs"]["timeout"] == 120
    assert calls["kwargs"]["stdout"] == subprocess.DEVNULL
    assert calls["kwargs"]["stderr"] == subprocess.DEVNULL
    assert calls["kwargs"]["text"] is True
    assert "capture_output" not in calls["kwargs"]


def test_transcribe_audio_caches_model_by_model_size(monkeypatch, tmp_path):
    init_calls = []

    class FakeSegment:
        text = "中文口播"

    class FakeWhisperModel:
        def __init__(self, model_size: str, **kwargs):
            init_calls.append(model_size)

        def transcribe(self, path: str, **kwargs):
            return [FakeSegment()], None

    fake_module = types.SimpleNamespace(WhisperModel=FakeWhisperModel)
    monkeypatch.setitem(sys.modules, "faster_whisper", fake_module)
    monkeypatch.setattr(speech, "_model", None)
    monkeypatch.setattr(speech, "_model_size", None)
    monkeypatch.setattr(settings, "speech_model_size", "tiny")

    audio_path = tmp_path / "video_1.wav"

    assert speech._transcribe_audio(audio_path) == "中文口播"
    assert speech._transcribe_audio(audio_path) == "中文口播"

    monkeypatch.setattr(settings, "speech_model_size", "base")
    assert speech._transcribe_audio(audio_path) == "中文口播"

    assert init_calls == ["tiny", "base"]
