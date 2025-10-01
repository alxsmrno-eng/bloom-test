from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Callable

from loguru import logger

try:  # pragma: no cover - UI component
    from PIL import Image
    import pystray
except Exception:  # pragma: no cover - fallback when dependencies missing
    Image = None
    pystray = None


class TrayIcon:  # pragma: no cover - requires Windows environment
    def __init__(
        self,
        icon_path: Path | None,
        is_listening: Callable[[], bool],
        toggle_listening: Callable[[], None],
        test_microphone: Callable[[], None],
        open_logs: Callable[[], None],
        on_exit: Callable[[], None],
    ) -> None:
        self.icon_path = icon_path
        self.is_listening = is_listening
        self.toggle_listening = toggle_listening
        self.test_microphone = test_microphone
        self.open_logs = open_logs
        self.on_exit = on_exit
        self.icon: pystray.Icon | None = None
        if pystray and Image:
            image = self._load_image(icon_path)
            self.icon = pystray.Icon(
                "Kay Listener",
                image,
                "Kay Listener",
                menu=pystray.Menu(
                    pystray.MenuItem(lambda item: self._toggle_label(), self._on_toggle),
                    pystray.MenuItem("Probar micrófono", self._on_test),
                    pystray.MenuItem("Abrir carpeta logs", self._on_open_logs),
                    pystray.MenuItem("Salir", self._on_exit),
                ),
            )
        else:
            logger.warning("pystray o PIL no disponibles, no se creará icono de bandeja")

    def _load_image(self, icon_path: Path | None):
        assert Image is not None  # pragma: no cover - guarded in __init__
        if icon_path and icon_path.exists():
            try:
                return Image.open(icon_path)
            except Exception as exc:  # pragma: no cover - depends on filesystem
                logger.warning("No se pudo cargar icono personalizado: %s", exc)
        logger.info("Usando icono de bandeja por defecto")
        return Image.new("RGBA", (64, 64), (40, 40, 40, 255))

    def _toggle_label(self) -> str:
        return "Pausar escucha" if self.is_listening() else "Iniciar escucha"

    def _on_toggle(self, icon, item) -> None:
        self.toggle_listening()

    def _on_test(self, icon, item) -> None:
        self.test_microphone()

    def _on_open_logs(self, icon, item) -> None:
        self.open_logs()

    def _on_exit(self, icon, item) -> None:
        self.on_exit()
        if self.icon:
            self.icon.stop()

    def run(self) -> None:
        if self.icon:
            self.icon.run_detached()

    def stop(self) -> None:
        if self.icon:
            self.icon.stop()


def open_path_in_explorer(path: Path) -> None:
    if os.name == "nt":
        os.startfile(path)  # type: ignore[attr-defined]
    else:
        subprocess.Popen(["xdg-open", str(path)])
