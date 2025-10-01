from __future__ import annotations

import argparse
import threading
import time
from pathlib import Path

from loguru import logger

from .audio_stream import AudioStream
from .config import AppConfig, ensure_directories, load_config, project_root
from .logger import configure_logging
from .recorder import Recorder, RecordingResult
from .tray import TrayIcon, open_path_in_explorer
from .uploader import UploadMeta, Uploader
from .utils import NotificationManager, RepeatedTimer
from .wake_detector import WakeDetector


class KayListenerApp:
    def __init__(self, config: AppConfig) -> None:
        ensure_directories()
        configure_logging(config.log_level)
        self.config = config
        self.notifier = NotificationManager()
        self.audio_stream = AudioStream(config)
        self.recorder = Recorder(config, self.audio_stream)
        from scripts.download_vosk_model import ensure_model

        model_dir = ensure_model(show_progress=False)
        self.wake_detector = WakeDetector(
            config=config,
            audio_stream=self.audio_stream,
            on_wake=self._on_wake_word,
            model_path=model_dir,
        )
        self.uploader = Uploader(config, self.notifier)
        self.listening = True
        self._recording_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._spooler = RepeatedTimer(config.spooler_interval_seconds, self._spool_once)
        if config.auto_start_spooler:
            self._spooler.start()
        icon_path = project_root() / "app" / "assets" / "icon.ico"
        if not icon_path.exists():
            icon_path = None
        self.tray = TrayIcon(
            icon_path=icon_path,
            is_listening=lambda: self.listening,
            toggle_listening=self.toggle_listening,
            test_microphone=self.test_microphone,
            open_logs=self.open_logs,
            on_exit=self.stop,
        )

    def start(self) -> None:
        logger.info("Iniciando Kay Listener")
        self.audio_stream.start()
        self.wake_detector.start()
        self.tray.run()
        self.notifier.show("Kay Listener", "Escuchando...")
        try:
            while not self._stop_event.is_set():
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Interrupción recibida, cerrando...")
            self.stop()

    def stop(self) -> None:
        if self._stop_event.is_set():
            return
        logger.info("Cerrando Kay Listener")
        self._stop_event.set()
        self.wake_detector.stop()
        self.audio_stream.stop()
        self._spooler.stop()
        self.tray.stop()
        self.notifier.show("Kay Listener", "Aplicación detenida")

    def toggle_listening(self) -> None:
        self.listening = not self.listening
        if self.listening:
            logger.info("Escucha reanudada")
            self.wake_detector.resume()
            self.notifier.show("Kay Listener", "Escucha reanudada")
        else:
            logger.info("Escucha pausada")
            self.wake_detector.pause()
            self.notifier.show("Kay Listener", "Escucha pausada")

    def test_microphone(self) -> None:
        logger.info("Grabación de prueba de micrófono")
        result = self.recorder.record_seconds(2.0)
        if result is None:
            self.notifier.show("Kay Listener", "No se pudo grabar audio de prueba")
            return
        self.notifier.show("Kay Listener", f"Grabación de prueba {len(result.audio_bytes)} bytes")

    def open_logs(self) -> None:
        logs_path = project_root() / "logs"
        open_path_in_explorer(logs_path)

    def _on_wake_word(self) -> None:
        if not self.listening:
            logger.debug("Wake word ignorada: escucha en pausa")
            return
        if not self._recording_lock.acquire(blocking=False):
            logger.info("Wake word ignorada: grabación en curso")
            return
        threading.Thread(target=self._capture_and_send, name="RecorderThread", daemon=True).start()

    def _capture_and_send(self) -> None:
        try:
            self.notifier.show("Kay Listener", "Grabando...")
            result = self.recorder.record_until_silence(self._stop_event)
            if result is None:
                self.notifier.show("Kay Listener", "Grabación cancelada")
                return
            self._send_recording(result)
        finally:
            self._recording_lock.release()
            self.wake_detector.resume()

    def _send_recording(self, result: RecordingResult) -> None:
        meta = UploadMeta(
            duration_ms=result.duration_ms,
            wake_word=result.wake_word,
            timestamp_iso=result.timestamp_iso,
        )
        success = self.uploader.upload(result.audio_bytes, meta)
        if success:
            logger.info("Grabación enviada (%sms)", result.duration_ms)
        else:
            logger.info("Grabación encolada (%sms)", result.duration_ms)

    def _spool_once(self) -> None:
        self.uploader.process_outbox_once()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Kay Listener")
    parser.add_argument("--list-devices", action="store_true", help="Lista dispositivos de entrada disponibles")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    config = load_config()
    if args.list_devices:
        for device in AudioStream.list_input_devices():
            print(device)
        return
    app = KayListenerApp(config)
    app.start()


if __name__ == "__main__":
    main()
