"""MCP resource definitions for the Data Agent."""

import logging

from mcp.server.fastmcp import FastMCP

from data_agent.mcp.context import MCPServerContext

logger = logging.getLogger(__name__)


def register_resources(mcp: FastMCP, ctx: MCPServerContext) -> None:
    """Register all MCP resources for the Data Agent.

    Args:
        mcp: FastMCP server instance.
        ctx: Server context with agent and configuration.
    """

    @mcp.resource("datasources://list")
    async def datasources_list() -> str:
        """List of available datasources as a resource.

        Returns:
            Formatted list of datasources with descriptions.
        """
        lines = ["Available Datasources:", ""]
        for agent_cfg in ctx.config.data_agents:
            desc = agent_cfg.description or "No description"
            lines.append(f"- {agent_cfg.name}: {desc}")

        return "\n".join(lines)

    @mcp.resource("schema://{datasource}")
    async def schema_resource(datasource: str) -> str:
        """Database schema as a readable resource.

        Args:
            datasource: Name of the datasource.

        Returns:
            Schema information for the datasource.
        """
        if datasource not in ctx.agent.datasources:
            return f"Datasource '{datasource}' not found."

        ds = ctx.agent.datasources[datasource]

        from langchain_community.utilities.sql_database import SQLDatabase

        from data_agent.adapters import CosmosAdapter

        if isinstance(ds, SQLDatabase):
            schema_info = ds.get_table_info()
            return schema_info or f"No schema information for '{datasource}'."
        elif isinstance(ds, CosmosAdapter):
            return (
                f"Cosmos DB container: {ds.container_name}\n"
                f"Partition key: {ds.partition_key_path}"
            )

        return f"Schema not available for '{datasource}'."

    @mcp.resource("tables://{datasource}")
    async def tables_resource(datasource: str) -> str:
        """List of tables in a datasource as a resource.

        Args:
            datasource: Name of the datasource.

        Returns:
            List of table names.
        """
        if datasource not in ctx.agent.datasources:
            return f"Datasource '{datasource}' not found."

        ds = ctx.agent.datasources[datasource]

        from langchain_community.utilities.sql_database import SQLDatabase

        from data_agent.adapters import CosmosAdapter

        if isinstance(ds, SQLDatabase):
            tables = ds.get_usable_table_names()
            return "\n".join(sorted(tables)) if tables else "No tables found."
        elif isinstance(ds, CosmosAdapter):
            return ds.container_name

        return f"Table listing not available for '{datasource}'."
