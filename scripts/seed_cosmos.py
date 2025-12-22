import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

CONFIG_DIR = Path(__file__).parent.parent / "src" / "data_agent" / "config"


def load_config(config_name: str, agent_name: str | None = None) -> dict:
    """Load Cosmos config from YAML file."""
    config_path = CONFIG_DIR / f"{config_name}.yaml"
    if not config_path.exists():
        print(f"Config file not found: {config_path}")
        sys.exit(1)

    with config_path.open(encoding="utf-8") as f:
        config = yaml.safe_load(f)

    for agent in config.get("data_agents", []):
        if agent.get("cosmos_config"):
            if agent_name is None or agent.get("name") == agent_name:
                cosmos_config = agent["cosmos_config"]
                return {
                    "agent_name": agent.get("name", "unknown"),
                    "endpoint": cosmos_config.get("endpoint", ""),
                    "database": cosmos_config.get("database", ""),
                    "container": cosmos_config.get("container", ""),
                    "use_aad": cosmos_config.get("use_aad", False),
                    "connection_string": os.getenv(
                        "COSMOS_CONNECTION_STRING",
                        cosmos_config.get("connection_string", ""),
                    ),
                    "key": os.getenv("COSMOS_KEY", cosmos_config.get("key", "")),
                }

    print(
        f"No cosmos_config found in {config_name}.yaml"
        + (f" for agent '{agent_name}'" if agent_name else "")
    )
    sys.exit(1)


def load_data() -> list[dict]:
    """Load sample data from JSON file."""
    data_file = Path(__file__).parent / "data" / "cosmos_data.json"
    if not data_file.exists():
        print(f"Data file not found: {data_file}")
        sys.exit(1)

    with Path(data_file).open(encoding="utf-8") as f:
        data = json.load(f)
        return data.get("products", [])


async def seed_cosmos(config_name: str, agent_name: str | None = None) -> None:
    """Seed Cosmos DB with product catalog from JSON file."""
    config = load_config(config_name, agent_name)

    if not config["endpoint"] and not config["connection_string"]:
        print("Either endpoint or connection_string is required in cosmos_config")
        sys.exit(1)

    try:
        from azure.cosmos import PartitionKey
        from azure.cosmos.aio import CosmosClient
    except ImportError:
        print("azure-cosmos is required. Install with: uv add azure-cosmos")
        sys.exit(1)

    if config["connection_string"]:
        print("Connecting to Cosmos DB using connection string...")
        client = CosmosClient.from_connection_string(config["connection_string"])
    elif config["use_aad"]:
        print(
            f"Connecting to {config['endpoint']} using Azure AD (DefaultAzureCredential)..."
        )
        try:
            from azure.identity.aio import DefaultAzureCredential
        except ImportError:
            print(
                "azure-identity is required for AAD authentication. Install with: uv add azure-identity"
            )
            sys.exit(1)
        credential = DefaultAzureCredential()
        client = CosmosClient(config["endpoint"], credential=credential)
    else:
        if not config["key"]:
            print(
                "key (or COSMOS_KEY env var) is required when use_aad=false and no connection_string"
            )
            sys.exit(1)
        print(f"Connecting to {config['endpoint']} using key authentication...")
        client = CosmosClient(config["endpoint"], config["key"])

    async with client:
        print(f"Creating database '{config['database']}' if not exists...")
        try:
            database = await client.create_database_if_not_exists(config["database"])
            print("Database ready")
        except Exception as e:
            print(f"Failed to create database: {e}")
            sys.exit(1)

        print(f"Creating container '{config['container']}' if not exists...")
        try:
            container = await database.create_container_if_not_exists(
                id=config["container"],
                partition_key=PartitionKey(path="/category"),
            )
            print("Container ready")
        except Exception as e:
            print(f"Failed to create container: {e}")
            sys.exit(1)

        products = load_data()
        print(f"Inserting {len(products)} products...")

        inserted = 0
        failed = 0
        for product in products:
            try:
                await container.upsert_item(product)
                inserted += 1
            except Exception as e:
                print(f"  Failed to insert product {product.get('id', 'unknown')}: {e}")
                failed += 1

        if failed > 0:
            print(f"Inserted {inserted} products, {failed} failed")
        else:
            print(f"Inserted {inserted} products")

        print(f"Cosmos DB seeded successfully for agent '{config['agent_name']}'!")


def main() -> None:
    """Entry point."""
    parser = argparse.ArgumentParser(
        description="Seed Azure Cosmos DB with product catalog data"
    )
    parser.add_argument(
        "--config",
        "-c",
        default="contoso",
        help="Config file name (without .yaml extension)",
    )
    parser.add_argument(
        "--agent",
        "-a",
        default="contoso_products",
        help="Agent name within the config (default: first agent with cosmos_config)",
    )
    args = parser.parse_args()
    asyncio.run(seed_cosmos(args.config, args.agent))


if __name__ == "__main__":
    main()
