"""A2A Agent Card builder for the NL2SQL Data Agent.

This module creates the Agent Card that describes the agent's capabilities
and is served at /.well-known/agent-card.json.
"""

from a2a.types import (
  AgentCapabilities,
  AgentCard,
  AgentSkill,
)

SUPPORTED_CONTENT_TYPES = ["text", "text/plain"]


def build_agent_card(
    host: str = "localhost",
    port: int = 8001,
    datasources: list[str] | None = None,
    name: str = "NL2SQL Data Agent",
    description: str | None = None,
    version: str = "1.0.0",
) -> AgentCard:
    """Build an A2A Agent Card for the NL2SQL Data Agent.

    Args:
        host: The host where the agent is running.
        port: The port where the agent is running.
        datasources: List of configured datasource names to advertise as skills.
        name: Agent display name.
        description: Agent description. Defaults to a standard description.
        version: Agent version string.

    Returns:
        AgentCard describing the agent's capabilities.
    """
    base_url = f"http://{host}:{port}"
    datasources = datasources or []

    default_description = (
        "An intelligent agent that converts natural language questions into SQL queries "
        "and executes them against configured databases. Supports multiple database types "
        "including Azure SQL, Azure Cosmos DB, Azure Synapse, PostgreSQL, BigQuery, and Databricks."
    )

    skills = _build_skills(datasources)

    return AgentCard(
        name=name,
        description=description or default_description,
        version=version,
        url=base_url,
        capabilities=AgentCapabilities(
            streaming=True,
            push_notifications=False,
            state_transition_history=True,
        ),
        default_input_modes=SUPPORTED_CONTENT_TYPES,
        default_output_modes=SUPPORTED_CONTENT_TYPES,
        skills=skills,
    )


def _build_skills(datasources: list[str]) -> list[AgentSkill]:
    """Build agent skills from configured datasources.

    Args:
        datasources: List of datasource names from configuration.

    Returns:
        List of AgentSkill objects for each datasource.
    """
    skills: list[AgentSkill] = []

    for ds_name in datasources:
        normalized = ds_name.lower().replace("-", "_").replace(" ", "_")
        skills.append(
            AgentSkill(
                id=f"query_{normalized}",
                name=f"Query {ds_name}",
                description=f"Query the {ds_name} datasource using natural language",
                tags=["sql", "query", ds_name],
                examples=[
                    f"Query {ds_name}: Show me the data",
                ],
            )
        )

    return skills
