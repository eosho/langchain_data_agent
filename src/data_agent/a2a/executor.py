"""A2A Executor for the NL2SQL Data Agent.

This module provides the AgentExecutor implementation that bridges the
A2A protocol with the DataAgentFlow for processing natural language queries.
"""

import logging

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import (
  InternalError,
  InvalidParamsError,
  Part,
  TaskState,
  TextPart,
  UnsupportedOperationError,
)
from a2a.utils import (
  new_agent_text_message,
  new_task,
)
from a2a.utils.errors import ServerError

from data_agent.agent import DataAgentFlow
from data_agent.config import AgentConfig

logger = logging.getLogger(__name__)


class DataAgentExecutor(AgentExecutor):
    """Data Agent A2A Executor for NL2SQL queries."""

    def __init__(
        self,
        config_path: str | None = None,
        config: AgentConfig | None = None,
    ):
        """Initialize the executor.

        Args:
            config_path: Path to agent configuration file.
            config: Pre-loaded AgentConfig instance.
                Takes precedence over config_path if both provided.
        """
        self.agent = DataAgentFlow(config_path=config_path, config=config)
        self._connected = False

    async def _ensure_connected(self) -> None:
        """Ensure the agent is connected to all datasources."""
        if not self._connected:
            await self.agent.connect()
            self._connected = True

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """Execute a natural language query via the A2A protocol.

        Args:
            context: Request context containing the user message and task info.
            event_queue: Queue for sending task status updates and artifacts.

        Raises:
            ServerError: If request validation fails or query execution errors.
        """
        error = self._validate_request(context)
        if error:
            raise ServerError(error=InvalidParamsError())

        await self._ensure_connected()

        query = context.get_user_input()
        task = context.current_task
        if not task:
            task = new_task(context.message)  # type: ignore
            await event_queue.enqueue_event(task)

        updater = TaskUpdater(event_queue, task.id, task.context_id)

        try:
            await updater.update_status(
                TaskState.working,
                new_agent_text_message(
                    "Processing your query...",
                    task.context_id,
                    task.id,
                ),
            )

            result = await self.agent.run(
                question=query,
                thread_id=task.context_id,
            )

            response = result.get("final_response", "Query completed.")

            await updater.add_artifact(
                [Part(root=TextPart(text=response))],
                name="query_result",
            )
            await updater.complete()

        except Exception as e:
            logger.error(f"An error occurred while executing the query: {e}")
            raise ServerError(error=InternalError()) from e

    def _validate_request(self, context: RequestContext) -> bool:
        """Validate the incoming request.

        Args:
            context: Request context to validate.

        Returns:
            True if validation fails, False if valid.
        """
        return False

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Cancel a running task.

        Args:
            context: Request context for the task to cancel.
            event_queue: Queue for sending cancellation events.

        Raises:
            ServerError: Always raises UnsupportedOperationError as cancellation
                is not currently supported.
        """
        raise ServerError(error=UnsupportedOperationError())
