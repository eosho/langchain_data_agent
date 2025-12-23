"""Output formatters for CLI display."""

from rich.panel import Panel
from rich.syntax import Syntax

from data_agent.cli.console import console, err_console
from data_agent.utils.sql_utils import pretty_sql


def print_sql(
    sql: str, title: str = "Generated SQL", dialect: str | None = None
) -> None:
    """Print SQL with syntax highlighting in a panel.

    Args:
        sql: The SQL query string to display.
        title: The panel title.
        dialect: SQL dialect for formatting.
    """
    formatted_sql = pretty_sql(sql, dialect=dialect)
    syntax = Syntax(formatted_sql, "sql", theme="monokai", line_numbers=False)
    panel = Panel(syntax, title=f"[sql]{title}[/sql]", border_style="green")
    console.print(panel)


def print_response(response: str) -> None:
    """Print the final response from the agent in a panel.

    Args:
        response: The response text to display.
    """
    panel = Panel(
        response,
        title="[success]Response[/success]",
        border_style="green",
        padding=(1, 2),
    )
    console.print(panel)


def print_error_panel(error: str, title: str = "Error") -> None:
    """Print an error message in a styled panel.

    Args:
        error: The error message to display.
        title: The panel title.
    """
    panel = Panel(
        f"[error]{error}[/error]",
        title=f"[error]{title}[/error]",
        border_style="red",
    )
    err_console.print(panel)


def print_dashboard(config_name: str, agents: list[dict[str, str]]) -> None:
    """Print the dashboard view with config info and available agents.

    Args:
        config_name: Name of the active configuration.
        agents: List of agent dictionaries with 'name' and 'description' keys.
    """
    from rich.align import Align
    from rich.console import Group
    from rich.panel import Panel
    from rich.text import Text

    banner = """
╔╦╗╔═╗╔╦╗╔═╗  ╔═╗╔═╗╔═╗╔╗╔╔╦╗
 ║║╠═╣ ║ ╠═╣  ╠═╣║ ╦║╣ ║║║ ║
═╩╝╩ ╩ ╩ ╩ ╩  ╩ ╩╚═╝╚═╝╝╚╝ ╩
"""
    banner_text = Text(banner.strip(), style="cyan bold")
    subtitle = Text("Natural Language → SQL Query Engine", style="dim")

    config_line = Text()
    config_line.append("📊 Config: ", style="dim")
    config_line.append(config_name, style="cyan bold")

    agent_names = [agent.get("name", "") for agent in agents]
    agents_line = Text()
    agents_line.append(f"🏢 Agents ({len(agents)}): ", style="dim")
    agents_line.append(" · ".join(agent_names), style="blue")

    content = Group(
        Align.center(banner_text),
        Align.center(subtitle),
        Text(""),
        Align.center(config_line),
        Align.center(agents_line),
    )

    outer_panel = Panel(
        content,
        border_style="cyan",
        padding=(1, 2),
    )
    console.print()
    console.print(outer_panel)
    console.print()


def print_query_info(
    question: str,
    agent: str | None = None,
    sql: str | None = None,
    rewritten_question: str | None = None,
) -> None:
    """Print query information in a styled panel.

    Displays the user's question, the routed agent, and optionally
    the generated SQL query.

    Args:
        question: The user's natural language question.
        agent: Name of the agent handling the query.
        sql: The generated SQL query to display.
        rewritten_question: The rewritten question (if different from original).
    """
    from rich.text import Text

    content = Text()
    content.append("❓ Question: ", style="dim")
    content.append(question, style="white")

    if rewritten_question and rewritten_question != question:
        content.append("\n✏️  Rewritten: ", style="dim")
        content.append(rewritten_question, style="yellow")

    if agent:
        content.append("\n🔀 Routed to agent ", style="dim")
        content.append(agent, style="blue bold")

    panel = Panel(
        content,
        title="[bold]Query[/bold]",
        border_style="magenta",
        padding=(0, 1),
    )
    console.print(panel)

    if sql:
        print_sql(sql)
