from __future__ import annotations

try:
    import webrtcvad
except ImportError:  # pragma: no cover - fallback for testing
    class _VadFallback:
        def __init__(self, aggressiveness: int) -> None:
            self.aggressiveness = aggressiveness

        def is_speech(self, frame: bytes, sample_rate: int) -> bool:
            return True

    webrtcvad = type("webrtcvad", (), {"Vad": _VadFallback})()  # type: ignore[assignment]

import io
import queue
import threading
import wave
from dataclasses import dataclass

try:
    from loguru import logger
except ImportError:  # pragma: no cover - fallback for testing
    class _DummyLogger:
        def __getattr__(self, name):
            def _noop(*args, **kwargs):
                pass

            return _noop

    logger = _DummyLogger()

from typing import TYPE_CHECKING

from .config import AppConfig

if TYPE_CHECKING:
    from .audio_stream import AudioStream


@dataclass
class RecordingResult:
    audio_bytes: bytes
    duration_ms: int
    wake_word: str
    timestamp_iso: str


class SilenceDetector:
    def __init__(self, silence_seconds: float, frame_duration: float) -> None:
        self.silence_seconds = silence_seconds
        self.frame_duration = frame_duration
        self.required_frames = max(1, int(silence_seconds / frame_duration))
        self.consecutive_silence = 0

    def mark(self, is_voice: bool) -> bool:
        if is_voice:
            self.consecutive_silence = 0
        else:
            self.consecutive_silence += 1
        return self.consecutive_silence >= self.required_frames


class Recorder:
    def __init__(self, config: AppConfig, audio_stream: AudioStream) -> None:
        self.config = config
        self.audio_stream = audio_stream
        self.vad = webrtcvad.Vad(config.vad_aggressiveness)

    def record_until_silence(self, stop_event: threading.Event | None = None) -> RecordingResult | None:
        frame_queue = self.audio_stream.subscribe(maxsize=200)
        raw_audio = bytearray()
        silence_detector = SilenceDetector(self.config.silence_seconds, self.config.frame_duration_seconds)
        total_frames = 0
        voiced_frames = 0
        try:
            while True:
                if stop_event and stop_event.is_set():
                    logger.info("Grabación cancelada")
                    return None
                try:
                    frame = frame_queue.get(timeout=1)
                except queue.Empty:
                    continue
                total_frames += 1
                raw_audio.extend(frame)
                is_voice = False
                try:
                    is_voice = self.vad.is_speech(bytes(frame), self.config.sample_rate)
                except Exception as exc:
                    logger.warning("Error en VAD: %s", exc)
                if is_voice:
                    voiced_frames += 1
                finished = silence_detector.mark(is_voice)
                if finished and voiced_frames > 0:
                    break
                if total_frames * self.config.frame_duration_seconds > 120:
                    logger.warning("Tiempo máximo de grabación alcanzado")
                    break
        finally:
            self.audio_stream.unsubscribe(frame_queue)

        if voiced_frames == 0:
            logger.warning("No se detectó voz tras la wake word")
            return None

        duration_ms = int(total_frames * self.config.frame_duration_seconds * 1000)
        wav_bytes = self._encode_wav(bytes(raw_audio))
        from .utils import timestamp_iso  # Lazy import to avoid cycles

        return RecordingResult(
            audio_bytes=wav_bytes,
            duration_ms=duration_ms,
            wake_word=self.config.wake_word,
            timestamp_iso=timestamp_iso(),
        )

    def record_seconds(self, seconds: float) -> RecordingResult | None:
        frame_queue = self.audio_stream.subscribe(maxsize=200)
        raw_audio = bytearray()
        frames_needed = int(seconds / self.config.frame_duration_seconds)
        total_frames = 0
        try:
            while total_frames < frames_needed:
                try:
                    frame = frame_queue.get(timeout=1)
                except queue.Empty:
                    continue
                raw_audio.extend(frame)
                total_frames += 1
        finally:
            self.audio_stream.unsubscribe(frame_queue)

        if not raw_audio:
            return None
        duration_ms = int(total_frames * self.config.frame_duration_seconds * 1000)
        wav_bytes = self._encode_wav(bytes(raw_audio))
        from .utils import timestamp_iso

        return RecordingResult(
            audio_bytes=wav_bytes,
            duration_ms=duration_ms,
            wake_word=self.config.wake_word,
            timestamp_iso=timestamp_iso(),
        )

    def _encode_wav(self, pcm_bytes: bytes) -> bytes:
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.config.sample_rate)
            wf.writeframes(pcm_bytes)
        return buffer.getvalue()


__all__ = ["Recorder", "RecordingResult", "SilenceDetector"]
