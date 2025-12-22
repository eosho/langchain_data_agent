"""Custom callback handlers for agent observability and logging."""

import logging
from typing import Any, Never
from uuid import UUID

from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatGeneration, LLMResult

logger = logging.getLogger(__name__)


class AgentCallback(AsyncCallbackHandler):
    """Custom async callback handler for agent operations."""

    def __init__(self, agent_name: str = "agent", context: Any | None = None) -> None:
        """Initialize the callback handler.

        Args:
            agent_name: Name of the agent for logging context. Defaults to "agent".
            context: Optional context object for persistence/tracking. Used by _persist_graph_run.
        """
        super().__init__()
        self.agent_name = agent_name
        self.context = context

    async def on_chain_start(
        self,
        serialized: dict[str, Any],
        inputs: Any,
        **kwargs: Any,
    ) -> None:
        """Run when chain starts running.

        Args:
            serialized: Serialized chain configuration
            inputs: Input data passed to the chain
            **kwargs: Additional arguments including run_id, parent_run_id, tags, metadata, name
        """
        name = kwargs.get("name")
        run_id = kwargs.get("run_id")
        parent_run_id = kwargs.get("parent_run_id")
        logger.debug(
            f"Chain started: name {name}, run_id {run_id}, parent_run_id: {parent_run_id}"
        )

    async def on_chain_end(
        self,
        outputs: Any,
        **kwargs: Any,
    ) -> None:
        """Run when chain ends running.

        Args:
            outputs: Output data from the chain
            **kwargs: Additional arguments including run_id, parent_run_id, name
        """
        name = kwargs.get("name")
        run_id = kwargs.get("run_id")
        parent_run_id = kwargs.get("parent_run_id")
        logger.debug(
            f"Chain ended: name {name}, run_id {run_id}, parent_run_id: {parent_run_id}"
        )

    async def on_chain_error(
        self,
        error: BaseException,
        **kwargs: Any,
    ) -> None:
        """Run when chain errors.

        Args:
            error: The exception that occurred
            **kwargs: Additional arguments including run_id, parent_run_id, name
        """
        name = kwargs.get("name")
        run_id = kwargs.get("run_id")
        parent_run_id = kwargs.get("parent_run_id")
        logger.debug(
            f"Chain error: run_id {run_id}, {name}, parent_run_id: {parent_run_id}"
        )

    async def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[BaseMessage]],
        **kwargs: Any,
    ) -> None:
        """Run when chat model starts running.

        Args:
            serialized: Serialized chat model configuration
            messages: List of message lists passed to the model
            **kwargs: Additional arguments including run_id, parent_run_id, tags, metadata
        """
        run_id = kwargs.get("run_id")
        parent_run_id = kwargs.get("parent_run_id")
        metadata = kwargs.get("metadata", {})
        model_name = metadata.get("ls_model_name", "unknown")

        logger.debug(
            f"Chat model started: name {model_name}, run_id {run_id}, parent_run_id: {parent_run_id}"
        )
        if messages and messages[0]:
            logger.debug(f"Chat model started with messages: {messages[0][-1].content}")

    async def on_llm_end(
        self,
        response: LLMResult,
        **kwargs: Any,
    ) -> None:
        """Run when LLM ends running.

        Args:
            response: The LLM response containing generations
            **kwargs: Additional arguments including run_id, parent_run_id, name
        """
        name = kwargs.get("name")
        run_id = kwargs.get("run_id")
        parent_run_id = kwargs.get("parent_run_id")

        logger.debug(
            f"Chat model ended: name {name}, run_id {run_id}, parent_run_id: {parent_run_id}"
        )

        generation = response.generations[0][0]
        if isinstance(generation, ChatGeneration) and generation.message is not None:
            message = generation.message.content
            tool_calls = getattr(generation.message, "tool_calls", []) or []
        else:
            message = getattr(generation, "text", None)
            tool_calls: list[Any] = []

        if message and tool_calls:
            logger.warning("AI message has both content and tool_calls")

    async def on_llm_error(
        self,
        error: BaseException,
        **kwargs: Any,
    ) -> None:
        """Run when LLM errors.

        Args:
            error: The exception that occurred
            **kwargs: Additional arguments including run_id, parent_run_id
        """
        logger.error(f"LLM error: {error}")

    async def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        **kwargs: Any,
    ) -> None:
        """Run when tool starts running.

        Args:
            serialized: Serialized tool configuration
            input_str: String representation of tool input
            **kwargs: Additional arguments including run_id, parent_run_id, tags, metadata, inputs, name
        """
        name = kwargs.get("name")
        tool_name = name or serialized.get("name", "unknown")
        logger.debug(f"Tool {tool_name} started with input: {input_str}.")

    async def on_tool_end(
        self,
        output: str,
        **kwargs: Any,
    ) -> None:
        """Run when tool ends running.

        Args:
            output: String representation of tool output
            **kwargs: Additional arguments including run_id, parent_run_id, name
        """
        name = kwargs.get("name")
        logger.debug(f"Tool {name} ended with output: {output}")

    async def on_tool_error(
        self,
        error: BaseException,
        **kwargs: Any,
    ) -> None:
        """Run when tool errors.

        Args:
            error: The exception that occurred
            **kwargs: Additional arguments including run_id, parent_run_id, name
        """
        name = kwargs.get("name")
        logger.error(f"Tool error: {name} with error: {error}")

    def _normalize_args(self, run_id=None, parent_run_id=None):
        """Normalize run_id and parent_run_id to strings if they are UUIDs.

        This utility method converts UUID objects to their string representation for logging
        or persistence. It's a no-op for values that are already strings or None.

        Args:
            run_id: Run identifier as str, UUID, or None
            parent_run_id: Parent run identifier as str, UUID, or None

        Returns:
            tuple: A tuple of (run_id, parent_run_id) as strings or None
        """
        if isinstance(run_id, UUID):
            run_id = str(run_id)
        if isinstance(parent_run_id, UUID):
            parent_run_id = str(parent_run_id)
        return run_id, parent_run_id

    async def _persist_graph_run(self) -> Never:
        """Persist the entire graph run to a database or storage system.

        This method is intended to store the complete execution trace including:
        - User input messages
        - Tool invocations and results
        - AI-generated responses
        - Execution metadata (run_ids, timestamps, etc.)

        The persistence layer should be implemented based on the specific storage backend
        (e.g., SQL database, document store, time-series database).

        Raises:
            NotImplementedError: This method must be implemented in a subclass or via context object
        """
        raise NotImplementedError("Graph run persistence not implemented yet.")
