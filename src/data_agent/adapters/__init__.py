"""Database adapters for the Data Agent.

This module provides:
- create_sql_database: Factory function to create SQLDatabase instances for all SQL databases
- CosmosAdapter: Adapter for Azure Cosmos DB (NoSQL, not compatible with SQLDatabase)
- QueryResult: Structured result from database query execution

Example:
    >>> from data_agent.adapters import create_sql_database, CosmosAdapter
    >>>
    >>> # SQL databases via factory
    >>> db = create_sql_database("postgres", host="localhost", database="mydb", ...)
    >>> result = db.run("SELECT 1")
    >>>
    >>> # Cosmos DB via adapter
    >>> async with CosmosAdapter(endpoint="...", database="db", container="c") as adapter:
    ...     result = await adapter.execute("SELECT * FROM c")
"""

from data_agent.adapters.azure.cosmos import CosmosAdapter
from data_agent.adapters.factory import create_sql_database
from data_agent.models.outputs import QueryResult

__all__ = [
    "CosmosAdapter",
    "QueryResult",
    "create_sql_database",
]
