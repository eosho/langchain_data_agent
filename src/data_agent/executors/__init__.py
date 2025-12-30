"""Code execution backends for sandboxed Python execution."""

import logging

from data_agent.executors.base import CodeExecutor, ExecutionResult, ExecutionStatus

logger = logging.getLogger(__name__)

__all__ = [
    "CodeExecutor",
    "ExecutionResult",
    "ExecutionStatus",
    "create_executor",
]


def create_executor() -> CodeExecutor:
    """Create a code executor based on environment configuration.

    Returns:
        Configured CodeExecutor instance.
    """
    from data_agent.config import VisualizationSettings

    settings = VisualizationSettings()

    if settings.use_azure_sessions:
        from data_agent.executors.azure_sessions import AzureSessionsExecutor

        logger.info("Using Azure Sessions executor")
        return AzureSessionsExecutor(
            pool_management_endpoint=settings.azure_sessions_pool_endpoint,
        )
    from data_agent.executors.local import LocalExecutor

    logger.info("Using local Python REPL executor (development only, no sandboxing)")
    return LocalExecutor()
