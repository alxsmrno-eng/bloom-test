from __future__ import annotations

import json
import queue
import threading
from pathlib import Path
from typing import Callable

from loguru import logger
from vosk import KaldiRecognizer, Model

from .audio_stream import AudioStream
from .config import AppConfig
from .utils import normalize_text, normalize_wake_variants

WAKE_VARIANTS = ["oye kay", "oye kei", "oye key", "oye quey"]


class WakeDetector:
    def __init__(
        self,
        config: AppConfig,
        audio_stream: AudioStream,
        on_wake: Callable[[], None],
        model_path: Path,
    ) -> None:
        self.config = config
        self.audio_stream = audio_stream
        self.on_wake = on_wake
        self.model_path = model_path
        self._model: Model | None = None
        self._recognizer: KaldiRecognizer | None = None
        self._queue = audio_stream.subscribe()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._enabled = threading.Event()
        self._enabled.set()
        self._wake_variants = normalize_wake_variants(WAKE_VARIANTS + [config.wake_word])

    def load(self) -> None:
        if self._model is None:
            logger.info("Cargando modelo Vosk desde %s", self.model_path)
            self._model = Model(model_path=str(self.model_path))
        if self._recognizer is None:
            grammar = json.dumps(list(WAKE_VARIANTS + [self.config.wake_word] + ["[unk]"]))
            self._recognizer = KaldiRecognizer(self._model, self.config.sample_rate, grammar)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self.load()
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="WakeDetector", daemon=True)
        self._thread.start()
        logger.info("WakeDetector iniciado")

    def pause(self) -> None:
        self._enabled.clear()

    def resume(self) -> None:
        self._enabled.set()

    def stop(self) -> None:
        self._stop_event.set()
        self._enabled.set()
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None
        self.audio_stream.unsubscribe(self._queue)

    def _run(self) -> None:
        assert self._recognizer is not None
        while not self._stop_event.is_set():
            try:
                frame = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if not self._enabled.is_set():
                continue
            if self._recognizer.AcceptWaveform(frame):
                result = json.loads(self._recognizer.Result())
                text = result.get("text", "")
                if self._is_wake_word(text):
                    logger.info("Wake word detectada: %s", text)
                    self.on_wake()
                    self._enabled.clear()
            else:
                partial = json.loads(self._recognizer.PartialResult()).get("partial", "")
                if partial and self._is_wake_word(partial):
                    logger.info("Wake word parcial detectada: %s", partial)
                    self.on_wake()
                    self._enabled.clear()

    def _is_wake_word(self, text: str) -> bool:
        normalized = normalize_text(text)
        return bool(normalized) and normalized in self._wake_variants
