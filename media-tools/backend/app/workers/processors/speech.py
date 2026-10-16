import subprocess
from pathlib import Path
from typing import Any

from app.core.config import settings

_model: Any | None = None
_model_size: str | None = None


def enrich_result_with_speech(result: dict) -> dict:
    enriched = dict(result)

    video_path = _first_local_mp4(result)
    if video_path is None:
        enriched.update(
            {
                "speech_status": "skipped",
                "speech_text": "",
                "speech_message": "当前作品无需提取口播文案",
            }
        )
        return enriched

    audio_path = _audio_path_for(video_path)
    try:
        audio_path = _extract_audio(video_path, _audio_path_for(video_path))
    except Exception:
        enriched.update(
            {
                "speech_status": "failed",
                "speech_text": "",
                "speech_message": "音频提取失败",
            }
        )
        return enriched

    try:
        speech_text = _transcribe_audio(audio_path).strip()
        if speech_text:
            enriched.update(
                {
                    "speech_status": "success",
                    "speech_text": speech_text,
                    "speech_message": "",
                }
            )
            return enriched

        enriched.update(
            {
                "speech_status": "empty",
                "speech_text": "",
                "speech_message": "未识别到有效口播内容",
            }
        )
        return enriched
    except Exception:
        enriched.update(
            {
                "speech_status": "failed",
                "speech_text": "",
                "speech_message": "口播识别失败",
            }
        )
        return enriched
    finally:
        _delete_file_quietly(audio_path)


def _first_local_mp4(result: dict) -> Path | None:
    for asset in result.get("assets") or []:
        local_url = asset.get("local_url") or ""
        mime_type = (asset.get("mime_type") or "").split(";", 1)[0].strip().lower()
        asset_type = (asset.get("type") or "").lower()
        if asset_type != "video" or mime_type != "video/mp4":
            continue

        video_path = _path_from_local_url(local_url)
        if video_path is not None and video_path.suffix.lower() == ".mp4" and video_path.exists():
            return video_path

    return None


def _audio_path_for(video_path: Path) -> Path:
    return video_path.with_suffix(".wav")


def _extract_audio(video_path: Path, audio_path: Path) -> Path:
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg",
        "-nostdin",
        "-y",
        "-i",
        str(video_path),
        "-vn",
        "-acodec",
        "pcm_s16le",
        "-ar",
        "16000",
        "-ac",
        "1",
        str(audio_path),
    ]
    try:
        completed = subprocess.run(
            command,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=120,
        )
    except Exception as exc:
        _delete_file_quietly(audio_path)
        raise RuntimeError("音频提取失败") from exc

    if completed.returncode != 0:
        _delete_file_quietly(audio_path)
        raise RuntimeError("音频提取失败")
    return audio_path


def _transcribe_audio(audio_path: Path) -> str:
    global _model, _model_size

    from faster_whisper import WhisperModel

    model_size = settings.speech_model_size
    if _model is None or _model_size != model_size:
        _model = WhisperModel(model_size, device="cpu", compute_type="int8")
        _model_size = model_size

    segments, _ = _model.transcribe(str(audio_path), language="zh", vad_filter=True)
    return "\n".join(segment.text.strip() for segment in segments if segment.text.strip())


def _delete_file_quietly(path: Path) -> None:
    try:
        if path.exists():
            path.unlink()
    except OSError:
        pass


def _path_from_local_url(local_url: str) -> Path | None:
    if not local_url:
        return None

    prefix = settings.public_media_prefix.rstrip("/") + "/"
    if not local_url.startswith(prefix):
        return None

    media_root = Path(settings.media_root).resolve()
    video_path = (media_root / local_url[len(prefix) :]).resolve()
    if not video_path.is_relative_to(media_root):
        return None
    return video_path
