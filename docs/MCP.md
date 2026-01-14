# MCP Protocol Support

The Data Agent supports the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/), enabling integration with Claude Desktop, VS Code, Cursor, and other MCP-compatible clients.

## Quick Start

```bash
# Start MCP server with SSE transport (default)
uv run data-agent mcp

# Start with a specific config
uv run data-agent mcp --config contoso

# Start with stdio transport (for Claude Desktop)
uv run data-agent mcp --transport stdio

# Start on a custom port
uv run data-agent mcp --port 9000
```

## Server Options

| Option | Default | Description |
|--------|---------|-------------|
| `--config, -c` | all | Configuration name (e.g., `contoso`). Loads all configs if not specified. |
| `--transport, -t` | sse | Transport: `sse` for HTTP clients (VS Code, Cursor), `stdio` for Claude Desktop |
| `--port, -p` | 8002 | Port for SSE transport |
| `--log-level` | warning | Logging level |

## Available Tools

The MCP server exposes the following tools:

| Tool | Description |
|------|-------------|
| `query` | Execute natural language queries against datasources |
| `list_datasources` | List all configured datasources with descriptions |
| `list_tables` | List tables for a specific datasource |
| `get_schema` | Get database schema for a specific datasource |
| `validate_sql` | Validate SQL syntax without executing |

## Available Resources

| Resource URI | Description |
|--------------|-------------|
| `datasources://list` | List of available datasources |
| `schema://{datasource}` | Database schema for a datasource |
| `tables://{datasource}` | List of tables for a datasource |

## Client Configuration

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "data-agent": {
      "command": "uv",
      "args": ["run", "data-agent-mcp"],
      "cwd": "/path/to/langchain_data_agent"
    }
  }
}
```

### VS Code

Add to `.vscode/mcp.json` in your workspace:

```json
{
  "servers": {
    "data-agent": {
      "type": "sse",
      "url": "http://127.0.0.1:8002/sse"
    }
  }
}
```

> **Note:** Start the MCP server first with `uv run data-agent mcp` before connecting.

Or for stdio transport (runs server automatically):

```json
{
  "servers": {
    "data-agent": {
      "type": "stdio",
      "command": "uv",
      "args": ["run", "data-agent-mcp", "--transport", "stdio"]
    }
  }
}
```

### Cursor / Windsurf

Similar configuration to VS Code. Check your IDE's MCP documentation.

## Example Usage

Once configured, you can interact with the Data Agent directly from your AI client:

```
User: What datasources are available?
AI: [calls list_datasources] → Shows contoso, adventure_works, amex

User: What's the schema for the contoso database?
AI: [calls get_schema("contoso")] → Shows tables, columns, types

User: Show me the top 5 products by sales in Q4 2024
AI: [calls query("top 5 products by sales Q4 2024")] → Returns results
```

## Programmatic Client Example

```python
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    server_params = StdioServerParameters(
        command="uv",
        args=["run", "data-agent-mcp"]
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # List available tools
            tools = await session.list_tools()
            print("Available tools:", [t.name for t in tools.tools])

            # Execute a query
            result = await session.call_tool(
                "query",
                arguments={"question": "What are the top selling products?"}
            )
            print(result.content)

import asyncio
asyncio.run(main())
```
