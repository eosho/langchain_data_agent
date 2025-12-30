"""Azure Container Apps Dynamic Sessions executor.

This module provides secure code execution using Azure Container Apps
dynamic sessions with Hyper-V isolation.

Requires:
    pip install langchain-azure-dynamic-sessions

Environment:
    AZURE_SESSIONS_POOL_ENDPOINT: Session pool management endpoint URL
"""

import logging
import os
from base64 import b64decode
from typing import Any

from langchain_azure_dynamic_sessions import SessionsPythonREPLTool

from data_agent.executors.base import CodeExecutor, ExecutionResult, ExecutionStatus

logger = logging.getLogger(__name__)


class AzureSessionsExecutor(CodeExecutor):
    """Execute code in Azure Container Apps dynamic sessions with Hyper-V isolation."""

    def __init__(
        self,
        pool_management_endpoint: str | None = None,
        session_id: str | None = None,
    ) -> None:
        """Initialize Azure Sessions executor.

        Args:
            pool_management_endpoint: Session pool management endpoint URL.
                Falls back to AZURE_SESSIONS_POOL_ENDPOINT environment variable.
            session_id: Optional session ID for session reuse. If not provided,
                the tool will manage session IDs automatically.

        Raises:
            ValueError: If pool_management_endpoint is not provided and
                AZURE_SESSIONS_POOL_ENDPOINT is not set.
        """
        self._endpoint = pool_management_endpoint or os.getenv(
            "AZURE_SESSIONS_POOL_ENDPOINT"
        )
        if not self._endpoint:
            raise ValueError(
                "pool_management_endpoint is required. "
                "Set via config or AZURE_SESSIONS_POOL_ENDPOINT environment variable."
            )

        self._session_id = session_id
        self._tool: SessionsPythonREPLTool | None = None

    def _get_tool(self) -> SessionsPythonREPLTool:
        """Get or create the SessionsPythonREPLTool instance.

        The tool uses DefaultAzureCredential internally for authentication.
        """
        if self._tool is None:
            # Per Microsoft docs, just pass the endpoint - the tool handles auth
            # internally using DefaultAzureCredential
            assert self._endpoint is not None  # Validated in __init__
            self._tool = SessionsPythonREPLTool(
                pool_management_endpoint=self._endpoint,
            )
            endpoint_preview = (
                self._endpoint[:50] + "..."
                if len(self._endpoint) > 50
                else self._endpoint
            )
            logger.debug(
                "Created Azure Sessions tool with endpoint: %s",
                endpoint_preview,
            )
        return self._tool

    async def execute(self, code: str, timeout: float = 30.0) -> ExecutionResult:
        """Execute Python code in an Azure dynamic session.

        Args:
            code: Python code to execute.
            timeout: Maximum execution time (note: Azure has its own limits).

        Returns:
            ExecutionResult with output and any generated files.
        """
        try:
            tool = self._get_tool()

            # Use execute() to get raw response with artifact support
            response = tool.execute(code)

            stdout = response.get("stdout", "")
            stderr = response.get("stderr", "")
            result = response.get("result")

            output = stdout
            if stderr:
                output += f"\nSTDERR: {stderr}"

            logger.debug("Azure session response: %s", _preview(response))

            # Check if result contains an image (native matplotlib capture)
            files = None
            if isinstance(result, dict) and result.get("type") == "image":
                base64_data = result.get("base64_data")
                if base64_data:
                    files = {"visualization.png": b64decode(base64_data)}
                    logger.debug("Captured visualization image from session")

            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                output=output,
                files=files,
                metadata={"session_id": self._session_id, "result": result},
            )

        except Exception as e:
            logger.exception("Azure session execution failed")
            return ExecutionResult(
                status=ExecutionStatus.ERROR,
                error=str(e),
                metadata={"session_id": self._session_id},
            )

    async def cleanup(self) -> None:
        """Clean up the Azure session.

        Note: Azure automatically cleans up idle sessions after timeout.
        """
        self._tool = None
        logger.debug("Azure sessions executor cleaned up")


def _preview(obj: Any, max_len: int = 200) -> str:
    """Create a preview string of an object for logging."""
    s = str(obj)
    return s[:max_len] + "..." if len(s) > max_len else s
