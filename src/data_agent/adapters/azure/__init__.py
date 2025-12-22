"""Azure-specific adapters for the Data Agent.

This module provides the CosmosAdapter for Azure Cosmos DB.
SQL databases (Azure SQL, Synapse) use the factory in adapters/factory.py.
"""

from data_agent.adapters.azure.cosmos import CosmosAdapter

__all__ = [
    "CosmosAdapter",
]
