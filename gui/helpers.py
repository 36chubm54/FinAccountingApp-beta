import logging
import os
import platform
import subprocess

logger = logging.getLogger(__name__)


def open_in_file_manager(path: str | None) -> None:
    """Open folder in OS file manager in a cross-platform way."""
    try:
        if not path:
            return
        if os.name == "nt":
            os.startfile(path)
            return
        system = platform.system()
        if system == "Darwin":
            subprocess.Popen(["open", path])
        else:
            # Assume Linux/Unix
            subprocess.Popen(["xdg-open", path])
    except Exception:
        logger.exception("Failed to open file manager for %s", path)
