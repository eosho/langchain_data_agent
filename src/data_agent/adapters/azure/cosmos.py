"""Azure Cosmos DB adapter implementation.

This module provides the CosmosAdapter for connecting to and querying
Azure Cosmos DB using the official azure-cosmos SDK with async support.

Cosmos DB is a NoSQL database and uses a SQL-like syntax that is NOT compatible
with SQLAlchemy. This adapter is kept separate from the SQLDatabase factory.
"""

from typing import TYPE_CHECKING, Any

from azure.cosmos.aio import CosmosClient

from data_agent.models.outputs import QueryResult

if TYPE_CHECKING:
    from azure.cosmos.aio import ContainerProxy, DatabaseProxy


class CosmosAdapter:
    """Adapter for Azure Cosmos DB NoSQL API.

    Uses the official azure-cosmos async SDK. Supports SQL API queries
    against Cosmos DB containers.

    Note:
        Cosmos DB uses a SQL-like syntax but is not a relational database.
        The adapter returns document results as dictionaries for consistency.

    Example:
        >>> async with CosmosAdapter(
        ...     endpoint="https://myaccount.documents.azure.com:443/",
        ...     database="mydb",
        ...     container="users",
        ...     key="your-key-here",
        ... ) as adapter:
        ...     result = await adapter.execute("SELECT * FROM c WHERE c.active = true")
    """

    def __init__(
        self,
        endpoint: str = "",
        database: str = "",
        container: str = "",
        key: str | None = None,
        connection_string: str | None = None,
        partition_key_path: str = "/id",
        use_aad: bool = False,
    ) -> None:
        """Initialize the Cosmos DB adapter.

        Args:
            endpoint: Cosmos DB account endpoint URL.
            database: Database name.
            container: Container name.
            key: Account key for authentication.
            connection_string: Full connection string (alternative to endpoint+key).
            partition_key_path: Partition key path for the container.
            use_aad: Use Azure AD authentication instead of key.
        """
        self._endpoint = endpoint
        self._database_name = database
        self._container_name = container
        self._key = key
        self._connection_string = connection_string
        self._partition_key_path = partition_key_path
        self._use_aad = use_aad
        self._client: CosmosClient | None = None
        self._database: DatabaseProxy | None = None
        self._container: ContainerProxy | None = None

    @property
    def dialect(self) -> str:
        """Return the dialect identifier for Cosmos DB.

        Returns:
            The string 'cosmosdb' - signals that sqlglot validation should be skipped.
        """
        return "cosmosdb"

    @property
    def container_name(self) -> str:
        """Return the current container name."""
        return self._container_name

    @property
    def partition_key_path(self) -> str:
        """Return the partition key path."""
        return self._partition_key_path

    async def connect(self) -> None:
        """Establish connection to Cosmos DB.

        Raises:
            ValueError: If no authentication method is provided.
            ConnectionError: If connection fails.
        """
        try:
            if self._connection_string:
                self._client = CosmosClient.from_connection_string(
                    self._connection_string
                )
            elif self._use_aad:
                from azure.identity.aio import DefaultAzureCredential

                credential = DefaultAzureCredential()
                self._client = CosmosClient(
                    url=self._endpoint,
                    credential=credential,
                )
            elif self._key:
                self._client = CosmosClient(
                    url=self._endpoint,
                    credential=self._key,
                )
            else:
                raise ValueError(
                    "Cosmos DB requires connection_string, key, or use_aad=True"
                )
            self._database = self._client.get_database_client(self._database_name)
            self._container = self._database.get_container_client(self._container_name)
        except ValueError:
            raise
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Cosmos DB: {e}") from e

    async def disconnect(self) -> None:
        """Close the Cosmos DB connection."""
        if self._client:
            await self._client.close()
            self._client = None
            self._database = None
            self._container = None

    async def execute(self, query: str) -> QueryResult:
        """Execute a SQL query against Cosmos DB.

        Args:
            query: The Cosmos DB SQL query to execute.

        Returns:
            QueryResult containing columns, rows, and metadata.

        Raises:
            RuntimeError: If not connected.
        """
        if not self._container:
            raise RuntimeError("Not connected to Cosmos DB. Call connect() first.")

        items: list[Any] = [
            item
            async for item in self._container.query_items(
                query=query,
            )
        ]

        if not items:
            return QueryResult(
                columns=[], rows=[], row_count=0, metadata={"query": query}
            )

        # Handle scalar results (e.g., SELECT VALUE COUNT(1))
        if not isinstance(items[0], dict):
            return QueryResult(
                columns=["value"],
                rows=[[item] for item in items],
                row_count=len(items),
                metadata={"query": query},
            )

        columns = list(items[0].keys())
        rows = [[item.get(col) for col in columns] for item in items]

        return QueryResult(
            columns=columns,
            rows=rows,
            row_count=len(rows),
            metadata={"query": query},
        )

    async def health_check(self) -> bool:
        """Check Cosmos DB connection health.

        Returns:
            True if connection is healthy, False otherwise.
        """
        if not self._container:
            return False
        try:
            await self.execute("SELECT VALUE 1")
            return True
        except Exception:
            return False

    async def set_container(self, container_name: str) -> None:
        """Switch to a different container.

        Args:
            container_name: Name of the container to switch to.

        Raises:
            RuntimeError: If not connected.
        """
        if not self._database:
            raise RuntimeError("Not connected to Cosmos DB.")
        self._container = self._database.get_container_client(container_name)
        self._container_name = container_name

    async def __aenter__(self) -> "CosmosAdapter":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.disconnect()
