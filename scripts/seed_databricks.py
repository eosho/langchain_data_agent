import argparse
import json
import os
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

CONFIG_DIR = Path(__file__).parent.parent / "src" / "data_agent" / "config"


def load_config(config_name: str, agent_name: str | None = None) -> dict:
    """Load Databricks config from YAML file."""
    config_path = CONFIG_DIR / f"{config_name}.yaml"
    if not config_path.exists():
        print(f"Config file not found: {config_path}")
        sys.exit(1)

    with config_path.open(encoding="utf-8") as f:
        config = yaml.safe_load(f)

    for agent in config.get("data_agents", []):
        if agent.get("databricks_config"):
            if agent_name is None or agent.get("name") == agent_name:
                db_config = agent["databricks_config"]
                return {
                    "agent_name": agent.get("name", "unknown"),
                    "hostname": db_config.get("hostname", ""),
                    "http_path": db_config.get("path", ""),
                    "catalog": db_config.get("catalog", "main"),
                    "schema": db_config.get("db_schema", "default"),
                    "token": os.getenv("DATABRICKS_TOKEN", db_config.get("token", "")),
                }

    print(
        f"No databricks_config found in {config_name}.yaml"
        + (f" for agent '{agent_name}'" if agent_name else "")
    )
    sys.exit(1)


def load_data() -> dict:
    """Load sample data from JSON file."""
    data_file = Path(__file__).parent / "data" / "databricks_data.json"
    if not data_file.exists():
        print(f"Data file not found: {data_file}")
        sys.exit(1)

    with Path(data_file).open(encoding="utf-8") as f:
        return json.load(f)


def escape_sql_string(value: str) -> str:
    """Escape single quotes in SQL string values."""
    if value is None:
        return "NULL"
    return value.replace("'", "''")


def generate_databricks_sql(data: dict) -> str:
    """Generate SQL for seeding Databricks sales data."""
    customers = data.get("customers", [])
    orders = data.get("orders", [])

    customers_sql = []
    for c in customers:
        customer_id = escape_sql_string(c["customer_id"])
        name = escape_sql_string(c["name"])
        email = escape_sql_string(c["email"])
        region = escape_sql_string(c["region"])
        customers_sql.append(f"('{customer_id}', '{name}', '{email}', '{region}')")

    orders_sql = []
    for o in orders:
        order_id = escape_sql_string(o["order_id"])
        customer_id = escape_sql_string(o["customer_id"])
        order_date = o["order_date"]
        total_amount = o["total_amount"]
        status = escape_sql_string(o["status"])
        orders_sql.append(
            f"('{order_id}', '{customer_id}', '{order_date}', {total_amount}, '{status}')"
        )

    return f"""-- ============================================================
-- DATABRICKS SALES DATA SEED SCRIPT
-- ============================================================
-- Generated from: scripts/data/databricks_data.json
-- Run this in your Databricks SQL warehouse
--
-- Before running, ensure you're in the correct catalog and schema:
--   USE CATALOG your_catalog;
--   USE SCHEMA your_schema;
-- ============================================================

-- Drop existing tables
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS customers;

-- Create customers table
CREATE TABLE customers (
    customer_id STRING NOT NULL,
    name STRING NOT NULL,
    email STRING NOT NULL,
    region STRING NOT NULL
);

-- Create orders table
CREATE TABLE orders (
    order_id STRING NOT NULL,
    customer_id STRING NOT NULL,
    order_date DATE NOT NULL,
    total_amount DECIMAL(10,2) NOT NULL,
    status STRING NOT NULL
);

-- Insert customers ({len(customers)} records)
INSERT INTO customers (customer_id, name, email, region) VALUES
{",\n".join(customers_sql)};

-- Insert orders ({len(orders)} records)
INSERT INTO orders (order_id, customer_id, order_date, total_amount, status) VALUES
{",\n".join(orders_sql)};

-- ============================================================
-- Verification queries
-- ============================================================

-- Row counts
SELECT 'customers' as table_name, COUNT(*) as row_count FROM customers
UNION ALL
SELECT 'orders' as table_name, COUNT(*) as row_count FROM orders;

-- Orders by status
SELECT status, COUNT(*) as count, SUM(total_amount) as total_revenue
FROM orders
GROUP BY status
ORDER BY count DESC;

-- Top customers by order count
SELECT c.name, c.region, COUNT(o.order_id) as order_count, SUM(o.total_amount) as total_spent
FROM customers c
JOIN orders o ON c.customer_id = o.customer_id
GROUP BY c.customer_id, c.name, c.region
ORDER BY total_spent DESC
LIMIT 10;

-- Revenue by region
SELECT c.region, COUNT(o.order_id) as orders, SUM(o.total_amount) as revenue
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
GROUP BY c.region
ORDER BY revenue DESC;
"""


