from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - fallback for testing
    def load_dotenv(*args, **kwargs):
        return False

import os


@dataclass
class AppConfig:
    webhook_url: str
    wake_word: str
    sample_rate: int
    frame_duration_ms: int
    vad_aggressiveness: int
    silence_seconds: float
    input_device_index: Optional[int]
    log_level: str
    auto_start_spooler: bool
    spooler_interval_seconds: float = 60.0
    max_retry_attempts: int = 3

    @property
    def frame_duration_seconds(self) -> float:
        return self.frame_duration_ms / 1000.0


def _parse_bool(value: str, default: bool) -> bool:
    if value is None:
        return default
    value = value.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return default


def _parse_device_index(raw: Optional[str]) -> Optional[int]:
    if raw is None:
        return None
    raw = raw.strip().lower()
    if not raw or raw == "auto":
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def load_config(env_path: Optional[Path] = None) -> AppConfig:
    env_file = env_path or Path.cwd() / ".env"
    if env_file.exists():
        load_dotenv(env_file)
    else:
        # Load environment variables from the current process if .env is missing
        load_dotenv()

    webhook_url = os.getenv("WEBHOOK_URL", "").strip()
    wake_word = os.getenv("WAKE_WORD", "oye kay").strip() or "oye kay"
    sample_rate = int(os.getenv("SAMPLE_RATE", "16000"))
    vad_aggressiveness = int(os.getenv("VAD_AGGRESSIVENESS", "2"))
    silence_seconds = float(os.getenv("SILENCE_SECONDS", "5"))
    input_device = _parse_device_index(os.getenv("INPUT_DEVICE_INDEX"))
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    auto_start_spooler = _parse_bool(os.getenv("AUTO_START_SPOOLER", "true"), True)
    frame_duration_ms = 20

    return AppConfig(
        webhook_url=webhook_url,
        wake_word=wake_word,
        sample_rate=sample_rate,
        frame_duration_ms=frame_duration_ms,
        vad_aggressiveness=vad_aggressiveness,
        silence_seconds=silence_seconds,
        input_device_index=input_device,
        log_level=log_level,
        auto_start_spooler=auto_start_spooler,
    )


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def ensure_directories() -> None:
    root = project_root()
    for folder in (root / "logs", root / "outbox", root / "models", root / "models" / "vosk-es"):
        folder.mkdir(parents=True, exist_ok=True)
