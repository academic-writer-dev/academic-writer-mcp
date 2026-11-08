"""Journalisation.

- stderr (stdout est réservé au protocole MCP en stdio) ;
- fichier tournant ``<data_dir>/logs/academic-writer.log`` (5 Mo x 5).

Règle : ne jamais journaliser le contenu des documents ni leurs noms complets ;
seulement des identifiants, extensions, tailles et codes d'erreur.
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from academic_writer.core.config import Settings

LOGGER_NAME = "academic_writer"
_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def configure_logging(settings: Settings | None = None) -> logging.Logger:
    # Windows utilise cp1252 par défaut pour stderr : on force l'UTF-8 (accents, cyrillique).
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")

    formatter = logging.Formatter(_FORMAT)
    handlers: list[logging.Handler] = []

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(formatter)
    handlers.append(stderr_handler)

    level = logging.INFO
    if settings is not None:
        level = getattr(logging, settings.log_level)
        settings.logs_dir.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            settings.logs_dir / "academic-writer.log",
            maxBytes=5 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)

    logger = logging.getLogger(LOGGER_NAME)
    for old in logger.handlers:
        old.close()
    logger.handlers[:] = handlers
    logger.setLevel(level)
    logger.propagate = False
    return logger
