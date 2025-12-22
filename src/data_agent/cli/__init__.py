"""CLI entry point for Data Agent."""

import warnings

from sqlalchemy.exc import SAWarning

from data_agent.cli.app import app

# Suppress deprecation warnings from third-party libraries
warnings.filterwarnings(
    "ignore",
    message=".*_user_agent_entry.*deprecated.*",
    category=DeprecationWarning,
)

# Suppress SQLAlchemy caching warnings from third-party dialects (databricks-sqlalchemy)
warnings.filterwarnings(
    "ignore",
    message=".*will not make use of SQL compilation caching.*",
    category=SAWarning,
)


def main() -> None:
    """Main entry point for the CLI."""
    app()


__all__ = ["app", "main"]
