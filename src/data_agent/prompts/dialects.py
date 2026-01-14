"""SQL dialect-specific guidelines for query generation.

This module provides dialect-specific SQL guidelines that are automatically
appended to system prompts based on the datasource type.
"""

BIGQUERY_GUIDELINES = """## BigQuery SQL Guidelines

1. **Use BigQuery SQL syntax:**
   - DATE_TRUNC, DATE_ADD, DATE_SUB for date operations
   - CURRENT_DATE(), CURRENT_TIMESTAMP() for current time
   - EXTRACT(YEAR FROM date), EXTRACT(MONTH FROM date) for date parts
   - STRING, INT64, FLOAT64, NUMERIC, BOOL data types
   - Use backticks for table names: `project.dataset.table`

2. **Aggregation functions:**
   - SUM(), AVG(), COUNT(), MIN(), MAX()
   - COUNTIF(), SUMIF() for conditional aggregations
   - APPROX_COUNT_DISTINCT() for large cardinality counts

3. **String functions:**
   - CONCAT(), SUBSTR(), UPPER(), LOWER(), TRIM()
   - REGEXP_CONTAINS(), REGEXP_EXTRACT() for regex
   - FORMAT() for string formatting

4. **Best practices:**
   - Always qualify column names with table aliases
   - Use LIMIT to restrict results unless user specifies otherwise
   - Use fully qualified table names: `project.dataset.table`
   - Partition filters improve performance (e.g., WHERE partition_date >= ...)
"""

POSTGRES_GUIDELINES = """## PostgreSQL SQL Guidelines

1. **Use PostgreSQL syntax:**
   - DATE_TRUNC(), DATE_PART() for date operations
   - NOW(), CURRENT_DATE, CURRENT_TIMESTAMP for current time
   - EXTRACT(YEAR FROM date) for date parts
   - TEXT, INTEGER, BIGINT, NUMERIC, BOOLEAN data types
   - Use double quotes for identifiers with special characters

2. **Aggregation functions:**
   - SUM(), AVG(), COUNT(), MIN(), MAX()
   - COUNT(*) FILTER (WHERE condition) for conditional counts
   - ARRAY_AGG(), STRING_AGG() for aggregation

3. **String functions:**
   - CONCAT(), SUBSTRING(), UPPER(), LOWER(), TRIM()
   - ~ operator or SIMILAR TO for regex matching
   - FORMAT() for string formatting

4. **Best practices:**
   - Always qualify column names with table aliases
   - Use LIMIT to restrict results unless user specifies otherwise
   - Use schema-qualified table names: schema.table
"""

AZURE_SQL_GUIDELINES = """## Azure SQL / SQL Server Guidelines

1. **Use T-SQL syntax:**
   - DATEPART(), DATEDIFF(), DATEADD() for date operations
   - GETDATE(), GETUTCDATE() for current time
   - VARCHAR, NVARCHAR, INT, BIGINT, DECIMAL, BIT data types
   - Use square brackets for identifiers: [schema].[table]

2. **Aggregation functions:**
   - SUM(), AVG(), COUNT(), MIN(), MAX()
   - COUNT(*) with CASE for conditional counts
   - STRING_AGG() for string aggregation (SQL Server 2017+)

3. **String functions:**
   - CONCAT(), SUBSTRING(), UPPER(), LOWER(), LTRIM(), RTRIM()
   - LIKE with wildcards for pattern matching
   - FORMAT() for string formatting

4. **Best practices:**
   - Always qualify column names with table aliases
   - Use TOP N instead of LIMIT
   - Use schema-qualified table names: [schema].[table]
"""

SYNAPSE_GUIDELINES = """## Azure Synapse Analytics Guidelines

1. **Use Synapse SQL syntax:**
   - Similar to T-SQL with distributed query optimizations
   - DATEPART(), DATEDIFF(), DATEADD() for date operations
   - GETDATE(), GETUTCDATE() for current time
   - VARCHAR, NVARCHAR, INT, BIGINT, DECIMAL data types

2. **Aggregation functions:**
   - SUM(), AVG(), COUNT(), MIN(), MAX()
   - APPROX_COUNT_DISTINCT() for large tables

3. **Best practices:**
   - Use TOP N instead of LIMIT
   - Filter on distribution columns when possible
   - Use schema-qualified table names: [schema].[table]
   - Avoid SELECT * on large tables
"""

DATABRICKS_GUIDELINES = """## Databricks SQL Guidelines

1. **Use Databricks SQL syntax:**
   - DATE_TRUNC(), DATE_ADD(), DATE_SUB() for date operations
   - CURRENT_DATE(), CURRENT_TIMESTAMP() for current time
   - STRING, INT, BIGINT, DOUBLE, DECIMAL, BOOLEAN data types

2. **Aggregation functions:**
   - SUM(), AVG(), COUNT(), MIN(), MAX()
   - APPROX_COUNT_DISTINCT() for large cardinality
   - COLLECT_LIST(), COLLECT_SET() for arrays

3. **Best practices:**
   - Always qualify column names with table aliases
   - Use LIMIT to restrict results
   - Use catalog.schema.table naming convention
   - Delta Lake tables support time travel: SELECT * FROM table@v1
"""

COSMOS_GUIDELINES = """## Azure Cosmos DB SQL Guidelines

1. **Use Cosmos DB SQL syntax:**
   - SELECT, FROM, WHERE, ORDER BY, TOP
   - No JOINs between containers (only within documents)
   - Array functions: ARRAY_CONTAINS(), ARRAY_LENGTH()

2. **Query limitations:**
   - Always include partition key in WHERE clause for efficiency
   - Cross-partition queries are expensive
   - No GROUP BY or aggregations without partition key filter

3. **Best practices:**
   - Filter by partition key first
   - Use TOP instead of LIMIT
   - Prefer point reads over queries when possible
"""

# Map datasource types to their guidelines
DIALECT_GUIDELINES_MAP: dict[str, str] = {
    "bigquery": BIGQUERY_GUIDELINES,
    "postgres": POSTGRES_GUIDELINES,
    "postgresql": POSTGRES_GUIDELINES,
    "azure_sql": AZURE_SQL_GUIDELINES,
    "mssql": AZURE_SQL_GUIDELINES,
    "sqlserver": AZURE_SQL_GUIDELINES,
    "synapse": SYNAPSE_GUIDELINES,
    "databricks": DATABRICKS_GUIDELINES,
    "cosmos": COSMOS_GUIDELINES,
    "cosmosdb": COSMOS_GUIDELINES,
}


def get_dialect_guidelines(datasource_type: str) -> str:
    """Get SQL guidelines for a specific datasource type.

    Args:
        datasource_type: Database type (e.g., 'bigquery', 'azure_sql', 'postgres').

    Returns:
        Dialect-specific SQL guidelines, or empty string if not found.
    """
    return DIALECT_GUIDELINES_MAP.get(datasource_type.lower(), "")
