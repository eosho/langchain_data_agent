"""MCP server context management with thread-safe state."""

import logging
from contextvars import ContextVar

from data_agent.agent import DataAgentFlow
from data_agent.config import AgentConfig

logger = logging.getLogger(__name__)


class MCPServerContext:
    """Context holding initialized server components.

    Manages the lifecycle of the Data Agent and its connections,
    providing thread-safe access to shared resources.
    """

    def __init__(self, config: AgentConfig):
        """Initialize the MCP server context.

        Args:
            config: Agent configuration with datasource definitions.
        """
        self.config = config
        self.agent = DataAgentFlow(config=config)
        self._connected = False

    async def ensure_connected(self) -> None:
        """Connect to all datasources if not already connected."""
        if not self._connected:
            logger.info("Connecting to datasources...")
            await self.agent.connect()
            self._connected = True
            logger.info("Connected to datasources")

    async def disconnect(self) -> None:
        """Cleanup connections."""
        self._connected = False
        logger.info("Disconnected from datasources")

    @property
    def is_connected(self) -> bool:
        """Check if datasources are connected."""
        return self._connected


# Thread-safe context variable for the server context
_context_var: ContextVar[MCPServerContext | None] = ContextVar(
    "mcp_server_context", default=None
)


def set_context(ctx: MCPServerContext) -> None:
    """Set the MCP server context.

    Args:
        ctx: The MCPServerContext instance to set.
    """
    _context_var.set(ctx)
