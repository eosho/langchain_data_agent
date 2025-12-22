"""
Logging configuration for the Terminal Agent.
"""

import logging
import logging.config


def setup_logging(default_level: int = logging.INFO) -> None:
    """Configure structured logging for the entire package."""
    level_name = logging.getLevelName(default_level)
    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": "[%(asctime)s] - [%(levelname)s] - %(name)s: %(message)s",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "standard",
                "level": level_name,
            },
        },
        "root": {
            "handlers": ["console"],
            "level": default_level,
        },
    }

    logging.config.dictConfig(logging_config)

    # Suppress noisy third-party loggers
    noisy_loggers = [
        "databricks.sql",
        "databricks.sdk",
        "azure.cosmos",
        "azure.core.pipeline.policies.http_logging_policy",
        "httpx",
        "azure.identity",
        "chainlit",
    ]
    for logger_name in noisy_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)
