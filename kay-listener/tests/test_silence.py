from __future__ import annotations

from app.recorder import SilenceDetector


def test_silence_detector_waits_until_threshold() -> None:
    detector = SilenceDetector(silence_seconds=1.0, frame_duration=0.1)
    # 9 frames of silencio no completan 1 segundo
    for _ in range(9):
        assert detector.mark(False) is False
    # Al llegar a 10 frames (1 segundo) debe disparar
    assert detector.mark(False) is True


def test_silence_detector_resets_with_voice() -> None:
    detector = SilenceDetector(silence_seconds=0.5, frame_duration=0.1)
    for _ in range(4):
        assert detector.mark(False) is False
    detector.mark(True)
    assert detector.mark(False) is False
