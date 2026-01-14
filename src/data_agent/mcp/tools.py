"""MCP tool definitions for the Data Agent."""

import logging
from typing import Any

from mcp.server.fastmcp import FastMCP

from data_agent.mcp.context import MCPServerContext
from data_agent.models.state import OutputState

logger = logging.getLogger(__name__)


def register_tools(mcp: FastMCP, ctx: MCPServerContext) -> None:
    """Register all MCP tools for the Data Agent.

    Args:
        mcp: FastMCP server instance.
        ctx: Server context with agent and configuration.
    """

    @mcp.tool()
    async def query(question: str, datasource: str | None = None) -> str:
        """Execute a natural language query against the configured datasources.

        Args:
            question: Natural language question to answer (e.g., "What are the top 10 customers by revenue?")
            datasource: Optional specific datasource name to target. If not provided, the agent will auto-detect.

        Returns:
            Query results as formatted text, including the SQL query used and the data returned.
        """
        logger.debug(f"MCP query tool called with question: {question}")
        logger.info(f"Executing query {question} on datasource: {datasource}")

        try:
            result = await ctx.agent.run(question)
            logger.info("Query execution completed")
            return _format_query_result(result)

        except Exception as e:
            logger.exception("Error executing query")
            return f"Error executing query: {e}"

    @mcp.tool()
    async def list_datasources() -> str:
        """List all configured datasources available for querying.

        Returns:
            Formatted list of available datasources with their descriptions.
        """
        datasources = []
        for agent_cfg in ctx.config.data_agents:
            ds_type = "unknown"
            if agent_cfg.datasource:
                ds_type = (
                    type(agent_cfg.datasource)
                    .__name__.replace("Datasource", "")
                    .lower()
                )

            ds_info = f"- **{agent_cfg.name}** ({ds_type})"
            if agent_cfg.description:
                ds_info += f": {agent_cfg.description}"

            if agent_cfg.table_schemas:
                tables = [schema.name for schema in agent_cfg.table_schemas]
                ds_info += f"\n  Tables: {', '.join(tables)}"

            datasources.append(ds_info)

        if not datasources:
            return "No datasources configured."

        return "**Available Datasources:**\n\n" + "\n\n".join(datasources)

    @mcp.tool()
    async def list_tables(datasource: str) -> str:
        """List all tables available in a specific datasource.

        Args:
            datasource: Name of the datasource to list tables for.

        Returns:
            List of table names in the datasource.
        """
        if datasource not in ctx.agent.datasources:
            available = ", ".join(ctx.agent.datasources.keys())
            return f"Datasource '{datasource}' not found. Available: {available}"

        ds = ctx.agent.datasources[datasource]

        try:
            from langchain_community.utilities.sql_database import SQLDatabase

            from data_agent.adapters import CosmosAdapter

            if isinstance(ds, SQLDatabase):
                tables = ds.get_usable_table_names()
                if tables:
                    return f"**Tables in {datasource}:**\n\n" + "\n".join(
                        f"- {t}" for t in sorted(tables)
                    )
                return f"No tables found in '{datasource}'."
            elif isinstance(ds, CosmosAdapter):
                return f"**Container in {datasource}:**\n\n- {ds.container_name}"
            else:
                return f"Table listing not supported for datasource '{datasource}'."

        except Exception as e:
            logger.exception("Error listing tables")
            return f"Error listing tables: {e}"

    @mcp.tool()
    async def get_schema(datasource: str) -> str:
        """Get the database schema for a specific datasource.

        Args:
            datasource: Name of the datasource to get schema for (use list_datasources to see available options)

        Returns:
            Database schema information including tables, columns, and their types.
        """
        if datasource not in ctx.agent.datasources:
            available = ", ".join(ctx.agent.datasources.keys())
            return f"Datasource '{datasource}' not found. Available: {available}"

        ds = ctx.agent.datasources[datasource]

        try:
            from langchain_community.utilities.sql_database import SQLDatabase

            from data_agent.adapters import CosmosAdapter

            if isinstance(ds, SQLDatabase):
                schema_info = ds.get_table_info()
                if schema_info:
                    return f"**Schema for {datasource}:**\n\n{schema_info}"
                return f"No schema information available for '{datasource}'."
            elif isinstance(ds, CosmosAdapter):
                return (
                    f"**Schema for {datasource}:**\n\n"
                    f"Cosmos DB container: {ds.container_name}\n"
                    f"Partition key: {ds.partition_key_path}\n\n"
                    "Note: Cosmos DB is a NoSQL database. Use queries like 'SELECT * FROM c' to explore data."
                )
            else:
                return f"Schema inspection not supported for datasource '{datasource}'."

        except Exception as e:
            logger.exception("Error getting schema")
            return f"Error retrieving schema: {e}"

    @mcp.tool()
    async def validate_sql(sql: str, datasource: str) -> str:
        """Validate SQL syntax without executing the query.

        Args:
            sql: The SQL query to validate.
            datasource: Name of the datasource to validate against (for dialect detection).

        Returns:
            Validation result indicating if the SQL is valid, with any errors or warnings.
        """
        if datasource not in ctx.agent.datasources:
            available = ", ".join(ctx.agent.datasources.keys())
            return f"Datasource '{datasource}' not found. Available: {available}"

        try:
            from data_agent.validators.sql_validator import (
              SQLValidator,
              ValidationStatus,
            )

            # Get dialect from datasource config
            dialect = "postgres"  # default
            for agent_cfg in ctx.config.data_agents:
                if agent_cfg.name == datasource and agent_cfg.datasource:
                    ds_type = type(agent_cfg.datasource).__name__.lower()
                    if "cosmos" in ds_type:
                        dialect = "cosmosdb"
                    elif "synapse" in ds_type or "azuresql" in ds_type:
                        dialect = "tsql"
                    elif "bigquery" in ds_type:
                        dialect = "bigquery"
                    elif "databricks" in ds_type:
                        dialect = "databricks"
                    break

            validator = SQLValidator(dialect=dialect)
            result = validator.validate(sql)

            response_parts = [f"**SQL Validation Result:**\n"]

            if result.status == ValidationStatus.VALID:
                response_parts.append("✅ **Status:** Valid\n")
                if result.query != sql:
                    response_parts.append(
                        f"**Transformed Query:**\n```sql\n{result.query}\n```\n"
                    )
            elif result.status == ValidationStatus.INVALID:
                response_parts.append("❌ **Status:** Invalid\n")
            else:
                response_parts.append("⚠️ **Status:** Unsafe\n")

            if result.errors:
                response_parts.append(
                    f"**Errors:**\n" + "\n".join(f"- {e}" for e in result.errors)
                )

            if result.warnings:
                response_parts.append(
                    f"\n**Warnings:**\n" + "\n".join(f"- {w}" for w in result.warnings)
                )

            return "\n".join(response_parts)

        except Exception as e:
            logger.exception("Error validating SQL")
            return f"Error validating SQL: {e}"


