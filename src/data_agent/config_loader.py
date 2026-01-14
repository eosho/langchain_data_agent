"""Configuration loading and parsing utilities.

This module provides the ConfigLoader class for loading agent configurations
from YAML files with automatic environment variable merging via Pydantic.
"""

import json
from pathlib import Path
from typing import Any, TypeVar

import yaml
from jsonschema import Draft7Validator, ValidationError
from pydantic_settings import BaseSettings

from .config import (
    CONFIG_DIR,
    DATASOURCE_TYPES,
    AgentConfig,
    DataAgentConfig,
    Datasource,
    FewShotExample,
    LLMConfig,
    TableSchema,
    ValidationConfig,
)

SCHEMA_PATH = CONFIG_DIR / "schema" / "agent_config.schema.json"

T = TypeVar("T", bound=BaseSettings)


class ConfigLoader:
    """Loads and parses agent configuration from YAML files.

    Environment variables are automatically merged with YAML values,
    with env vars taking precedence over YAML.

    Example:
        ```python
        config = ConfigLoader.load("path/to/config.yaml")
        # Or load by name from config directory
        config = ConfigLoader.load_by_name("contoso")
        ```
    """

    _schema: dict[str, Any] | None = None

    @classmethod
    def _get_schema(cls) -> dict[str, Any]:
        """Load and cache the JSON schema."""
        if cls._schema is None:
            with SCHEMA_PATH.open(encoding="utf-8") as f:
                cls._schema = json.load(f)
        assert (
            cls._schema is not None
        )  # Schema is guaranteed to be loaded at this point
        return cls._schema

    @classmethod
    def validate(cls, data: dict[str, Any]) -> list[str]:
        """Validate configuration data against the JSON schema.

        Args:
            data: Configuration data to validate.

        Returns:
            List of validation error messages (empty if valid).
        """
        schema = cls._get_schema()
        validator = Draft7Validator(schema)
        errors = sorted(validator.iter_errors(data), key=lambda e: e.path)
        return [cls._format_error(e) for e in errors]

    @staticmethod
    def _format_error(error: ValidationError) -> str:
        """Format a validation error into a readable message."""
        path = ".".join(str(p) for p in error.absolute_path) or "(root)"
        return f"{path}: {error.message}"

    @classmethod
    def load(cls, path: str | Path, validate: bool = True) -> AgentConfig:
        """Load agent configuration from a YAML file.

        Args:
            path: Path to the YAML configuration file.
            validate: Whether to validate against JSON schema (default True).

        Returns:
            Parsed AgentConfig instance.

        Raises:
            FileNotFoundError: If the config file doesn't exist.
            yaml.YAMLError: If the YAML is invalid.
            ValueError: If validation is enabled and schema validation fails.
        """
        path = Path(path)
        with path.open(encoding="utf-8") as f:
            raw = yaml.safe_load(f)

        if validate:
            errors = cls.validate(raw)
            if errors:
                raise ValueError(
                    f"Config validation failed for {path.name}:\n"
                    + "\n".join(f"  - {e}" for e in errors)
                )

        return cls._parse_config(raw)

    @classmethod
    def load_by_name(cls, name: str, validate: bool = True) -> AgentConfig:
        """Load agent configuration by name from the config directory.

        Args:
            name: Configuration name (without .yaml extension).
            validate: Whether to validate against JSON schema (default True).

        Returns:
            Parsed AgentConfig instance.
        """
        return cls.load(CONFIG_DIR / f"{name}.yaml", validate=validate)

    @classmethod
    def load_all(cls, validate: bool = True) -> AgentConfig:
        """Load and merge all configuration files from the config directory.

        Combines data_agents from all configs into a single AgentConfig.

        Args:
            validate: Whether to validate against JSON schema (default True).

        Returns:
            Merged AgentConfig instance with all data agents.
        """
        config_files = sorted(CONFIG_DIR.glob("*.yaml"))
        if not config_files:
            raise FileNotFoundError(f"No config files found in {CONFIG_DIR}")

        merged = cls.load(config_files[0], validate=validate)

        for config_file in config_files[1:]:
            config = cls.load(config_file, validate=validate)
            merged.data_agents.extend(config.data_agents)

        return merged

    @classmethod
    def _parse_config(cls, data: dict[str, Any]) -> AgentConfig:
        """Parse raw config dict into AgentConfig."""
        return AgentConfig(
            data_agents=[cls._parse_data_agent(a) for a in data.get("data_agents", [])],
            max_retries=data.get("max_retries", 3),
        )

    @classmethod
    def _parse_data_agent(cls, data: dict[str, Any]) -> DataAgentConfig:
        """Parse a single data agent config."""
        return DataAgentConfig(
            name=data.get("name", ""),
            description=data.get("description", ""),
            datasource=cls._parse_datasource(data.get("datasource")),
            llm_config=LLMConfig.from_dict(data.get("llm", {})),
            validation_config=ValidationConfig.from_dict(data.get("validation", {})),
            system_prompt=data.get("system_prompt", ""),
            response_prompt=data.get("response_prompt", ""),
            table_schemas=[
                TableSchema.from_dict(t) for t in data.get("table_schemas", [])
            ],
            few_shot_examples=[
                FewShotExample.from_dict(e) for e in data.get("few_shot_examples", [])
            ],
        )

    @classmethod
    def _parse_datasource(cls, data: dict[str, Any] | None) -> Datasource | None:
        """Parse datasource config with environment variable merging."""
        if not data:
            return None

        ds_type = data.get("type")
        if not ds_type or ds_type not in DATASOURCE_TYPES:
            raise ValueError(f"Invalid datasource type: {ds_type}")

        # Normalize 'schema' to 'db_schema' for postgres
        if ds_type == "postgres" and "schema" in data and "db_schema" not in data:
            data = {**data, "db_schema": data["schema"]}

        return cls._merge_env(DATASOURCE_TYPES[ds_type], data)

    @staticmethod
    def _merge_env(config_cls: type[T], yaml_data: dict[str, Any] | None) -> T | None:
        """Merge YAML config with environment variables.

        Env vars (loaded automatically by Pydantic) take precedence over YAML values.
        If yaml_data is None (config not declared in YAML), returns None regardless
        of env vars - env vars only augment explicitly declared configs.

        Args:
            config_cls: The BaseSettings config class.
            yaml_data: Raw YAML configuration dict, or None if not declared.

        Returns:
            Config instance if yaml_data was provided, None otherwise.
        """
        if yaml_data is None:
            return None

        env_config = config_cls()
        defaults = config_cls.model_construct().model_dump()

        merged = dict(yaml_data)
        for key, env_val in env_config.model_dump().items():
            if env_val != defaults.get(key):
                merged[key] = env_val

        return config_cls.model_validate(merged)


