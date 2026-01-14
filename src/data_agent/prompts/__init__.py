"""Default prompts for the data agent."""

from data_agent.prompts.defaults import (
  COSMOS_PROMPT_ADDENDUM,
  DEFAULT_GENERAL_CHAT_PROMPT,
  DEFAULT_INTENT_DETECTION_PROMPT,
  DEFAULT_RESPONSE_PROMPT,
  DEFAULT_SQL_PROMPT,
  VISUALIZATION_SYSTEM_PROMPT,
)
from data_agent.prompts.dialects import get_dialect_guidelines

__all__ = [
    "COSMOS_PROMPT_ADDENDUM",
    "DEFAULT_GENERAL_CHAT_PROMPT",
    "DEFAULT_INTENT_DETECTION_PROMPT",
    "DEFAULT_RESPONSE_PROMPT",
    "DEFAULT_SQL_PROMPT",
    "VISUALIZATION_SYSTEM_PROMPT",
    "get_dialect_guidelines",
]
