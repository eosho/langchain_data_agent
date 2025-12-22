"""SQLDatabase factory with Azure AD authentication support.

This module provides a factory function to create LangChain SQLDatabase instances
for various database types, with built-in support for Azure AD authentication.

Example:
    >>> from data_agent.adapters import create_sql_database
    >>> db = create_sql_database(
    ...     "postgres",
    ...     host="localhost",
    ...     port=5432,
    ...     database="mydb",
    ...     username="user",
    ...     password="pass",
    ... )
    >>> db.run("SELECT 1")
    '[(1,)]'
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langchain_community.utilities.sql_database import SQLDatabase
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine


def create_sql_database(
    datasource_type: str,
    host: str | None = None,
    port: int | None = None,
    database: str | None = None,
    username: str | None = None,
    password: str | None = None,
    connection_string: str | None = None,
    use_aad: bool = False,
    **kwargs: Any,
) -> SQLDatabase:
    """Create a SQLDatabase instance for the specified datasource type.

    Args:
        datasource_type: Type of database. Supported values: "postgres",
            "azure_sql", "synapse", "databricks", "bigquery", "mysql", "sqlite".
        host: Database hostname.
        port: Database port.
        database: Database name.
        username: Username for authentication.
        password: Password for authentication.
        connection_string: Full connection string (overrides other parameters).
        use_aad: Use Azure AD authentication via DefaultAzureCredential.
        **kwargs: Datasource-specific options and SQLDatabase options.
            Datasource options (passed to URI builder):
                - driver: ODBC driver for MSSQL
                - http_path, access_token, catalog: Databricks
                - project, dataset, credentials_path: BigQuery
            SQLDatabase options (passed to SQLDatabase):
                - schema, include_tables, ignore_tables, sample_rows_in_table_info

    Returns:
        Configured SQLDatabase instance.

    Raises:
        ValueError: If datasource_type is not supported or required parameters are missing.
        ImportError: If required packages are not installed.

    Example:
        >>> db = create_sql_database(
        ...     "postgres",
        ...     host="localhost",
        ...     port=5432,
        ...     database="mydb",
        ...     username="user",
        ...     password="pass",
        ... )
        >>> db.run("SELECT 1")
        '[(1,)]'
    """
    # Separate SQLDatabase options from URI builder options
    sqldb_keys = {
        "schema",
        "metadata",
        "ignore_tables",
        "include_tables",
        "sample_rows_in_table_info",
        "indexes_in_table_info",
        "custom_table_info",
        "view_support",
        "max_string_length",
        "lazy_table_reflection",
    }
    sqldb_options = {k: v for k, v in kwargs.items() if k in sqldb_keys}
    builder_options = {k: v for k, v in kwargs.items() if k not in sqldb_keys}

    if connection_string:
        return SQLDatabase.from_uri(connection_string, **sqldb_options)

    builder = _URI_BUILDERS.get(datasource_type)
    if builder is None:
        raise ValueError(
            f"Unsupported datasource type: {datasource_type}. "
            f"Supported types: {list(_URI_BUILDERS.keys())}"
        )

    uri = builder(
        host=host,
        port=port,
        database=database,
        username=username,
        password=password,
        use_aad=use_aad,
        **builder_options,
    )

    if use_aad and datasource_type in ("azure_sql", "synapse", "mssql"):
        driver = builder_options.get("driver", "ODBC Driver 18 for SQL Server")
        engine = _create_mssql_aad_engine(host, port, database, driver)
        return SQLDatabase(engine, **sqldb_options)

    return SQLDatabase.from_uri(uri, **sqldb_options)


def _build_postgres_uri(
    host: str | None,
    port: int | None,
    database: str | None,
    username: str | None,
    password: str | None,
    use_aad: bool = False,
    **options: Any,
) -> str:
    """Build PostgreSQL connection URI."""
    if use_aad:
        password = _get_postgres_aad_token()

    port = port or 5432
    return f"postgresql://{username}:{password}@{host}:{port}/{database}"


def _build_mssql_uri(
    host: str | None,
    port: int | None,
    database: str | None,
    username: str | None,
    password: str | None,
    use_aad: bool = False,
    driver: str = "ODBC Driver 18 for SQL Server",
    **options: Any,
) -> str:
    """Build Microsoft SQL Server connection URI."""
    port = port or 1433
    driver_encoded = driver.replace(" ", "+")

    if use_aad:
        # For AAD, build URI without any credentials.
        # The token is injected via SQLAlchemy event listener.
        return (
            f"mssql+pyodbc://{host}:{port}/{database}"
            f"?driver={driver_encoded}&Encrypt=yes&TrustServerCertificate=no"
        )

    return (
        f"mssql+pyodbc://{username}:{password}@{host}:{port}/{database}"
        f"?driver={driver_encoded}&Encrypt=yes&TrustServerCertificate=no"
    )


def _build_databricks_uri(
    host: str | None,
    port: int | None,
    database: str | None,
    username: str | None,
    password: str | None,
    http_path: str | None = None,
    access_token: str | None = None,
    catalog: str | None = None,
    **options: Any,
) -> str:
    """Build Databricks SQL connection URI."""
    catalog = catalog or database
    return (
        f"databricks://token:{access_token}@{host}"
        f"?http_path={http_path}&catalog={catalog}"
    )


def _build_bigquery_uri(
    host: str | None,
    port: int | None,
    database: str | None,
    username: str | None,
    password: str | None,
    project: str | None = None,
    dataset: str | None = None,
    credentials_path: str | None = None,
    **options: Any,
) -> str:
    """Build BigQuery connection URI."""
    project = project or database
    uri = f"bigquery://{project}"
    if dataset:
        uri += f"/{dataset}"
    if credentials_path:
        uri += f"?credentials_path={credentials_path}"
    return uri


def _build_mysql_uri(
    host: str | None,
    port: int | None,
    database: str | None,
    username: str | None,
    password: str | None,
    **options: Any,
) -> str:
    """Build MySQL connection URI."""
    port = port or 3306
    return f"mysql+pymysql://{username}:{password}@{host}:{port}/{database}"


def _build_sqlite_uri(
    host: str | None,
    port: int | None,
    database: str | None,
    username: str | None,
    password: str | None,
    **options: Any,
) -> str:
    """Build SQLite connection URI."""
    return f"sqlite:///{database}"


_URI_BUILDERS: dict[str, Callable[..., str]] = {
    "postgres": _build_postgres_uri,
    "postgresql": _build_postgres_uri,
    "azure_sql": _build_mssql_uri,
    "synapse": _build_mssql_uri,
    "mssql": _build_mssql_uri,
    "databricks": _build_databricks_uri,
    "bigquery": _build_bigquery_uri,
    "mysql": _build_mysql_uri,
    "sqlite": _build_sqlite_uri,
}


def _get_postgres_aad_token() -> str:
    """Get Azure AD token for Azure Database for PostgreSQL.

    Returns:
        Access token string to use as password.

    Raises:
        ImportError: If azure-identity is not installed.
    """
    try:
        from azure.identity import DefaultAzureCredential
    except ImportError as e:
        raise ImportError(
            "azure-identity is required for AAD authentication. "
            "Install with: pip install azure-identity"
        ) from e

    credential = DefaultAzureCredential()
    token = credential.get_token("https://ossrdbms-aad.database.windows.net/.default")
    return token.token


def _get_mssql_aad_token_struct() -> bytes:
    """Get Azure AD token for Azure SQL Database as bytes struct.

    Returns:
        Token struct in format required by pyodbc.

    Raises:
        ImportError: If azure-identity is not installed.
    """
    import struct

    try:
        from azure.identity import DefaultAzureCredential
    except ImportError as e:
        raise ImportError(
            "azure-identity is required for AAD authentication. "
            "Install with: pip install azure-identity"
        ) from e

    credential = DefaultAzureCredential()
    token = credential.get_token("https://database.windows.net/.default")
    token_bytes = token.token.encode("utf-16-le")
    return struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)


def _create_mssql_aad_engine(
    host: str | None,
    port: int | None,
    database: str | None,
    driver: str = "ODBC Driver 18 for SQL Server",
) -> Engine:
    """Create SQLAlchemy engine with AAD token injection for MSSQL.

    Uses odbc_connect parameter with raw ODBC connection string to avoid
    SQLAlchemy adding any default authentication parameters.

    Args:
        host: SQL Server hostname.
        port: SQL Server port.
        database: Database name.
        driver: ODBC driver name.

    Returns:
        SQLAlchemy Engine with AAD token injection.
    """
    from urllib.parse import quote_plus

    import pyodbc

    port = port or 1433

    odbc_conn_str = (
        f"Driver={{{driver}}};"
        f"Server=tcp:{host},{port};"
        f"Database={database};"
        f"Encrypt=yes;"
        f"TrustServerCertificate=no;"
        f"Connection Timeout=30"
    )

    uri = f"mssql+pyodbc:///?odbc_connect={quote_plus(odbc_conn_str)}"

    def get_connection():
        """Create connection with AAD token."""
        token_struct = _get_mssql_aad_token_struct()
        sql_copt_ss_access_token = 1256
        return pyodbc.connect(
            odbc_conn_str, attrs_before={sql_copt_ss_access_token: token_struct}
        )

    engine = create_engine(uri, creator=get_connection)
    return engine
