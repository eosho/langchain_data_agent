"""Pydantic models for structured LLM outputs.

This module defines Pydantic models used to parse and validate
structured responses from the LLM during SQL generation.
"""

from pydantic import BaseModel, Field


class SQLGeneratorOutput(BaseModel):
    """Structured output for SQL generation.

    Attributes:
        thinking: Step-by-step reasoning about how to answer the question.
        sql_query: The generated SQL query.
        explanation: Brief explanation of what the query does.
    """

    thinking: str = Field(
        description="Step-by-step reasoning about how to construct the SQL query"
    )
    sql_query: str = Field(description="The SQL query that answers the user's question")
    explanation: str = Field(description="Brief explanation of what the query does")


class SQLValidationOutput(BaseModel):
    """Structured output for SQL validation results.

    Attributes:
        is_valid: Whether the SQL query passed validation.
        query: The validated (possibly transformed) SQL query.
        errors: List of validation error messages.
        warnings: List of non-blocking warnings.
    """

    is_valid: bool = Field(description="Whether the SQL query passed validation")
    query: str = Field(default="", description="The validated SQL query")
    errors: list[str] = Field(default_factory=list, description="Validation errors")
    warnings: list[str] = Field(default_factory=list, description="Validation warnings")


class ResponseGeneratorOutput(BaseModel):
    """Structured output for natural language response generation.

    Attributes:
        response: Human-readable response summarizing the query results.
        confidence: Confidence level in the response (0-1).
    """

    response: str = Field(
        description="Human-readable response summarizing the query results"
    )
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Confidence level in the response"
    )


class QueryResult(BaseModel):
    """Structured result from database query execution.

    Attributes:
        columns: List of column names in the result.
        rows: List of rows, each row is a list of values.
        row_count: Number of rows returned.
        metadata: Optional metadata about the query execution.
    """

    columns: list[str] = Field(default_factory=list, description="Column names")
    rows: list[list] = Field(default_factory=list, description="Result rows")
    row_count: int = Field(default=0, description="Number of rows returned")
    metadata: dict = Field(default_factory=dict, description="Execution metadata")
