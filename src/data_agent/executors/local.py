"""Local Python executor for development.

Warning:
    The local executor runs code directly on the host machine without sandboxing.
    Only use in development environments with trusted code generation.
"""

import io
import logging
from contextlib import redirect_stdout

from data_agent.executors.base import CodeExecutor, ExecutionResult, ExecutionStatus

logger = logging.getLogger(__name__)


class LocalExecutor(CodeExecutor):
    """Local Python executor for development.

    Executes Python code using exec(). Captures matplotlib output
    by hooking plt.show() to save figures to a buffer.
    """

    def __init__(self) -> None:
        """Initialize the local executor."""
        logger.warning(
            "LocalExecutor runs code without sandboxing. Use only in development."
        )

    async def execute(self, code: str, timeout: float = 30.0) -> ExecutionResult:
        """Execute Python code locally.

        Args:
            code: Python code to execute.
            timeout: Execution timeout in seconds (not enforced locally).

        Returns:
            ExecutionResult with output, status, and any captured image.
        """
        # Set up execution environment
        exec_globals: dict = {}
        output_buffer = io.StringIO()
        image_buffer = io.BytesIO()
        image_captured = False

        # Set up matplotlib with Agg backend and custom show
        setup_code = """
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
"""
        try:
            exec(setup_code, exec_globals)
        except Exception as e:
            return ExecutionResult(
                status=ExecutionStatus.ERROR,
                output="",
                error=f"Failed to set up matplotlib: {e}",
            )

        # Create custom show function that captures the figure
        def capture_show(*args, **kwargs):
            nonlocal image_captured
            plt = exec_globals.get("plt")
            if plt:
                image_buffer.seek(0)
                image_buffer.truncate()
                plt.savefig(image_buffer, format="png", dpi=150, bbox_inches="tight")
                image_buffer.seek(0)
                image_captured = True
                plt.close("all")

        # Replace plt.show with our capture function
        exec_globals["plt"].show = capture_show

        try:
            with redirect_stdout(output_buffer):
                exec(code, exec_globals)

            output = output_buffer.getvalue()

            if image_captured:
                return ExecutionResult(
                    status=ExecutionStatus.SUCCESS,
                    output=output,
                    files={"visualization.png": image_buffer.getvalue()},
                )

            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                output=output,
            )

        except Exception as e:
            logger.exception("Local execution failed")
            return ExecutionResult(
                status=ExecutionStatus.ERROR,
                output=output_buffer.getvalue(),
                error=str(e),
            )
