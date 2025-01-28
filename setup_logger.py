import logging

from config import LOG_LEVEL


def setup_logger() -> None:
    # Ensure that all loggers have a stream handler (console output)
    LOGGERS = [logging.getLogger(name) for name in logging.root.manager.loggerDict]

    for _logger in LOGGERS:
        # Set the logger level
        _logger.setLevel(LOG_LEVEL)

        # Add StreamHandler to output to console
        if not _logger.handlers:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(
                logging.Formatter("%(name)s - %(levelname)s - %(message)s")
            )
            _logger.addHandler(console_handler)

    # Disable all Uvicorn logs
    logging.getLogger("uvicorn").setLevel(logging.CRITICAL)
    logging.getLogger("uvicorn.error").setLevel(logging.CRITICAL)
    logging.getLogger("uvicorn.access").setLevel(logging.CRITICAL)
    logging.getLogger("uvicorn.lifespan").setLevel(logging.CRITICAL)

    # Disable uvicorn access logs
    uvicorn_access = logging.getLogger("uvicorn.access")
    uvicorn_access.disabled = True
