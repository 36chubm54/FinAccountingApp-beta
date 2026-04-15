import ctypes
import logging
import os

APP_LANGUAGE = "ru"
APP_THEME = "light"
_LOGGER = logging.getLogger(__name__)


def _enable_windows_dpi_awareness() -> None:
    """Enable high-DPI awareness early so Tk and native file dialogs stay sharp."""
    if os.name != "nt":
        return
    errors: list[str] = []

    try:
        user32 = ctypes.windll.user32
    except Exception as exc:
        _LOGGER.debug("DPI awareness skipped: user32 is unavailable: %s", exc)
        return

    try:
        # Best quality on modern Windows: Per-Monitor v2.
        if hasattr(user32, "SetProcessDpiAwarenessContext"):
            per_monitor_v2 = ctypes.c_void_p(-4)
            if user32.SetProcessDpiAwarenessContext(per_monitor_v2):
                _LOGGER.debug("DPI awareness enabled via SetProcessDpiAwarenessContext(PMv2).")
                return
            errors.append("SetProcessDpiAwarenessContext returned 0")
    except Exception as exc:
        errors.append(f"SetProcessDpiAwarenessContext failed: {exc}")

    try:
        # Fallback for Windows 8.1+.
        shcore = ctypes.windll.shcore
        if hasattr(shcore, "SetProcessDpiAwareness"):
            # 2 == PROCESS_PER_MONITOR_DPI_AWARE
            shcore.SetProcessDpiAwareness(2)
            _LOGGER.debug("DPI awareness enabled via SetProcessDpiAwareness(2).")
            return
        errors.append("SetProcessDpiAwareness is unavailable")
    except Exception as exc:
        errors.append(f"SetProcessDpiAwareness failed: {exc}")

    try:
        # Legacy fallback for older Windows versions.
        if hasattr(user32, "SetProcessDPIAware"):
            user32.SetProcessDPIAware()
            _LOGGER.debug("DPI awareness enabled via SetProcessDPIAware().")
            return
        errors.append("SetProcessDPIAware is unavailable")
    except Exception as exc:
        errors.append(f"SetProcessDPIAware failed: {exc}")

    if errors:
        _LOGGER.warning("DPI awareness was not enabled. Details: %s", " | ".join(errors))


if __name__ == "__main__":
    from gui.i18n import set_language
    from gui.tkinter_gui import main
    from gui.ui_theme import set_theme

    # Basic logging configuration for the application
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    _enable_windows_dpi_awareness()
    set_language(os.getenv("FIN_ACCOUNTING_LANG", APP_LANGUAGE))
    set_theme(os.getenv("FIN_ACCOUNTING_THEME", APP_THEME))
    main()
