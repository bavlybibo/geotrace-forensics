from __future__ import annotations

import logging
from pathlib import Path


def setup_logging(log_dir: Path) -> logging.Logger:
    """Create a simple local-only logger for diagnostics without exposing evidence content."""
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("geotrace")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if not any(isinstance(handler, logging.FileHandler) for handler in logger.handlers):
        file_handler = logging.FileHandler(log_dir / "geotrace.log", encoding="utf-8")
        file_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s"))
        logger.addHandler(file_handler)

    if not any(isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler) for handler in logger.handlers):
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(logging.Formatter("%(levelname)s | %(message)s"))
        logger.addHandler(stream_handler)

    return logger
