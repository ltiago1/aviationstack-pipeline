"""
Centralized logging utility for training data engineering pipelines.
"""

import logging
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from pathlib import Path

# ─────────────────────────────────────────────
# SECTION 1 — Log Level Map
# A convenience dict so callers can pass strings instead of logging constants.
# ─────────────────────────────────────────────
LEVELS = {
    "debug": logging.DEBUG,  # 10 — fine-grained diagnostics
    "info": logging.INFO,  # 20 — normal pipeline events
    "warning": logging.WARNING,  # 30 — recoverable issues
    "error": logging.ERROR,  # 40 — non-fatal failures
    "critical": logging.CRITICAL,  # 50 — pipeline-stopping failures
}


# ─────────────────────────────────────────────
# SECTION 2 — Formatter Factory
# Builds the log line format. Two flavours:
#   verbose  → timestamp | level | module | message  (for files / CI)
#   simple   → level | message                       (for quick console runs)
# ─────────────────────────────────────────────
def _make_formatter(verbose: bool = True) -> logging.Formatter:
    if verbose:
        fmt = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
        datefmt = "%Y-%m-%d %H:%M:%S"
    else:
        fmt = "%(levelname)-8s | %(message)s"
        datefmt = None
    return logging.Formatter(fmt, datefmt=datefmt)


# ─────────────────────────────────────────────
# SECTION 3 — Handler Builders
# Each function returns a configured handler ready to attach to a logger.
# Keeping handlers separate makes it easy to mix-and-match per environment.
# ─────────────────────────────────────────────
def _console_handler(level: int, verbose: bool = False) -> logging.StreamHandler:
    """Writes to stdout — good for local runs and container logs."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    handler.setFormatter(_make_formatter(verbose))
    return handler


def _file_handler(
    log_dir: str | Path,
    filename: str,
    level: int,
    max_bytes: int = 10 * 1024 * 1024,  # 10 MB per file
    backup_count: int = 5,
) -> RotatingFileHandler:
    """
    Rotating file handler — rolls over when the file hits `max_bytes`,
    keeping the last `backup_count` archives.  Safe for long training runs.
    """
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / filename
    handler = RotatingFileHandler(path, maxBytes=max_bytes, backupCount=backup_count)
    handler.setLevel(level)
    handler.setFormatter(_make_formatter(verbose=True))
    return handler


def _daily_file_handler(
    log_dir: str | Path,
    base_name: str = "pipeline",
    level: int = logging.DEBUG,
    backup_count: int = 14,  # keep two weeks of daily logs
) -> TimedRotatingFileHandler:
    """
    Time-based rotation — creates a new file at midnight each day.
    Useful when you want logs organised by date rather than size.
    """
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / f"{base_name}.log"
    handler = TimedRotatingFileHandler(
        path, when="midnight", interval=1, backupCount=backup_count
    )
    handler.setLevel(level)
    handler.setFormatter(_make_formatter(verbose=True))
    return handler


# ─────────────────────────────────────────────
# SECTION 4 — Main Factory Function
# Single entry-point used throughout the project.
# Returns a named logger; calling get_logger() twice with the same name
# returns the *same* object (Python's logging module deduplicates them).
# ─────────────────────────────────────────────
def get_logger(
    name: str = "data_pipeline",
    level: str = "info",
    log_dir: str | Path | None = "logs",
    log_file: str | None = None,
    console: bool = True,
    rotate_daily: bool = False,
) -> logging.Logger:
    """
    Get (or create) a named logger.

    Parameters
    ----------
    name         : logger name — use __name__ in each module for clean hierarchy
    level        : minimum severity to capture ("debug", "info", "warning", …)
    log_dir      : directory for log files; pass None to disable file logging
    log_file     : explicit filename; auto-generated with timestamp if None
    console      : whether to echo logs to stdout
    rotate_daily : use time-based rotation instead of size-based

    Returns
    -------
    logging.Logger
    """
    logger = logging.getLogger(name)

    # Guard: don't add duplicate handlers if logger was already configured.
    if logger.handlers:
        return logger

    log_level = LEVELS.get(level.lower(), logging.INFO)
    logger.setLevel(log_level)
    logger.propagate = False  # prevent double-printing via root logger

    # Console handler
    if console:
        logger.addHandler(_console_handler(log_level, verbose=False))

    # File handler
    if log_dir is not None:
        if log_file is None:
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = f"{name}_{stamp}.log"

        if rotate_daily:
            logger.addHandler(
                _daily_file_handler(log_dir, base_name=name, level=log_level)
            )
        else:
            logger.addHandler(_file_handler(log_dir, log_file, level=log_level))

    return logger


# ─────────────────────────────────────────────
# SECTION 5 — Pipeline-Stage Helper
# Data pipelines have named stages (ingest, transform, store, …).
# This wrapper automatically prefixes every message with the stage name,
# so you can grep logs by stage without adding boilerplate in each module.
# ─────────────────────────────────────────────
class StageLogger:
    """Thin wrapper that tags every log line with a pipeline stage name."""

    def __init__(self, stage: str, logger: logging.Logger):
        self.stage = stage
        self._log = logger

    def _tag(self, msg: str) -> str:
        return f"[{self.stage.upper()}] {msg}"

    def debug(self, msg: str, *args, **kwargs):
        self._log.debug(self._tag(msg), *args, **kwargs)

    def info(self, msg: str, *args, **kwargs):
        self._log.info(self._tag(msg), *args, **kwargs)

    def warning(self, msg: str, *args, **kwargs):
        self._log.warning(self._tag(msg), *args, **kwargs)

    def error(self, msg: str, *args, **kwargs):
        self._log.error(self._tag(msg), *args, **kwargs)

    def critical(self, msg: str, *args, **kwargs):
        self._log.critical(self._tag(msg), *args, **kwargs)

    def exception(self, msg: str, *args, **kwargs):
        """Logs ERROR + full traceback — use inside except blocks."""
        self._log.exception(self._tag(msg), *args, **kwargs)


def get_stage_logger(stage: str, **kwargs) -> StageLogger:
    """Convenience constructor: get_stage_logger('tokenise', level='debug')"""
    base = get_logger(name=stage, **kwargs)
    return StageLogger(stage=stage, logger=base)


# ─────────────────────────────────────────────
# SECTION 6 — Quick Smoke-Test
# Run `python logger.py` directly to verify everything is wired up.
# ─────────────────────────────────────────────
if __name__ == "__main__":
    log = get_logger("smoke_test", level="debug", log_dir="logs/test")
    log.debug("debug message — fine-grained detail")
    log.info("info message — normal event")
    log.warning("warning — something looks off")
    log.error("error — something failed but pipeline continues")

    stage_log = get_stage_logger("tokenise", level="debug", log_dir="logs/test")
    stage_log.info("starting tokenisation")
    try:
        raise ValueError("bad token encoding")
    except ValueError:
        stage_log.exception("tokenisation crashed")
