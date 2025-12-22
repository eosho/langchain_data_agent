"""A2A (Agent-to-Agent) Protocol implementation for the NL2SQL Data Agent.

This module provides an A2A-compliant server that exposes the DataAgentFlow
via the Google A2A protocol, enabling interoperability with other A2A agents.
"""

from data_agent.a2a.agent_card import build_agent_card
from data_agent.a2a.executor import DataAgentExecutor
from data_agent.a2a.server import create_a2a_app, run_server

__all__ = [
    "DataAgentExecutor",
    "build_agent_card",
    "create_a2a_app",
    "run_server",
]
