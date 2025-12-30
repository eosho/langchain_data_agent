"""Base interface for sandboxed code execution.

This module defines the abstract interface for code execution backends,
providing a consistent API for different isolation strategies.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ExecutionStatus(Enum):
    """Status of code execution."""

    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"


@dataclass
class ExecutionResult:
    """Result of code execution in a sandbox.

    Attributes:
        status: Execution status (success, error, timeout).
        output: Standard output from code execution.
        error: Error message if execution failed.
        files: Dictionary of generated files {filename: content_bytes}.
        metadata: Additional execution metadata (timing, resource usage).
    """

    status: ExecutionStatus
    output: str = ""
    error: str | None = None
    files: dict[str, bytes] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        """Check if execution was successful."""
        return self.status == ExecutionStatus.SUCCESS


class CodeExecutor(ABC):
    """Abstract base class for code execution backends.

    Implementations:
        - AzureSessionsExecutor: Production (Hyper-V isolation via Azure Container Apps)
        - LocalExecutor: Development (no sandboxing, uses exec())
    """

    @abstractmethod
    async def execute(self, code: str, timeout: float = 30.0) -> ExecutionResult:
        """Execute Python code in an isolated environment.

        Args:
            code: Python code to execute.
            timeout: Maximum execution time in seconds.

        Returns:
            ExecutionResult with output, errors, and any generated files.
        """

    async def cleanup(self) -> None:
        """Clean up any resources (sessions, containers).

        Override in implementations that maintain state.
        """

    async def __aenter__(self) -> "CodeExecutor":
        """Async context manager entry."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Async context manager exit - cleanup resources."""
        await self.cleanup()
