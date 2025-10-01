from __future__ import annotations

import json
import threading
import time
import unicodedata
from pathlib import Path
from typing import Iterable

try:
    from loguru import logger
except ImportError:  # pragma: no cover - fallback for testing
    class _DummyLogger:
        def __getattr__(self, name):
            def _noop(*args, **kwargs):
                pass
            return _noop

    logger = _DummyLogger()


from .config import project_root


class NotificationManager:
    """Wrapper around win10toast notifications with graceful fallback."""

    def __init__(self, app_name: str = "Kay Listener") -> None:
        self.app_name = app_name
        try:
            from win10toast import ToastNotifier

            self._toaster = ToastNotifier()
        except Exception as exc:  # pragma: no cover - depends on OS
            logger.debug("No se pudo inicializar ToastNotifier: %s", exc)
            self._toaster = None

    def show(self, title: str, message: str, duration: int = 5) -> None:
        if self._toaster is None:
            logger.info("NOTIFY %s - %s", title, message)
            return
        try:
            self._toaster.show_toast(title, message, duration=duration, threaded=True)
        except Exception as exc:  # pragma: no cover
            logger.warning("No se pudo mostrar notificación: %s", exc)


def timestamp_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def base_dir() -> Path:
    return project_root()


def logs_dir() -> Path:
    return base_dir() / "logs"


def outbox_dir() -> Path:
    directory = base_dir() / "outbox"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value)
    stripped = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return "".join(stripped.lower().split())


def normalize_wake_variants(variants: Iterable[str]) -> set[str]:
    return {normalize_text(item) for item in variants}


class RepeatedTimer:
    """Simple repeated timer utility for the spooler."""

    def __init__(self, interval: float, function, *args, **kwargs) -> None:
        self.interval = interval
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="SpoolerTimer", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop_event.is_set():
            start = time.monotonic()
            self.function(*self.args, **self.kwargs)
            elapsed = time.monotonic() - start
            wait_time = max(0.1, self.interval - elapsed)
            self._stop_event.wait(wait_time)

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None


def save_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
