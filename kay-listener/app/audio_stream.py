from __future__ import annotations

import queue
import threading
from typing import Optional

import sounddevice as sd
from loguru import logger

from .config import AppConfig


class AudioStream:
    """Real-time audio capture with subscription support."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.frame_samples = int(config.sample_rate * config.frame_duration_seconds)
        self.subscribers: list[queue.Queue[bytes]] = []
        self._lock = threading.Lock()
        self._stream: Optional[sd.InputStream] = None
        self._running = False

    def start(self) -> None:
        if self._running:
            return
        logger.info("Iniciando captura de audio (%s Hz)", self.config.sample_rate)
        try:
            self._stream = sd.InputStream(
                samplerate=self.config.sample_rate,
                blocksize=self.frame_samples,
                channels=1,
                dtype="int16",
                callback=self._callback,
                device=self.config.input_device_index,
            )
            self._stream.start()
            self._running = True
        except Exception as exc:
            logger.exception("No se pudo iniciar el stream de audio: %s", exc)
            raise

    def stop(self) -> None:
        if not self._running:
            return
        logger.info("Deteniendo captura de audio")
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
        with self._lock:
            self.subscribers.clear()
        self._running = False

    def subscribe(self, maxsize: int = 50) -> queue.Queue[bytes]:
        q: queue.Queue[bytes] = queue.Queue(maxsize=maxsize)
        with self._lock:
            self.subscribers.append(q)
        return q

    def unsubscribe(self, q: queue.Queue[bytes]) -> None:
        with self._lock:
            if q in self.subscribers:
                self.subscribers.remove(q)

    def _callback(self, indata, frames, time_info, status) -> None:  # pragma: no cover - realtime callback
        if status:
            logger.warning("Audio callback status: %s", status)
        frame = indata.tobytes()
        with self._lock:
            subscribers = list(self.subscribers)
        for q in subscribers:
            try:
                q.put_nowait(frame)
            except queue.Full:
                logger.debug("Descartando frame: cola llena")

    @staticmethod
    def list_input_devices() -> list[str]:
        devices = sd.query_devices()
        return [f"{idx}: {device['name']}" for idx, device in enumerate(devices)]


__all__ = ["AudioStream"]
