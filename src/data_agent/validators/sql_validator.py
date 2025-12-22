"""SQL validation and safety checking using sqlglot.

This module provides SQL parsing, validation, and policy enforcement
to ensure only safe read-only queries are executed.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import ClassVar

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError


class ValidationStatus(Enum):
    """Status of SQL validation."""

    VALID = "valid"
    INVALID = "invalid"
    UNSAFE = "unsafe"


@dataclass
class ValidationResult:
    """Result of SQL validation.

    Attributes:
        status: Validation status (valid, invalid, or unsafe).
        query: The original or transformed SQL query.
        errors: List of validation error messages.
        warnings: List of non-blocking warnings.
        dialect: SQL dialect used for validation.
    """

    status: ValidationStatus
    query: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    dialect: str = "postgres"


class SQLValidator:
    """SQL validator with configurable safety policies.

    Validates SQL queries for syntax correctness and policy compliance.
    Only allows read-only SELECT queries by default.

    Attributes:
        dialect: SQL dialect for parsing (e.g., 'postgres', 'databricks').
        max_limit: Maximum rows allowed in queries (enforced via LIMIT).
        blocked_functions: Set of SQL functions that are not allowed.

    Example:
        ```python
        validator = SQLValidator(dialect="postgres", max_limit=1000)
        result = validator.validate("SELECT * FROM users")

        if result.status == ValidationStatus.VALID:
            print(f"Safe query: {result.query}")
        else:
            print(f"Validation failed: {result.errors}")
        ```
    """

    WRITE_STATEMENTS: ClassVar[set[type]] = {
        exp.Insert,
        exp.Update,
        exp.Delete,
        exp.Drop,
        exp.Create,
        exp.Alter,
        exp.Merge,
        exp.TruncateTable,
        exp.Copy,
        exp.LoadData,
        exp.Grant,
        exp.Revoke,
    }

    DANGEROUS_FUNCTIONS: ClassVar[set[str]] = {
        "pg_sleep",
        "pg_read_file",
        "pg_read_binary_file",
        "pg_ls_dir",
        "pg_stat_file",
        "lo_import",
        "lo_export",
        "sleep",
        "benchmark",
        "load_file",
        "into_outfile",
        "into_dumpfile",
        "xp_cmdshell",
        "xp_fileexist",
        "xp_dirtree",
        "xp_regread",
        "xp_regwrite",
        "sp_oacreate",
        "sp_oamethod",
        "openrowset",
        "opendatasource",
        "bulk",
        "waitfor",
        "session_user",
        "reflect",
        "java_method",
        "exec",
        "execute",
        "system",
        "shell",
    }

    # Dialects that use basic validation instead of sqlglot
    BASIC_VALIDATION_DIALECTS: ClassVar[set[str]] = {
        "cosmosdb",  # Cosmos DB SQL has unique syntax not supported by sqlglot
    }

    # Disallowed keywords for basic validation (write operations)
    DISALLOWED_KEYWORDS: ClassVar[set[str]] = {
        "INSERT",
        "UPDATE",
        "DELETE",
        "DROP",
        "CREATE",
        "ALTER",
        "TRUNCATE",
        "MERGE",
        "GRANT",
        "REVOKE",
    }

    DIALECT_MAP: ClassVar[dict[str, str]] = {
        "mssql": "tsql",
        "azure_sql": "tsql",
        "synapse": "tsql",
        "postgresql": "postgres",
    }

    def __init__(
        self,
        dialect: str = "postgres",
        max_limit: int = 10000,
        blocked_functions: set[str] | None = None,
    ) -> None:
        """Initialize the SQL validator.

        Args:
            dialect: SQL dialect for parsing and validation.
            max_limit: Maximum number of rows allowed (LIMIT clause).
            blocked_functions: Additional functions to block.
        """
        self.dialect = self.DIALECT_MAP.get(dialect, dialect)
        self.max_limit = max_limit
        self.blocked_functions = self.DANGEROUS_FUNCTIONS.copy()
        if blocked_functions:
            self.blocked_functions.update(blocked_functions)

    def validate(self, query: str) -> ValidationResult:
        """Validate a SQL query for syntax and safety.

        Args:
            query: The SQL query to validate.

        Returns:
            ValidationResult with status, transformed query, and any errors.
        """
        # Use basic validation for dialects not supported by sqlglot
        if self.dialect in self.BASIC_VALIDATION_DIALECTS:
            return self._validate_basic(query)

        errors: list[str] = []
        warnings: list[str] = []

        try:
            parsed = sqlglot.parse_one(query, dialect=self.dialect)
        except ParseError as e:
            return ValidationResult(
                status=ValidationStatus.INVALID,
                query=query,
                errors=[f"SQL syntax error: {e}"],
                dialect=self.dialect,
            )

        if not self._is_select_statement(parsed):
            return ValidationResult(
                status=ValidationStatus.UNSAFE,
                query=query,
                errors=["Only SELECT statements are allowed"],
                dialect=self.dialect,
            )

        unsafe_funcs = self._find_dangerous_functions(parsed)
        if unsafe_funcs:
            return ValidationResult(
                status=ValidationStatus.UNSAFE,
                query=query,
                errors=[f"Blocked function(s) detected: {', '.join(unsafe_funcs)}"],
                dialect=self.dialect,
            )

        transformed = self._enforce_limit(parsed)
        if transformed != parsed:
            warnings.append(f"LIMIT clause added/modified to max {self.max_limit}")

        final_query = transformed.sql(dialect=self.dialect)

        return ValidationResult(
            status=ValidationStatus.VALID,
            query=final_query,
            errors=errors,
            warnings=warnings,
            dialect=self.dialect,
        )

    def _is_select_statement(self, parsed: exp.Expression) -> bool:
        """Check if the parsed expression is a SELECT statement.

        Args:
            parsed: Parsed SQL expression.

        Returns:
            True if it's a SELECT statement, False otherwise.
        """
        if isinstance(parsed, exp.Select):
            return True

        for stmt_type in self.WRITE_STATEMENTS:
            if isinstance(parsed, stmt_type):
                return False

        if isinstance(parsed, (exp.Union, exp.Intersect, exp.Except)):
            return True

        return isinstance(parsed, exp.Subquery)

    def _find_dangerous_functions(self, parsed: exp.Expression) -> list[str]:
        """Find any dangerous function calls in the query.

        Args:
            parsed: Parsed SQL expression.

        Returns:
            List of dangerous function names found.
        """
        dangerous = []
        for func in parsed.find_all(exp.Func):
            func_name = func.sql_name().lower()
            if func_name in self.blocked_functions:
                dangerous.append(func_name)
        return dangerous

    def _enforce_limit(self, parsed: exp.Expression) -> exp.Expression:
        """Enforce LIMIT clause on the query.

        Adds or modifies LIMIT to ensure it doesn't exceed max_limit.

        Args:
            parsed: Parsed SQL expression.

        Returns:
            Modified expression with enforced LIMIT.
        """
        if not isinstance(parsed, exp.Select):
            return parsed

        existing_limit = parsed.find(exp.Limit)
        if existing_limit:
            try:
                limit_val = int(existing_limit.expression.this)
                if limit_val > self.max_limit:
                    existing_limit.set("expression", exp.Literal.number(self.max_limit))
            except (ValueError, AttributeError):
                pass
        else:
            parsed = parsed.limit(self.max_limit)

        return parsed

    def _validate_basic(self, query: str) -> ValidationResult:
        """Perform basic keyword-based validation for unsupported dialects.

        Used for dialects like Cosmos DB that sqlglot doesn't support.
        Checks that query starts with SELECT and contains no write operations.

        Args:
            query: The SQL query to validate.

        Returns:
            ValidationResult with status and any errors.
        """
        query_upper = query.strip().upper()

        # Must start with SELECT
        if not query_upper.startswith("SELECT"):
            return ValidationResult(
                status=ValidationStatus.UNSAFE,
                query=query,
                errors=["Queries must start with SELECT"],
                dialect=self.dialect,
            )

        # Check for disallowed write operations
        for keyword in self.DISALLOWED_KEYWORDS:
            # Use word boundary check to avoid false positives
            # e.g., "UPDATED_AT" shouldn't match "UPDATE"
            if f" {keyword} " in f" {query_upper} ":
                return ValidationResult(
                    status=ValidationStatus.UNSAFE,
                    query=query,
                    errors=[f"{keyword} operations are not allowed"],
                    dialect=self.dialect,
                )

        return ValidationResult(
            status=ValidationStatus.VALID,
            query=query,
            errors=[],
            warnings=[f"Basic validation used for {self.dialect} dialect"],
            dialect=self.dialect,
        )

    def transpile(self, query: str, target_dialect: str) -> str:
        """Transpile SQL from one dialect to another.

        Args:
            query: The SQL query to transpile.
            target_dialect: Target SQL dialect.

        Returns:
            Transpiled SQL query.

        Raises:
            ValueError: If query cannot be parsed or transpiled.
        """
        try:
            return sqlglot.transpile(
                query,
                read=self.dialect,
                write=target_dialect,
            )[0]
        except Exception as e:
            raise ValueError(f"Failed to transpile query: {e}") from e
