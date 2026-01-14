"""MCP (Model Context Protocol) server for the NL2SQL Data Agent.

The MCP server exposes:
- Tools: query, list_datasources, list_tables, get_schema, validate_sql
- Resources: datasources://list, schema://{datasource}, tables://{datasource}
"""

from data_agent.mcp.context import MCPServerContext, set_context
from data_agent.mcp.server import create_mcp_server, main

__all__ = [
    "create_mcp_server",
    "main",
    "MCPServerContext",
    "set_context",
]