def seed_databricks(config_name: str, agent_name: str | None = None) -> None:
    """Seed Databricks with sales data directly via SQL connector."""
    config = load_config(config_name, agent_name)

    if not config["hostname"]:
        print("hostname is required in databricks_config")
        sys.exit(1)

    if not config["token"]:
        print("DATABRICKS_TOKEN environment variable is required")
        sys.exit(1)

    if not config["http_path"]:
        print("path (HTTP path) is required in databricks_config")
        sys.exit(1)

    try:
        from databricks import sql as databricks_sql
    except ImportError:
        print(
            "databricks-sql-connector is required. Install with: uv add databricks-sql-connector"
        )
        sys.exit(1)

    print(f"Connecting to {config['hostname']}...")
    print(f"  Catalog: {config['catalog']}, Schema: {config['schema']}")

    data = load_data()
    customers = data.get("customers", [])
    orders = data.get("orders", [])

    try:
        conn = databricks_sql.connect(
            server_hostname=config["hostname"],
            http_path=config["http_path"],
            access_token=config["token"],
            catalog=config["catalog"],
            schema=config["schema"],
        )
        print("Connected to Databricks")
        cursor = conn.cursor()

        # Drop existing tables
        print("Creating schema...")
        cursor.execute("DROP TABLE IF EXISTS orders")
        cursor.execute("DROP TABLE IF EXISTS customers")

        # Create customers table
        cursor.execute(
            """
            CREATE TABLE customers (
                customer_id STRING NOT NULL,
                name STRING NOT NULL,
                email STRING NOT NULL,
                region STRING NOT NULL
            )
        """
        )

        # Create orders table
        cursor.execute(
            """
            CREATE TABLE orders (
                order_id STRING NOT NULL,
                customer_id STRING NOT NULL,
                order_date DATE NOT NULL,
                total_amount DECIMAL(10,2) NOT NULL,
                status STRING NOT NULL
            )
        """
        )
        print("Schema created")

        # Insert customers
        print(f"Inserting {len(customers)} customers...")
        for c in customers:
            cursor.execute(
                "INSERT INTO customers (customer_id, name, email, region) VALUES (?, ?, ?, ?)",
                (c["customer_id"], c["name"], c["email"], c["region"]),
            )
        print(f"Inserted {len(customers)} customers")

        # Insert orders
        print(f"Inserting {len(orders)} orders...")
        for o in orders:
            cursor.execute(
                "INSERT INTO orders (order_id, customer_id, order_date, total_amount, status) VALUES (?, ?, ?, ?, ?)",
                (
                    o["order_id"],
                    o["customer_id"],
                    o["order_date"],
                    o["total_amount"],
                    o["status"],
                ),
            )
        print(f"Inserted {len(orders)} orders")

        # Summary
        cursor.execute("SELECT COUNT(*) FROM customers")
        result = cursor.fetchone()
        customer_count = result[0] if result else 0

        cursor.execute("SELECT COUNT(*) FROM orders")
        result = cursor.fetchone()
        order_count = result[0] if result else 0

        cursor.execute(
            "SELECT status, COUNT(*) as cnt FROM orders GROUP BY status ORDER BY cnt DESC"
        )
        status_counts = cursor.fetchall()

        cursor.execute(
            "SELECT region, COUNT(*) as cnt FROM customers GROUP BY region ORDER BY cnt DESC"
        )
        region_counts = cursor.fetchall()

        print("\nSummary:")
        print(f"  Customers: {customer_count}")
        print(f"  Orders: {order_count}")
        print(f"  By region: {', '.join(f'{r}={c}' for r, c in region_counts)}")
        print(f"  By status: {', '.join(f'{s}={c}' for s, c in status_counts)}")

        cursor.close()
        conn.close()

        print(f"\nDatabricks seeded successfully for agent '{config['agent_name']}'!")

    except Exception as e:
        print(f"Database error: {e}")
        sys.exit(1)


def main() -> None:
    """Entry point."""
    parser = argparse.ArgumentParser(description="Seed Databricks with sales data")
    parser.add_argument(
        "--config",
        "-c",
        default="contoso",
        help="Config file name (without .yaml extension)",
    )
    parser.add_argument(
        "--agent",
        "-a",
        default="contoso_sales",
        help="Agent name within the config (default: first agent with databricks_config)",
    )
    args = parser.parse_args()
    seed_databricks(args.config, args.agent)


if __name__ == "__main__":
    main()
