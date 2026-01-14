"""Prompt builder for assembling system prompts from components.

This module provides the `build_prompt` function that assembles
the final system prompt by appending all components in order.
"""

import logging

from data_agent.prompts.defaults import (
    COSMOS_PROMPT_ADDENDUM,
    DEFAULT_RESPONSE_PROMPT,
    DEFAULT_SQL_PROMPT,
)
from data_agent.prompts.dialects import get_dialect_guidelines
from data_agent.utils.sql_utils import build_date_context

logger = logging.getLogger(__name__)


def build_prompt(
    datasource_type: str,
    user_prompt: str | None = None,
    schema_context: str = "",
    few_shot_examples: str | None = None,
    partition_key: str | None = None,
) -> str:
    """Build the complete prompt by appending all components.

    Args:
        datasource_type: Database type (e.g., 'bigquery', 'azure_sql', 'postgres', 'cosmosdb').
        user_prompt: Team's custom prompt from YAML (optional).
        schema_context: Schema information (auto-discovered or from YAML).
        few_shot_examples: Formatted examples string (optional).
        partition_key: Cosmos DB partition key path (only for Cosmos datasources).

    Returns:
        Complete prompt with all components assembled.
    """
    sections: list[str] = []

    sections.append(build_date_context().strip())

    base_prompt = user_prompt.strip() if user_prompt else DEFAULT_SQL_PROMPT.strip()

    formatted_prompt = base_prompt.format(
        schema_context=schema_context or "",
        few_shot_examples=few_shot_examples or "",
    )
    sections.append(formatted_prompt)

    dialect_guidelines = get_dialect_guidelines(datasource_type)
    if dialect_guidelines:
        sections.append(dialect_guidelines.strip())

    if datasource_type.lower() in ("cosmos", "cosmosdb"):
        cosmos_addendum = COSMOS_PROMPT_ADDENDUM.format(
            partition_key=partition_key or "/id"
        )
        sections.append(cosmos_addendum.strip())

    prompt = "\n\n".join(sections)

    logger.debug(
        "Built system prompt for %s (%d chars):\n%s",
        datasource_type,
        len(prompt),
        prompt,
    )

    return prompt


def build_response_prompt(user_prompt: str | None = None) -> str:
    """Build the response generation prompt.

    Args:
        user_prompt: Team's custom response prompt from YAML (optional).

    Returns:
        Response prompt (custom or default).
    """
    if user_prompt:
        return user_prompt.strip()
    return DEFAULT_RESPONSE_PROMPT.strip()
