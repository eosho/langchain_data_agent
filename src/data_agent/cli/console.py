"""Rich console configuration and theming."""

from rich.console import Console
from rich.theme import Theme

# Custom theme for consistent styling
THEME = Theme(
    {
        "info": "cyan",
        "success": "green",
        "warning": "yellow",
        "error": "red bold",
        "highlight": "magenta",
        "muted": "dim",
        "agent": "blue bold",
        "sql": "green",
        "config": "cyan",
    }
)

# Singleton console instance
console = Console(theme=THEME)

# Error console for stderr
err_console = Console(theme=THEME, stderr=True)


def print_error(message: str) -> None:
    """Print an error message to stderr.

    Args:
        message: The error message to display.
    """
    err_console.print(f"[error]✗[/error] {message}")
