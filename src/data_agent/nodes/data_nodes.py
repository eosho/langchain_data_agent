"""Data agent nodes for LangGraph pipeline.

This module provides the DataAgentNodes class that handles query generation,
validation, and execution for all datasource types (SQL databases and Cosmos DB).
"""

import logging
from typing import TYPE_CHECKING, Any, Union

from langchain_community.utilities.sql_database import SQLDatabase
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from data_agent.config import DataAgentConfig
from data_agent.config_loader import SchemaFormatter
from data_agent.models.outputs import (
    QueryResult,
    SQLGeneratorOutput,
    SQLValidationOutput,
)
from data_agent.utils.message_utils import get_recent_history
from data_agent.utils.sql_utils import build_date_context, clean_sql_query
from data_agent.validators.sql_validator import SQLValidator, ValidationStatus

if TYPE_CHECKING:
    from langchain_community.utilities.sql_database import SQLDatabase

    from data_agent.adapters.azure.cosmos import CosmosAdapter
    from data_agent.models.state import AgentState

logger = logging.getLogger(__name__)

DEFAULT_SQL_PROMPT = """You are a SQL expert. Generate a syntactically correct SQL query.
Limit results to 10 unless specified. Only select relevant columns.

## Conversation Context
If this is a follow-up question, use the conversation history to understand what the user is referring to:
- When in doubt, infer context from the most recent SQL query in the conversation

IMPORTANT: Always generate a single, executable SQL query. Never include comments, explanations, or multiple query options.

{schema_context}

{few_shot_examples}"""

COSMOS_PROMPT_ADDENDUM = """
Key Cosmos DB constraints:
1. Queries operate on a SINGLE container - no cross-container or cross-document joins.
2. JOIN only works WITHIN documents (to traverse arrays), not across documents.
3. Always filter on partition key ({partition_key}) for performance - avoids fan-out queries.
4. DISTINCT inside aggregate functions (COUNT, SUM, AVG) is NOT supported.
5. Aggregates without partition key filter may timeout or consume high RUs.
6. SUM/AVG return undefined if any value is string, boolean, or null.
7. Max 4MB response per page; use continuation tokens for large results.
"""


