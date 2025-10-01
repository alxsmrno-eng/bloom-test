from __future__ import annotations

try:
    import requests
except ImportError:  # pragma: no cover - fallback for testing
    class _RequestsFallback:
        class RequestException(Exception):
            pass

        class ConnectionError(RequestException):
            pass

        class Session:  # type: ignore[override]
            def post(self, *args, **kwargs):
                raise NotImplementedError("Requests no disponible")

    requests = _RequestsFallback()  # type: ignore[assignment]

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

try:
    from loguru import logger
except ImportError:  # pragma: no cover - fallback for testing
    class _DummyLogger:
        def __getattr__(self, name):
            def _noop(*args, **kwargs):
                pass

            return _noop

    logger = _DummyLogger()

from .config import AppConfig
from .utils import NotificationManager, load_json, outbox_dir, save_json


@dataclass
class UploadMeta:
    duration_ms: int
    wake_word: str
    timestamp_iso: str

    def to_payload(self) -> dict[str, str]:
        return {
            "source": "desktop-kay",
            "timestamp_iso": self.timestamp_iso,
            "wake_word": self.wake_word,
            "duration_ms": str(self.duration_ms),
        }


class UploadError(Exception):
    pass


class Uploader:
    def __init__(
        self,
        config: AppConfig,
        notifier: NotificationManager,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.config = config
        self.notifier = notifier
        self.session = session or requests.Session()
        self._outbox = outbox_dir()

    def upload(self, audio_bytes: bytes, meta: UploadMeta, *, enqueue_on_fail: bool = True) -> bool:
        if not self.config.webhook_url:
            logger.warning("WEBHOOK_URL no configurada. Encolando automáticamente.")
            if enqueue_on_fail:
                self.enqueue_job(audio_bytes, meta)
            return False

        for attempt in range(1, self.config.max_retry_attempts + 1):
            try:
                response = self.session.post(
                    self.config.webhook_url,
                    files={
                        "audio": (
                            "recording.wav",
                            audio_bytes,
                            "audio/wav",
                        )
                    },
                    data=meta.to_payload(),
                    timeout=15,
                )
                if 200 <= response.status_code < 300:
                    logger.info("Audio enviado correctamente (%s)", response.status_code)
                    self.notifier.show("Kay Listener", f"Audio enviado ({response.status_code})")
                    return True
                if response.status_code >= 500:
                    raise UploadError(f"Error del servidor {response.status_code}")
                else:
                    logger.error("Error permanente %s: %s", response.status_code, response.text)
                    self.notifier.show("Kay Listener", f"Error al subir: {response.status_code}")
                    return False
            except (requests.RequestException, UploadError) as exc:
                wait_time = 2 ** (attempt - 1)
                logger.warning("Intento %s fallido al subir audio: %s", attempt, exc)
                if attempt == self.config.max_retry_attempts:
                    break
                time.sleep(wait_time)

        logger.error("No se pudo subir el audio tras varios intentos. Encolando.")
        self.notifier.show("Kay Listener", "Audio encolado por error de red")
        if enqueue_on_fail:
            self.enqueue_job(audio_bytes, meta)
        return False

    def enqueue_job(self, audio_bytes: bytes, meta: UploadMeta) -> Path:
        timestamp = int(time.time())
        base_name = f"job_{timestamp}_{int(time.time() * 1000)}"
        wav_path = self._outbox / f"{base_name}.wav"
        meta_path = self._outbox / f"{base_name}.json"
        wav_path.write_bytes(audio_bytes)
        save_json(
            meta_path,
            {
                "duration_ms": meta.duration_ms,
                "wake_word": meta.wake_word,
                "timestamp_iso": meta.timestamp_iso,
            },
        )
        logger.info("Envío encolado en %s", wav_path)
        return wav_path

    def process_outbox_once(self) -> None:
        for json_file in sorted(self._outbox.glob("*.json")):
            try:
                payload = load_json(json_file)
            except Exception as exc:
                logger.error("No se pudo leer %s: %s", json_file, exc)
                continue
            wav_path = json_file.with_suffix(".wav")
            if not wav_path.exists():
                logger.warning("Archivo WAV faltante para %s", json_file)
                json_file.unlink(missing_ok=True)
                continue
            meta = UploadMeta(
                duration_ms=int(payload.get("duration_ms", 0)),
                wake_word=str(payload.get("wake_word", self.config.wake_word)),
                timestamp_iso=str(payload.get("timestamp_iso", "")),
            )
            logger.info("Reintentando envío desde outbox: %s", wav_path)
            success = self.upload(wav_path.read_bytes(), meta, enqueue_on_fail=False)
            if success:
                wav_path.unlink(missing_ok=True)
                json_file.unlink(missing_ok=True)
            else:
                break
