import logging

if __name__ == "__main__":
    from gui.tkinter_gui import main

    # Basic logging configuration for the application
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    main()