class SchemaFormatter:
    """Formats configuration schemas for LLM context."""

    @staticmethod
    def format_schema_context(agent_config: DataAgentConfig) -> str:
        """Format table schemas into a context string for the LLM."""
        if not agent_config.table_schemas:
            return ""

        lines = ["Available tables and their schemas:", ""]

        for table in agent_config.table_schemas:
            lines.append(f"Table: {table.name}")
            if table.description:
                lines.append(f"Description: {table.description}")
            lines.append("Columns:")

            for col in table.columns:
                col_line = f"  - {col.name} ({col.data_type}): {col.description}"
                if col.allowed_values:
                    values_str = ", ".join(
                        f"'{k}' = {v}" for k, v in col.allowed_values.items()
                    )
                    col_line += f" [Allowed: {values_str}]"
                if col.constraints:
                    col_line += f" [Constraints: {', '.join(col.constraints)}]"
                if col.formatting:
                    col_line += f" [Format: {col.formatting}]"
                lines.append(col_line)

            if table.sample_rows:
                lines.append("")
                lines.append(f"Sample rows from {table.name}:")
                col_names = list(table.sample_rows[0].keys())
                lines.append("  " + "\t".join(col_names))
                for row in table.sample_rows[:3]:
                    row_values = [str(row.get(c, ""))[:50] for c in col_names]
                    lines.append("  " + "\t".join(row_values))

            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def format_few_shot_examples(agent_config: DataAgentConfig) -> str:
        """Format few-shot examples into a context string for the LLM."""
        if not agent_config.few_shot_examples:
            return ""

        lines = ["Here are some example questions and their SQL queries:", ""]

        for i, ex in enumerate(agent_config.few_shot_examples, 1):
            lines.extend(
                [
                    f"Example {i}:",
                    f"Question: {ex.question}",
                    f"SQL: {ex.sql_query}",
                    f"Answer: {ex.answer}",
                    "",
                ]
            )

        return "\n".join(lines)
