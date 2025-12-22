"""A2A server for the NL2SQL Data Agent.

This module provides the A2A-compliant HTTP server using the a2a-sdk
Starlette integration.
"""

import argparse
import logging
import os

import uvicorn
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore

from data_agent.a2a.agent_card import build_agent_card
from data_agent.a2a.executor import DataAgentExecutor
from data_agent.config import CONFIG_DIR
from data_agent.config_loader import ConfigLoader

logger = logging.getLogger(__name__)


def create_a2a_app(
    config_path: str | None = None,
    config_name: str | None = None,
    host: str = "localhost",
    port: int = 8001,
) -> A2AStarletteApplication:
    """Create the A2A Starlette application.

    Args:
        config_path: Path to agent configuration file.
        config_name: Name of config to load from config directory.
            If neither config_path nor config_name is provided, loads all configs.
        host: Server host for agent card URL.
        port: Server port for agent card URL.

    Returns:
        Configured A2AStarletteApplication instance.
    """
    # Load configuration
    if config_path:
        config = ConfigLoader.load(config_path)
    elif config_name:
        config = ConfigLoader.load_by_name(config_name)
    else:
        config = ConfigLoader.load_all()

    datasources = [agent.name for agent in config.data_agents]

    agent_card = build_agent_card(
        host=host,
        port=port,
        datasources=datasources,
    )
    executor = DataAgentExecutor(config=config)
    task_store = InMemoryTaskStore()
    handler = DefaultRequestHandler(
        agent_executor=executor,
        task_store=task_store,
    )
    app = A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=handler,
    )

    return app


def get_config_choices() -> list[str]:
    """Get available configuration file names.

    Returns:
        List of config names (without .yaml extension).
    """
    return [f.stem for f in CONFIG_DIR.glob("*.yaml")]


def run_server(
    config_name: str | None = None,
    host: str = "localhost",
    port: int = 8001,
    reload: bool = False,
    log_level: str = "info",
) -> None:
    """Run the A2A server.

    Args:
        config_name: Name of config to load (e.g., 'contoso').
            If None, loads all configs.
        host: Server bind host.
        port: Server bind port.
        reload: Enable auto-reload for development.
        log_level: Logging level.
    """
    a2a_app = create_a2a_app(
        config_name=config_name,
        host=host,
        port=port,
    )

    starlette_app = a2a_app.build()

    config_display = config_name or "all"
    logger.info(f"Starting A2A server at http://{host}:{port}")
    logger.info(
        f"Agent Card available at http://{host}:{port}/.well-known/agent-card.json"
    )
    logger.info(f"Config: {config_display}")

    uvicorn.run(
        starlette_app,
        host=host,
        port=port,
        log_level=log_level,
        reload=reload,
    )


def main() -> None:
    """Main entry point for the A2A server CLI."""
    parser = argparse.ArgumentParser(
        description="NL2SQL Data Agent - A2A Protocol Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start server with all configs (default)
  data-agent-a2a

  # Start with a specific config
  data-agent-a2a --config contoso

  # Start on a specific port with debug logging
  data-agent-a2a --port 9000 --log-level debug
        """,
    )

    available_configs = get_config_choices()
    parser.add_argument(
        "--config",
        "-c",
        type=str,
        default=None,
        choices=available_configs,
        help=f"Config name to load. Available: {', '.join(available_configs)}. "
        "If not specified, loads all configs.",
    )

    parser.add_argument(
        "--host",
        type=str,
        default="localhost",
        help="Server bind host (default: localhost)",
    )

    parser.add_argument(
        "--port",
        "-p",
        type=int,
        default=8001,
        help="Server bind port (default: 8001)",
    )

    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development",
    )

    parser.add_argument(
        "--log-level",
        type=str,
        default="info",
        choices=["debug", "info", "warning", "error", "critical"],
        help="Logging level (default: info)",
    )

    args = parser.parse_args()

    config_name = args.config or os.environ.get("DATA_AGENT_CONFIG")

    run_server(
        config_name=config_name,
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level,
    )


if __name__ == "__main__":
    main()
