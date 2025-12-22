import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

CONFIG_DIR = Path(__file__).parent.parent / "src" / "data_agent" / "config"


def load_config(config_name: str, agent_name: str | None = None) -> dict:
    """Load PostgreSQL config from YAML file."""
    config_path = CONFIG_DIR / f"{config_name}.yaml"
    if not config_path.exists():
        print(f"Config file not found: {config_path}")
        sys.exit(1)

    with config_path.open(encoding="utf-8") as f:
        config = yaml.safe_load(f)

    for agent in config.get("data_agents", []):
        if agent.get("postgres_config"):
            if agent_name is None or agent.get("name") == agent_name:
                pg_config = agent["postgres_config"]
                return {
                    "agent_name": agent.get("name", "unknown"),
                    "host": pg_config.get("host", "localhost"),
                    "port": pg_config.get("port", 5432),
                    "database": pg_config.get("database", ""),
                    "user": pg_config.get("username", "postgres"),
                    "password": os.getenv(
                        "POSTGRES_PASSWORD", pg_config.get("password", "")
                    ),
                    "schema": pg_config.get("schema", "public"),
                    "connection_string": os.getenv(
                        "POSTGRES_CONNECTION_STRING",
                        pg_config.get("connection_string", ""),
                    ),
                }

    print(
        f"No postgres_config found in {config_name}.yaml"
        + (f" for agent '{agent_name}'" if agent_name else "")
    )
    sys.exit(1)


POSTGRES_SCHEMA_SQL = """
DROP TABLE IF EXISTS shipments CASCADE;
DROP TABLE IF EXISTS inventory CASCADE;
DROP TABLE IF EXISTS warehouses CASCADE;

CREATE TABLE warehouses (
    warehouse_id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    location TEXT NOT NULL,
    capacity INTEGER NOT NULL,
    is_active BOOLEAN DEFAULT true
);

CREATE TABLE inventory (
    inventory_id SERIAL PRIMARY KEY,
    product_id TEXT NOT NULL,
    warehouse_id INTEGER REFERENCES warehouses(warehouse_id),
    quantity INTEGER NOT NULL DEFAULT 0,
    reorder_level INTEGER NOT NULL DEFAULT 10,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE shipments (
    shipment_id SERIAL PRIMARY KEY,
    warehouse_id INTEGER REFERENCES warehouses(warehouse_id),
    shipment_type TEXT NOT NULL CHECK (shipment_type IN ('inbound', 'outbound')),
    status TEXT NOT NULL CHECK (status IN ('pending', 'in_transit', 'delivered', 'cancelled')),
    scheduled_date DATE NOT NULL,
    actual_date DATE
);

CREATE INDEX idx_inventory_product ON inventory(product_id);
CREATE INDEX idx_inventory_warehouse ON inventory(warehouse_id);
CREATE INDEX idx_inventory_quantity ON inventory(quantity);
CREATE INDEX idx_shipments_status ON shipments(status);
CREATE INDEX idx_shipments_warehouse ON shipments(warehouse_id);
"""


def load_data() -> dict:
    """Load sample data from JSON file."""
    data_file = Path(__file__).parent / "data" / "postgres_data.json"
    if not data_file.exists():
        print(f"Data file not found: {data_file}")
        sys.exit(1)

    with Path(data_file).open(encoding="utf-8") as f:
        return json.load(f)


