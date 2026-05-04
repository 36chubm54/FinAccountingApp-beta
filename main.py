import logging
import os

APP_LANGUAGE = "ru"
APP_THEME = "light"

if __name__ == "__main__":
    from gui.i18n import set_language
    from gui.tkinter_gui import _enable_windows_dpi_awareness, main
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
