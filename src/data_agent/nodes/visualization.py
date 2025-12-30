"""Data visualization node using Azure Container Apps Dynamic Sessions."""

import base64
import logging
import re
from typing import TYPE_CHECKING, Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from data_agent.executors import CodeExecutor, ExecutionStatus
from data_agent.prompts import VISUALIZATION_SYSTEM_PROMPT

if TYPE_CHECKING:
    from data_agent.models.state import AgentState

logger = logging.getLogger(__name__)


class VisualizationNode:
    """Node for generating data visualizations using sandboxed code execution."""

    def __init__(self, llm: BaseChatModel, executor: CodeExecutor) -> None:
        """Initialize the visualization node.

        Args:
            llm: Language model for code generation.
            executor: Code executor backend for running generated code.
        """
        self._llm = llm
        self._executor = executor

    async def generate_visualization(self, state: "AgentState") -> dict[str, Any]:
        """Generate a visualization from query results using LLM + PythonREPL.

        Args:
            state: Current agent state with query results and visualization_requested flag.

        Returns:
            State update with visualization_image (base64 PNG) or visualization_error.
        """
        result = state.get("result")
        if not result:
            logger.warning("Visualization requested but no query result available")
            return {"visualization_error": "No data to visualize"}

        if isinstance(result, dict):
            rows = result.get("rows", [])
            columns = result.get("columns", [])
        else:
            rows = getattr(result, "rows", [])
            columns = getattr(result, "columns", [])

        if not rows or not columns:
            logger.warning("Visualization requested but result has no data")
            return {"visualization_error": "No data to visualize"}

        data = [dict(zip(columns, row)) for row in rows]

        messages = [
            SystemMessage(content=VISUALIZATION_SYSTEM_PROMPT),
            HumanMessage(
                content=f"""User question: {state["question"]}

Data columns: {columns}
Data ({len(data)} rows):
data = {data}

Generate Python code to create an appropriate visualization for this data and question.
"""
            ),
        ]

        try:
            response = await self._llm.ainvoke(messages)

            content = response.content
            if isinstance(content, list):
                content = "".join(
                    part if isinstance(part, str) else part.get("text", "")
                    for part in content
                )
            code = self._extract_code(content)
            if not code:
                logger.error("Failed to extract code from LLM response")
                return {"visualization_error": "Failed to generate visualization code"}

            logger.debug("Generated visualization code:\n%s", code[:500])

            # Execute code in sandbox
            exec_result = await self._executor.execute(code)

            if exec_result.status == ExecutionStatus.SUCCESS:
                # Check for image in files (native capture from Azure Sessions)
                if exec_result.files and "visualization.png" in exec_result.files:
                    img_base64 = base64.b64encode(
                        exec_result.files["visualization.png"]
                    ).decode()
                    logger.debug("Successfully generated visualization")
                    return {
                        "visualization_image": img_base64,
                        "visualization_code": code,
                        "messages": [
                            AIMessage(
                                content="Generated visualization",
                                name="visualizer",
                            )
                        ],
                    }
                output_preview = exec_result.output[:500] if exec_result.output else ""
                logger.error("Code executed but no image output: %s", output_preview)
                return {
                    "visualization_error": f"Code executed but no image: {exec_result.output[:200]}"
                }
            logger.error("Code execution failed: %s", exec_result.error)
            return {"visualization_error": exec_result.error}

        except Exception as e:
            logger.exception("Visualization code execution failed")
            return {"visualization_error": str(e)}

    def _extract_code(self, content: str) -> str | None:
        """Extract Python code from LLM response.

        Tries to find code in:
        1. ```python ... ``` blocks
        2. ``` ... ``` blocks
        3. Raw content if it looks like Python code

        Args:
            content: LLM response content.

        Returns:
            Extracted Python code or None if not found.
        """
        code_match = re.search(r"```python\n(.*?)```", content, re.DOTALL)
        if code_match:
            return code_match.group(1)

        code_match = re.search(r"```\n(.*?)```", content, re.DOTALL)
        if code_match:
            return code_match.group(1)

        if "import" in content and ("plt" in content or "matplotlib" in content):
            return content

        return None
