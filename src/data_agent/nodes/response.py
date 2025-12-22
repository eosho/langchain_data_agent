"""Response generation node for LangGraph pipeline.

This module provides the ResponseNode class that generates natural language
responses from query results.
"""

import logging
from typing import TYPE_CHECKING, Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from data_agent.config import DataAgentConfig
from data_agent.models.outputs import ResponseGeneratorOutput
from data_agent.utils.message_utils import get_recent_history

if TYPE_CHECKING:
    from data_agent.models.state import AgentState

logger = logging.getLogger(__name__)

DEFAULT_RESPONSE_PROMPT = """You are a helpful data analyst. Given the user's question,
the SQL query that was executed, and the results, provide a clear and concise natural
language response that answers the user's question.

Be conversational but precise. Include relevant numbers and insights from the data."""


class ResponseNode:
    """Response generation node.

    Generates natural language responses from query results using an LLM.

    Args:
        llm: Language model for response generation.
        config: Data agent configuration with optional response prompt.

    Example:
        ```python
        response_node = ResponseNode(llm, config)
        result = response_node.generate_response(state)
        ```
    """

    def __init__(self, llm: BaseChatModel, config: DataAgentConfig) -> None:
        """Initialize the response node.

        Args:
            llm: Language model for response generation.
            config: Data agent configuration with response prompt.
        """
        self._llm = llm
        self._config = config
        self._response_llm = llm.with_structured_output(ResponseGeneratorOutput)

    def generate_response(self, state: "AgentState") -> dict[str, Any]:
        """Generate natural language response from query results.

        Args:
            state: Current agent state containing question, SQL, and results.

        Returns:
            State update with final response and messages.
        """
        prompt = self._config.response_prompt or DEFAULT_RESPONSE_PROMPT

        question = state["question"]
        sql = state.get("generated_sql", "")
        result = state.get("result", {})

        # Get recent conversation history for conversational continuity
        history = get_recent_history(state.get("messages", []), max_messages=4)

        messages = [
            SystemMessage(content=prompt),
            *history,  # Previous turns for conversational context
            HumanMessage(
                content=(
                    f"Question: {question}\n\nSQL Query: {sql}\n\nResults: {result}"
                )
            ),
        ]

        logger.debug("Generating response for question: %s", question[:100])
        response_result = self._response_llm.invoke(messages)
        response = (
            response_result.response
            if isinstance(response_result, ResponseGeneratorOutput)
            else str(response_result)
        )

        logger.debug("Generated response: %s", response[:200])
        return {
            "final_response": response,
            "messages": [AIMessage(content=response, name="response_generator")],
        }
