from __future__ import annotations

from logging import Logger


def log_ui_error(logger: Logger, code: str, error: BaseException, **context: object) -> None:
    context_payload = " ".join(
        f"{key}={value}" for key, value in context.items() if value is not None
    )
    if context_payload:
        logger.warning("%s error=%s %s", code, error, context_payload)
        return
    logger.warning("%s error=%s", code, error)
