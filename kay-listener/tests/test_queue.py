from __future__ import annotations

from pathlib import Path

from app.config import AppConfig, project_root
from app.uploader import UploadMeta, Uploader, requests


class DummyNotifier:
    def show(self, title: str, message: str) -> None:  # pragma: no cover - no-op for tests
        pass


class DummyResponse:
    def __init__(self, status_code: int, text: str = "OK") -> None:
        self.status_code = status_code
        self.text = text


class SequenceSession:
    def __init__(self, outcomes):
        self.outcomes = outcomes
        self.calls = 0

    def post(self, *args, **kwargs):
        outcome = self.outcomes[self.calls]
        self.calls += 1
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def build_config() -> AppConfig:
    return AppConfig(
        webhook_url="https://example.com",
        wake_word="oye kay",
        sample_rate=16000,
        frame_duration_ms=20,
        vad_aggressiveness=2,
        silence_seconds=5.0,
        input_device_index=None,
        log_level="INFO",
        auto_start_spooler=False,
    )


def clean_outbox() -> Path:
    outbox = project_root() / "outbox"
    for file in outbox.glob("*"):
        if file.name == ".gitkeep":
            continue
        file.unlink()
    return outbox


def test_uploader_retries_and_succeeds() -> None:
    clean_outbox()
    config = build_config()
    session = SequenceSession([
        requests.ConnectionError("net"),
        DummyResponse(200),
    ])
    uploader = Uploader(config, DummyNotifier(), session=session)
    meta = UploadMeta(duration_ms=1000, wake_word="oye kay", timestamp_iso="now")
    assert uploader.upload(b"abc", meta) is True
    assert session.calls == 2


def test_uploader_enqueue_and_spooler_success() -> None:
    outbox = clean_outbox()
    config = build_config()
    session = SequenceSession([
        requests.ConnectionError("net"),
        requests.ConnectionError("net"),
        requests.ConnectionError("net"),
        DummyResponse(200),
    ])
    uploader = Uploader(config, DummyNotifier(), session=session)
    meta = UploadMeta(duration_ms=1000, wake_word="oye kay", timestamp_iso="now")
    assert uploader.upload(b"abc", meta) is False
    assert any(outbox.glob("*.wav"))
    uploader.process_outbox_once()
    assert not any(outbox.glob("*.wav"))
