from __future__ import annotations

import argparse
import io
import wave

import sounddevice as sd

from app.config import ensure_directories, load_config
from app.logger import configure_logging
from app.uploader import Uploader, UploadMeta
from app.utils import NotificationManager


def record_audio(sample_rate: int, seconds: float) -> bytes:
    frames = int(sample_rate * seconds)
    recording = sd.rec(frames, samplerate=sample_rate, channels=1, dtype="int16")
    sd.wait()
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(recording.tobytes())
    return buffer.getvalue()


def main() -> None:
    parser = argparse.ArgumentParser(description="Kay Listener self test")
    parser.add_argument("--duration", type=float, default=3.0, help="Duración en segundos")
    parser.add_argument("--dry-run", action="store_true", help="No envía el audio, solo muestra metadatos")
    args = parser.parse_args()

    ensure_directories()
    config = load_config()
    configure_logging("INFO")

    print(f"Grabando {args.duration}s de audio...")
    audio_bytes = record_audio(config.sample_rate, args.duration)
    meta = UploadMeta(duration_ms=int(args.duration * 1000), wake_word=config.wake_word, timestamp_iso="self-test")

    print(f"WAV generado ({len(audio_bytes)} bytes)")
    if args.dry_run:
        print("DRY-RUN: no se envía el audio")
        return

    if not config.webhook_url:
        print("WEBHOOK_URL no configurada. Configura .env antes de enviar.")
        return

    uploader = Uploader(config, NotificationManager())
    uploader.upload(audio_bytes, meta)


if __name__ == "__main__":
    main()
