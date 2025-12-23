"""SQL utility functions for cleaning and sanitizing queries."""

import re
from datetime import date

import sqlglot


def _get_current_date() -> str:
    """Return current date in ISO format.

    Returns:
        Current date as ISO format string (YYYY-MM-DD).
    """
    return date.today().isoformat()


def build_date_context() -> str:
    """Build date context string for prompts.

    Provides comprehensive temporal context to help the LLM interpret
    relative date references accurately in SQL queries.

    Returns:
        Formatted string with current date and temporal context.
    """
    today = date.fromisoformat(_get_current_date())
    quarter = (today.month - 1) // 3 + 1
    week_number = today.isocalendar()[1]

    return (
        f"Current date: {today.isoformat()} ({today.strftime('%A, %B %d, %Y')})\n"
        f"Current year: {today.year}, Quarter: Q{quarter}, Week: {week_number}\n"
        "Use this context to interpret relative time references like "
        "'today', 'yesterday', 'this week', 'last month', 'this quarter', "
        "'year to date', 'last 7 days', etc.\n\n"
    )


def clean_sql_query(query: str) -> str:
    """Clean a SQL query by removing markdown formatting and extra whitespace.

    LLMs often return SQL wrapped in markdown code blocks. This function
    strips those wrappers and normalizes the query.

    Args:
        query: Raw SQL query string, possibly with markdown formatting.

    Returns:
        Cleaned SQL query string.

    Examples:
        >>> clean_sql_query("```sql\\nSELECT * FROM users\\n```")
        'SELECT * FROM users'
        >>> clean_sql_query("```\\nSELECT 1\\n```")
        'SELECT 1'
        >>> clean_sql_query("SELECT * FROM orders")
        'SELECT * FROM orders'
    """
    if not query:
        return ""

    cleaned = query.strip()

    code_block_pattern = r"^```(?:sql|SQL)?\s*\n?(.*?)\n?```$"
    match = re.match(code_block_pattern, cleaned, re.DOTALL | re.IGNORECASE)
    if match:
        cleaned = match.group(1).strip()

    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
        if cleaned.lower().startswith("sql"):
            cleaned = cleaned[3:]
        cleaned = cleaned.strip()
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()

    cleaned = cleaned.strip().rstrip(";").strip()

    return re.sub(r"\s+", " ", cleaned)


def pretty_sql(query: str, dialect: str | None = None, pretty: bool = True) -> str:
    """Format SQL query with proper indentation.

    Args:
        query: The SQL query to format.
        dialect: SQL dialect for parsing (e.g., 'postgres', 'bigquery').
        pretty: Whether to format with indentation (default True).

    Returns:
        Formatted SQL query, or original if parsing fails.
    """
    try:
        return sqlglot.transpile(
            query,
            read=dialect,
            write=dialect,
            pretty=pretty,
        )[0]
    except Exception:
        return query.strip()
