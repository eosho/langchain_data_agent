"""Configuration dataclasses and connection settings.

This module defines configuration structures for database connections and agent settings.
For loading configs from YAML, see config_loader.py.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

CONFIG_DIR = Path(__file__).resolve().parent / "config"

DatasourceType = Literal[
    "databricks", "cosmos", "postgres", "azure_sql", "synapse", "bigquery"
]


@dataclass
class FewShotExample:
    """A few-shot example for SQL generation."""

    question: str
    sql_query: str
    answer: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FewShotExample":
        return cls(
            question=data.get("question", ""),
            sql_query=data.get("sql_query", ""),
            answer=data.get("answer", ""),
        )


@dataclass
class ColumnSchema:
    """Schema definition for a database column."""

    name: str
    data_type: str = ""
    description: str = ""
    allowed_values: dict[str, str] = field(default_factory=dict)
    examples: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    formatting: str = ""
    nullable: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ColumnSchema":
        return cls(
            name=data.get("column_name", data.get("name", "")),
            data_type=data.get("data_type", data.get("type", "")),
            description=data.get("description", ""),
            allowed_values=data.get("allowed_values", {}),
            examples=data.get("examples", []),
            constraints=data.get("constraints", []),
            formatting=data.get("formatting", ""),
            nullable=data.get("nullable", False),
        )


@dataclass
class TableSchema:
    """Schema definition for a database table."""

    name: str
    description: str = ""
    columns: list[ColumnSchema] = field(default_factory=list)
    sample_rows: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TableSchema":
        return cls(
            name=data.get("table_name", data.get("name", "")),
            description=data.get("table_description", data.get("description", "")),
            columns=[ColumnSchema.from_dict(c) for c in data.get("columns", [])],
            sample_rows=data.get("sample_rows", []),
        )


class DatabricksDatasource(BaseSettings):
    """Databricks SQL Warehouse connection.

    Attributes:
        type: Datasource type identifier.
        hostname: Databricks workspace hostname.
        path: SQL warehouse HTTP path.
        catalog: Unity Catalog name.
        db_schema: Database schema name.
        access_token: Personal access token for authentication.
    """

    model_config = SettingsConfigDict(
        env_prefix="DATABRICKS_",
        env_file=".env",
        extra="ignore",
    )

    type: Literal["databricks"] = "databricks"
    hostname: str = Field(default="", validation_alias="DATABRICKS_HOST")
    path: str = Field(default="", validation_alias="DATABRICKS_PATH")
    catalog: str = "hive_metastore"
    db_schema: str = Field(default="default", validation_alias="DATABRICKS_SCHEMA")
    access_token: str = Field(default="", validation_alias="DATABRICKS_TOKEN")


class CosmosDatasource(BaseSettings):
    """Azure Cosmos DB connection.

    Attributes:
        type: Datasource type identifier.
        endpoint: Cosmos DB account endpoint URL.
        database: Database name.
        container: Container name.
        key: Account key for authentication.
        connection_string: Full connection string (alternative to endpoint+key).
        use_aad: Use Azure AD authentication instead of key.
    """

    model_config = SettingsConfigDict(
        env_prefix="COSMOS_",
        env_file=".env",
        extra="ignore",
    )

    type: Literal["cosmos"] = "cosmos"
    endpoint: str = ""
    database: str = ""
    container: str = ""
    key: str = ""
    connection_string: str = ""
    use_aad: bool = False


class PostgresDatasource(BaseSettings):
    """PostgreSQL connection.

    Attributes:
        type: Datasource type identifier.
        host: Database server hostname.
        port: Database server port.
        database: Database name.
        username: Database username.
        password: Database password.
        db_schema: Schema name.
        connection_string: Full connection string (overrides other settings).
    """

    model_config = SettingsConfigDict(
        env_prefix="POSTGRES_",
        env_file=".env",
        extra="ignore",
    )

    type: Literal["postgres"] = "postgres"
    host: str = "localhost"
    port: int = 5432
    database: str = ""
    username: str = ""
    password: str = ""
    db_schema: str = Field(default="public", validation_alias="POSTGRES_SCHEMA")
    connection_string: str = ""


class _MSSQLDatasourceBase(BaseSettings):
    """Base class for Microsoft SQL Server-based datasources.

    Attributes:
        server: SQL server hostname.
        database: Database name.
        username: SQL authentication username.
        password: SQL authentication password.
        db_schema: Database schema name.
        use_aad: Use Azure AD authentication instead of SQL auth.
        driver: ODBC driver name.
        connection_string: Full connection string (overrides other settings).
    """

    server: str = ""
    database: str = ""
    username: str = ""
    password: str = ""
    db_schema: str = "dbo"
    use_aad: bool = False
    driver: str = "ODBC Driver 18 for SQL Server"
    connection_string: str = ""


class AzureSQLDatasource(_MSSQLDatasourceBase):
    """Azure SQL Database connection.

    Attributes:
        type: Datasource type identifier.
        server: SQL server hostname (e.g., myserver.database.windows.net).
        database: Database name.
        username: SQL authentication username.
        password: SQL authentication password.
        use_aad: Use Azure AD authentication instead of SQL auth.
        driver: ODBC driver name.
        connection_string: Full connection string (overrides other settings).
    """

    model_config = SettingsConfigDict(
        env_prefix="AZURE_SQL_",
        env_file=".env",
        extra="ignore",
    )

    type: Literal["azure_sql"] = "azure_sql"


class SynapseDatasource(_MSSQLDatasourceBase):
    """Azure Synapse Analytics connection.

    Attributes:
        type: Datasource type identifier.
        server: Synapse SQL endpoint (e.g., myworkspace.sql.azuresynapse.net).
        database: Database name.
        username: SQL authentication username.
        password: SQL authentication password.
        use_aad: Use Azure AD authentication instead of SQL auth.
        driver: ODBC driver name.
        connection_string: Full connection string (overrides other settings).
        pool: Dedicated or serverless pool name.
    """

    model_config = SettingsConfigDict(
        env_prefix="SYNAPSE_",
        env_file=".env",
        extra="ignore",
    )

    type: Literal["synapse"] = "synapse"
    pool: str = "Built-in"


class BigQueryDatasource(BaseSettings):
    """Google BigQuery connection.

    Attributes:
        type: Datasource type identifier.
        project: Google Cloud project ID.
        project_id: Google Cloud project ID (alias for project).
        dataset: BigQuery dataset name.
        location: BigQuery dataset location (e.g., US, EU).
        credentials_path: Path to service account credentials JSON.
        credentials_json: Service account credentials as JSON string.
    """

    model_config = SettingsConfigDict(
        env_prefix="BIGQUERY_",
        env_file=".env",
        extra="ignore",
    )

    type: Literal["bigquery"] = "bigquery"
    project: str = ""
    project_id: str = Field(default="", validation_alias="GOOGLE_CLOUD_PROJECT")
    dataset: str = ""
    location: str = "US"
    credentials_path: str = Field(
        default="", validation_alias="GOOGLE_APPLICATION_CREDENTIALS"
    )
    credentials_json: str = ""


Datasource = (
    DatabricksDatasource
    | CosmosDatasource
    | PostgresDatasource
    | AzureSQLDatasource
    | SynapseDatasource
    | BigQueryDatasource
)

DATASOURCE_TYPES: dict[str, type[Datasource]] = {
    "databricks": DatabricksDatasource,
    "cosmos": CosmosDatasource,
    "postgres": PostgresDatasource,
    "azure_sql": AzureSQLDatasource,
    "synapse": SynapseDatasource,
    "bigquery": BigQueryDatasource,
}


@dataclass
class LLMConfig:
    """LLM configuration settings."""

    provider: str = "azure_openai"
    model: str = "gpt-5-mini"
    api_version: str = "2024-12-01-preview"
    temperature: float = 0.0
    max_tokens: int | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LLMConfig":
        return cls(
            provider=data.get("provider", "azure_openai"),
            model=data.get("model", ""),
            api_version=data.get("api_version", "2024-12-01-preview"),
            temperature=data.get("temperature", 0.0),
            max_tokens=data.get("max_tokens"),
        )


@dataclass
class ValidationConfig:
    """SQL validation configuration settings."""

    max_rows: int = 10000
    blocked_functions: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ValidationConfig":
        return cls(
            max_rows=data.get("max_rows", 10000),
            blocked_functions=data.get("blocked_functions", []),
        )


@dataclass
class DataAgentConfig:
    """Configuration for a single data agent."""

    name: str
    description: str = ""
    datasource: Datasource | None = None
    llm_config: LLMConfig = field(default_factory=LLMConfig)
    validation_config: ValidationConfig = field(default_factory=ValidationConfig)
    system_prompt: str = ""
    response_prompt: str = ""
    table_schemas: list[TableSchema] = field(default_factory=list)
    few_shot_examples: list[FewShotExample] = field(default_factory=list)


@dataclass
class IntentDetectionConfig:
    """Configuration for intent detection agent."""

    llm_config: LLMConfig = field(default_factory=LLMConfig)
    system_prompt: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IntentDetectionConfig":
        return cls(
            llm_config=LLMConfig.from_dict(data.get("llm", {})),
            system_prompt=data.get("system_prompt", ""),
        )


@dataclass
class AgentConfig:
    """Complete agent configuration."""

    intent_detection: IntentDetectionConfig = field(
        default_factory=IntentDetectionConfig
    )
    data_agents: list[DataAgentConfig] = field(default_factory=list)
    max_retries: int = 3
