"""MCP server for the NL2SQL Data Agent.

This module provides the main MCP server implementation, integrating
tools, resources, and prompts for natural language to SQL queries.
"""

import argparse
import logging

from dotenv import load_dotenv

load_dotenv()

from mcp.server.fastmcp import FastMCP

from data_agent.config import CONFIG_DIR
from data_agent.config_loader import ConfigLoader
from data_agent.core.logging import setup_logging
from data_agent.mcp.context import MCPServerContext, set_context
from data_agent.mcp.resources import register_resources
from data_agent.mcp.tools import register_tools

setup_logging()
logger = logging.getLogger(__name__)


def create_mcp_server(
    config_path: str | None = None,
    config_name: str | None = None,
) -> FastMCP:
    """Create and configure the MCP server.

    Args:
        config_path: Path to agent configuration file.
        config_name: Name of config to load from config directory.
            If neither provided, loads all configs.

    Returns:
        Configured FastMCP server instance.
    """
    # Load configuration
    if config_path:
        config = ConfigLoader.load(config_path)
    elif config_name:
        config = ConfigLoader.load_by_name(config_name)
    else:
        config = ConfigLoader.load_all()

    # Create and set context (thread-safe)
    ctx = MCPServerContext(config)
    set_context(ctx)

    # Create the MCP server
    mcp = FastMCP(
        "data-agent",
        instructions="""Data Agent is a natural language to SQL platform.
You can query databases using natural language, list available datasources,
and inspect database schemas. Use the 'query' tool to ask questions about data.

IMPORTANT: Always include the SQL query that was executed in your response to the user.
Format results clearly with the data, SQL query used, and any relevant insights.

Available tools:
- query: Execute natural language queries against databases
- list_datasources: See all available data sources
- list_tables: Quick list of tables in a datasource
- get_schema: Get detailed schema information
- validate_sql: Validate SQL syntax without executing

Available resources:
- datasources://list: List of configured datasources
- schema://{datasource}: Database schema for a datasource
- tables://{datasource}: Tables in a datasource""",
    )

    # Register all components
    register_tools(mcp, ctx)
    register_resources(mcp, ctx)

    logger.info(
        f"MCP server created with {len(config.data_agents)} datasource(s) configured"
    )

    return mcp


def get_config_choices() -> list[str]:
    """Get available configuration file names.

    Returns:
        List of config names (without .yaml extension).
    """
    return [f.stem for f in CONFIG_DIR.glob("*.yaml")]


def main() -> None:
    """Main entry point for the MCP server."""
    parser = argparse.ArgumentParser(
        description="Data Agent MCP Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-c",
        "--config",
        choices=get_config_choices() or None,
        default=None,
        help="Configuration name to load (loads all if not specified)",
    )
    parser.add_argument(
        "--config-path",
        type=str,
        default=None,
        help="Path to configuration file",
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="sse",
        help="Transport mechanism (default: sse for VS Code/Cursor)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8002,
        help="Port for SSE transport (default: 8002)",
    )
    parser.add_argument(
        "--log-level",
        choices=["debug", "info", "warning", "error"],
        default="warning",
        help="Logging level (default: warning)",
    )

    args = parser.parse_args()

    mcp = create_mcp_server(
        config_path=args.config_path,
        config_name=args.config,
    )

    if args.transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.settings.host = "127.0.0.1"
        mcp.settings.port = args.port
        mcp.run(transport="sse")


if __name__ == "__main__":
    main()