def _format_query_result(result: OutputState | dict[str, Any]) -> str:
    """Format query result into a readable response.

    Args:
        result: Query result dictionary or OutputState from the agent.

    Returns:
        Formatted string response.
    """
    if not isinstance(result, dict):
        result = dict(result)

    response_parts = []

    if result.get("final_response"):
        response_parts.append(str(result.get("final_response")))

    if result.get("generated_sql"):
        response_parts.append(
            f"\n**SQL Query:**\n```sql\n{result.get('generated_sql')}\n```"
        )

    if result.get("result") and not result.get("final_response"):
        response_parts.append(f"\n**Results:**\n{result.get('result')}")

    if result.get("visualization_image"):
        img_data = result.get("visualization_image")
        response_parts.append(
            f"\n**Visualization:**\n![Chart](data:image/png;base64,{img_data})"
        )

    if result.get("visualization_code"):
        response_parts.append(
            f"\n**Visualization Code:**\n```python\n{result.get('visualization_code')}\n```"
        )

    if result.get("visualization_error"):
        response_parts.append(
            f"\n**Visualization Error:** {result.get('visualization_error')}"
        )

    if result.get("error") and result.get("error") != "out_of_scope":
        response_parts.append(f"\n**Error:** {result.get('error')}")

    return "\n".join(response_parts) if response_parts else "No results returned."
