"""Message utilities for conversation history management."""

from collections.abc import Sequence

from langchain_core.messages import AnyMessage, SystemMessage


def get_recent_history(
    messages: list[AnyMessage] | None,
    max_messages: int = 6,
) -> Sequence[AnyMessage]:
    """Get recent conversation history for LLM context.

    Filters to last N messages, excluding system messages (which are
    rebuilt each call with current schema context).

    Args:
        messages: Full message history from state.
        max_messages: Maximum messages to return (default: 6 = ~3 turns).

    Returns:
        List of recent messages suitable for LLM prompt inclusion.
    """
    if not messages:
        return []

    # Filter out system messages (they're rebuilt each call)
    non_system = [m for m in messages if not isinstance(m, SystemMessage)]
    return non_system[-max_messages:]
