from __future__ import annotations

import shutil
import sys
import zipfile
from pathlib import Path
from typing import Optional

import requests

MODEL_URL = "https://alphacephei.com/vosk/models/vosk-model-small-es-0.42.zip"
MODEL_FOLDER_NAME = "vosk-model-small-es-0.42"


def ensure_model(destination: Optional[Path] = None, show_progress: bool = True) -> Path:
    root = Path(__file__).resolve().parents[1]
    models_dir = destination or (root / "models" / "vosk-es")
    models_dir.parent.mkdir(parents=True, exist_ok=True)

    if models_dir.exists() and any(models_dir.iterdir()):
        return models_dir

    tmp_zip = root / "models" / "vosk_model.zip"
    download_file(MODEL_URL, tmp_zip, show_progress=show_progress)

    with zipfile.ZipFile(tmp_zip, "r") as zf:
        extracted_dir = root / "models" / MODEL_FOLDER_NAME
        if extracted_dir.exists():
            shutil.rmtree(extracted_dir)
        zf.extractall(root / "models")
        if models_dir.exists():
            shutil.rmtree(models_dir)
        extracted_dir.rename(models_dir)

    tmp_zip.unlink(missing_ok=True)
    return models_dir


def download_file(url: str, target: Path, show_progress: bool = True) -> None:
    with requests.get(url, stream=True, timeout=60) as response:
        response.raise_for_status()
        total = int(response.headers.get("content-length", 0))
        chunk_size = 8192
        downloaded = 0
        with open(target, "wb") as fh:
            for chunk in response.iter_content(chunk_size):
                if chunk:
                    fh.write(chunk)
                    downloaded += len(chunk)
                    if show_progress and total:
                        progress = downloaded / total * 100
                        sys.stdout.write(f"\rDescargando modelo Vosk... {progress:5.1f}%")
                        sys.stdout.flush()
        if show_progress:
            sys.stdout.write("\n")


def main() -> None:
    ensure_model(show_progress=True)
    print("Modelo Vosk listo.")


if __name__ == "__main__":
    main()