async def seed_postgres(config_name: str, agent_name: str | None = None) -> None:
    """Seed PostgreSQL with inventory data from JSON file."""
    config = load_config(config_name, agent_name)

    try:
        import asyncpg
    except ImportError:
        print("asyncpg is required. Install with: uv add asyncpg")
        sys.exit(1)

    if config["connection_string"]:
        print("Connecting to PostgreSQL using connection string...")
        try:
            conn = await asyncpg.connect(config["connection_string"])
            print("Connected to PostgreSQL")
        except Exception as e:
            print(f"Failed to connect: {e}")
            sys.exit(1)
    else:
        if not config["database"]:
            print("database is required in postgres_config")
            sys.exit(1)

        if not config["password"]:
            print("No password set - attempting connection without password")

        print(f"Connecting to {config['host']}:{config['port']}...")

        try:
            conn = await asyncpg.connect(
                host=config["host"],
                port=config["port"],
                user=config["user"],
                password=config["password"],
                database="postgres",
            )
            print("Connected to PostgreSQL")

            exists = await conn.fetchval(
                "SELECT 1 FROM pg_database WHERE datname = $1",
                config["database"],
            )

            if not exists:
                print(f"Creating database '{config['database']}'...")
                await conn.execute(f'CREATE DATABASE {config["database"]}')
                print("Database created")
            else:
                print(f"Database '{config['database']}' exists")

            await conn.close()
        except Exception as e:
            print(f"Failed to connect: {e}")
            sys.exit(1)

        print(f"Connecting to database '{config['database']}'...")
        conn = await asyncpg.connect(
            host=config["host"],
            port=config["port"],
            user=config["user"],
            password=config["password"],
            database=config["database"],
        )
        print("Connected")

    print("Creating schema...")
    await conn.execute(POSTGRES_SCHEMA_SQL)
    print("Schema created")

    data = load_data()

    print(f"Inserting {len(data['warehouses'])} warehouses...")
    for w in data["warehouses"]:
        await conn.execute(
            "INSERT INTO warehouses (name, location, capacity, is_active) VALUES ($1, $2, $3, $4)",
            w["name"],
            w["location"],
            w["capacity"],
            w["is_active"],
        )
    print(f"Inserted {len(data['warehouses'])} warehouses")

    print(f"Inserting {len(data['inventory'])} inventory records...")
    for inv in data["inventory"]:
        last_updated = datetime.fromisoformat(
            inv["last_updated"].replace("Z", "+00:00")
        )
        await conn.execute(
            "INSERT INTO inventory (product_id, warehouse_id, quantity, reorder_level, last_updated) VALUES ($1, $2, $3, $4, $5)",
            inv["product_id"],
            inv["warehouse_id"],
            inv["quantity"],
            inv["reorder_level"],
            last_updated,
        )
    print(f"Inserted {len(data['inventory'])} inventory records")

    print(f"Inserting {len(data['shipments'])} shipments...")
    for s in data["shipments"]:
        from datetime import date as date_type

        scheduled_parts = s["scheduled_date"].split("-")
        scheduled_date = date_type(
            int(scheduled_parts[0]), int(scheduled_parts[1]), int(scheduled_parts[2])
        )
        actual_date = None
        if s.get("actual_date"):
            actual_parts = s["actual_date"].split("-")
            actual_date = date_type(
                int(actual_parts[0]), int(actual_parts[1]), int(actual_parts[2])
            )

        await conn.execute(
            "INSERT INTO shipments (warehouse_id, shipment_type, status, scheduled_date, actual_date) VALUES ($1, $2, $3, $4, $5)",
            s["warehouse_id"],
            s["shipment_type"],
            s["status"],
            scheduled_date,
            actual_date,
        )
    print(f"Inserted {len(data['shipments'])} shipments")

    # Stats
    warehouse_count = await conn.fetchval("SELECT COUNT(*) FROM warehouses")
    inventory_count = await conn.fetchval("SELECT COUNT(*) FROM inventory")
    shipment_count = await conn.fetchval("SELECT COUNT(*) FROM shipments")
    low_stock = await conn.fetchval(
        "SELECT COUNT(*) FROM inventory WHERE quantity < reorder_level"
    )
    in_transit = await conn.fetchval(
        "SELECT COUNT(*) FROM shipments WHERE status = 'in_transit'"
    )

    print("\nSummary:")
    print(f"  Warehouses: {warehouse_count}")
    print(f"  Inventory records: {inventory_count}")
    print(f"  Shipments: {shipment_count}")
    print(f"  Low stock items: {low_stock}")
    print(f"  In transit: {in_transit}")

    await conn.close()

    print(f"\nPostgreSQL seeded successfully for agent '{config['agent_name']}'!")


def main() -> None:
    """Entry point."""
    parser = argparse.ArgumentParser(description="Seed PostgreSQL with inventory data")
    parser.add_argument(
        "--config",
        "-c",
        default="contoso",
        help="Config file name (without .yaml extension)",
    )
    parser.add_argument(
        "--agent",
        "-a",
        default="contoso_inventory",
        help="Agent name within the config (default: first agent with postgres_config)",
    )
    args = parser.parse_args()
    asyncio.run(seed_postgres(args.config, args.agent))


if __name__ == "__main__":
    main()