class DataAgentNodes:
    """Unified query nodes for all datasource types. Handles query generation, validation, and execution.

    Args:
        llm: Language model for query generation.
        datasource: SQLDatabase or CosmosAdapter instance.
        config: Data agent configuration.
        max_retries: Maximum retry attempts.

    Example:
        ```python
        from langchain_community.utilities.sql_database import SQLDatabase

        db = SQLDatabase.from_uri("postgresql://...")
        nodes = DataAgentNodes(llm, db, config)
        result = nodes.generate_sql(state)
        ```
    """

    def __init__(
        self,
        llm: BaseChatModel,
        datasource: Union["SQLDatabase", "CosmosAdapter"],
        config: DataAgentConfig,
        max_retries: int = 3,
    ) -> None:
        """Initialize the data agent nodes.

        Args:
            llm: Language model for query generation.
            datasource: SQLDatabase or CosmosAdapter instance.
            config: Data agent configuration with schema and prompts.
            max_retries: Maximum SQL generation retry attempts.
        """
        self._llm = llm
        self._datasource = datasource
        self._config = config
        self._max_retries = max_retries
        self._sql_llm = llm.with_structured_output(SQLGeneratorOutput)

        self._is_cosmos = self._check_is_cosmos(datasource)
        self._dialect = (
            "cosmosdb"
            if self._is_cosmos
            else getattr(datasource, "dialect", "postgres")
        )

        validation_cfg = config.validation_config
        self._validator = SQLValidator(
            dialect=self._dialect,
            max_limit=validation_cfg.max_rows,
            blocked_functions=set(validation_cfg.blocked_functions) or None,
        )

    @staticmethod
    def _check_is_cosmos(datasource: Any) -> bool:
        """Check if datasource is a CosmosAdapter.

        Args:
            datasource: The datasource to check.

        Returns:
            True if datasource is a CosmosAdapter, False otherwise.
        """
        # Check by class name to avoid import issues
        return type(datasource).__name__ == "CosmosAdapter"

    def _get_schema_context(self) -> str:
        """Get schema context from config or dynamically from database.

        If table_schemas is defined in config, uses the static schema.
        Otherwise, fetches schema dynamically from the database using
        SQLDatabase.get_table_info().

        Returns:
            Schema context string for the LLM prompt.
        """
        if self._config.table_schemas:
            return SchemaFormatter.format_schema_context(self._config)

        if not self._is_cosmos and isinstance(self._datasource, SQLDatabase):
            try:
                table_info = self._datasource.get_table_info()
                if table_info:
                    logger.debug(
                        "Using dynamic schema from database. Available tables: %s",
                        table_info,
                    )
                    return f"Available tables and their schemas:\n\n{table_info}"
            except Exception as e:
                logger.warning("Failed to fetch dynamic schema: %s", e)

        return ""

    def _build_prompt(self) -> str:
        """Build system prompt, adding Cosmos constraints if needed.

        Returns:
            Formatted system prompt with schema context and date.
        """
        schema_context = self._get_schema_context()
        few_shot = SchemaFormatter.format_few_shot_examples(self._config)
        base_prompt = self._config.system_prompt or DEFAULT_SQL_PROMPT

        formatted = base_prompt.format(
            schema_context=schema_context,
            few_shot_examples=few_shot,
        )

        # Add Cosmos-specific constraints
        if self._is_cosmos:
            partition_key = "/id"
            if self._config.datasource:
                partition_key = getattr(
                    self._config.datasource, "partition_key_path", "/id"
                )
            formatted += COSMOS_PROMPT_ADDENDUM.format(partition_key=partition_key)

        return build_date_context() + formatted

    async def generate_sql(self, state: "AgentState") -> dict[str, Any]:
        """Generate query from natural language question.

        Args:
            state: Current agent state containing the question.

        Returns:
            State update with generated SQL, dialect, and messages.
        """
        question = state["question"]
        logger.debug("Generating query for: %s", question[:100])

        history = get_recent_history(state.get("messages", []), max_messages=6)

        messages = [
            SystemMessage(content=self._build_prompt()),
            *history,
            HumanMessage(content=question),
        ]

        result = await self._sql_llm.ainvoke(messages)
        sql = (
            result.sql_query if isinstance(result, SQLGeneratorOutput) else str(result)
        )
        cleaned = clean_sql_query(sql)

        logger.debug("Generated SQL: %s", cleaned)
        return {
            "generated_sql": cleaned,
            "dialect": self._dialect,
            "messages": [
                AIMessage(content=f"```sql\n{cleaned}\n```", name="sql_generator"),
            ],
        }

    def validate_sql(self, state: "AgentState") -> dict[str, Any]:
        """Validate query - uses sqlglot for SQL, basic checks for Cosmos.

        Args:
            state: Current agent state containing generated SQL.

        Returns:
            State update with validation result or error message.
        """
        sql = state.get("generated_sql", "")
        if not sql:
            logger.warning("No SQL query to validate")
            return {"error": "No query to validate"}

        return self._validate_sql_query(sql, state)

    def _validate_sql_query(self, sql: str, state: "AgentState") -> dict[str, Any]:
        """Validate SQL query using the centralized validator.

        Args:
            sql: The query to validate.
            state: Current agent state for retry count.

        Returns:
            State update with validated query, validation_result, or error message.
        """
        result = self._validator.validate(sql)
        validation_output = SQLValidationOutput(
            is_valid=result.status == ValidationStatus.VALID,
            query=result.query,
            errors=result.errors,
            warnings=result.warnings,
        )

        if result.status == ValidationStatus.VALID:
            logger.debug("SQL validation passed")
            warnings_text = f"\nWarnings: {result.warnings}" if result.warnings else ""
            return {
                "generated_sql": result.query,
                "validation_result": validation_output,
                "error": "",
                "messages": [
                    AIMessage(
                        content=f"SQL validation passed for query:\n```sql\n{result.query}\n```{warnings_text}",
                        name="sql_validator",
                    ),
                ],
            }

        retry_count = state.get("retry_count", 0)
        if retry_count >= self._max_retries:
            error_msg = (
                f"Validation failed after {retry_count} attempts: {result.errors}"
            )
            logger.error(error_msg)
            return {
                "validation_result": validation_output,
                "error": error_msg,
                "messages": [
                    AIMessage(
                        content=f"{error_msg}\n\nQuery:\n```sql\n{sql}\n```",
                        name="sql_validator",
                    ),
                ],
            }

        logger.warning(
            "Validation error (attempt %d): %s", retry_count + 1, result.errors
        )
        return {
            "validation_result": validation_output,
            "error": f"Validation error: {result.errors}",
            "messages": [
                AIMessage(
                    content=f"Validation error (attempt {retry_count + 1}): {result.errors}\n\nQuery:\n```sql\n{sql}\n```",
                    name="sql_validator",
                ),
            ],
        }

    async def execute_query(self, state: "AgentState") -> dict[str, Any]:
        """Execute query using the appropriate datasource method.

        Args:
            state: Current agent state containing validated SQL.

        Returns:
            State update with QueryResult or error message.
        """
        sql = state.get("generated_sql", "")
        if not sql:
            logger.warning("No SQL query to execute")
            return {"error": "No query to execute"}

        logger.debug("Executing: %s", sql[:200])
        try:
            if self._is_cosmos:
                cosmos_adapter: CosmosAdapter = self._datasource  # type: ignore
                result = await cosmos_adapter.execute(sql)
                logger.debug("Execution successful")
                return {
                    "result": result,
                    "messages": [
                        AIMessage(
                            content=f"Query executed successfully.\n\nResults:\n{result}",
                            name="query_executor",
                        ),
                    ],
                }
            sql_db: SQLDatabase = self._datasource  # type: ignore
            raw_result = sql_db.run(sql)
            result = QueryResult(
                columns=["result"],
                rows=[[raw_result]],
                row_count=1,
                metadata={"raw": True},
            )
            logger.debug("Execution successful")
            return {
                "result": result,
                "messages": [
                    AIMessage(
                        content=f"Query executed successfully.\n\nResults:\n{raw_result}",
                        name="query_executor",
                    ),
                ],
            }
        except Exception as e:
            logger.error("Execution failed: %s", str(e))
            return {
                "error": f"Query execution failed: {e}",
                "messages": [
                    AIMessage(
                        content=f"Query execution failed: {e}",
                        name="query_executor",
                    ),
                ],
            }

    async def retry_sql(self, state: "AgentState") -> dict[str, Any]:
        """Retry query generation with error feedback.

        Args:
            state: Current agent state with error from previous attempt.

        Returns:
            State update with new SQL and incremented retry count.
        """
        retry_count = state.get("retry_count", 0) + 1
        if retry_count > self._max_retries:
            return {"error": f"Max retries ({self._max_retries}) exceeded"}

        error = state.get("error", "")
        previous_sql = state.get("generated_sql", "")

        history = get_recent_history(state.get("messages", []), max_messages=4)

        messages = [
            SystemMessage(content=self._build_prompt()),
            *history,
            HumanMessage(content=state["question"]),
            AIMessage(content=f"```sql\n{previous_sql}\n```"),
            HumanMessage(content=f"Error: {error}\n\nPlease fix the query."),
        ]

        result = await self._sql_llm.ainvoke(messages)
        sql = (
            result.sql_query if isinstance(result, SQLGeneratorOutput) else str(result)
        )
        cleaned = clean_sql_query(sql)

        logger.debug("Retry %d generated SQL: %s", retry_count, cleaned)
        return {
            "generated_sql": cleaned,
            "error": None,
            "retry_count": retry_count,
            "messages": [
                HumanMessage(
                    content=f"Error: {error}\n\nPlease fix the query.",
                    name="sql_validator",
                ),
                AIMessage(content=f"```sql\n{cleaned}\n```", name="sql_generator"),
            ],
        }
