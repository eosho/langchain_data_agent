import argparse
import json
import os
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv
from google.cloud import bigquery

load_dotenv()

CONFIG_DIR = Path(__file__).parent.parent / "src" / "data_agent" / "config"


def load_config(config_name: str, agent_name: str | None = None) -> dict:
    """Load BigQuery config from YAML file."""
    config_path = CONFIG_DIR / f"{config_name}.yaml"
    if not config_path.exists():
        print(f"Config file not found: {config_path}")
        sys.exit(1)

    with config_path.open(encoding="utf-8") as f:
        config = yaml.safe_load(f)

    for agent in config.get("data_agents", []):
        if agent.get("bigquery_config"):
            if agent_name is None or agent.get("name") == agent_name:
                bq_config = agent["bigquery_config"]
                return {
                    "agent_name": agent.get("name", "unknown"),
                    "project_id": os.getenv(
                        "GOOGLE_CLOUD_PROJECT", bq_config.get("project_id", "")
                    ),
                    "dataset": os.getenv(
                        "BIGQUERY_DATASET", bq_config.get("dataset", "financial_data")
                    ),
                    "location": bq_config.get("location", "US"),
                }

    print(
        f"No bigquery_config found in {config_name}.yaml"
        + (f" for agent '{agent_name}'" if agent_name else "")
    )
    sys.exit(1)


SCHEMA_SQL = """
CREATE OR REPLACE TABLE `{project}.{dataset}.customers` (
    customer_id STRING NOT NULL,
    first_name STRING NOT NULL,
    last_name STRING NOT NULL,
    email STRING NOT NULL,
    phone STRING,
    date_of_birth DATE,
    registration_date DATE NOT NULL,
    customer_segment STRING NOT NULL,  -- 'Standard', 'Premium', 'VIP'
    risk_score FLOAT64,
    is_active BOOL DEFAULT TRUE
);

CREATE OR REPLACE TABLE `{project}.{dataset}.accounts` (
    account_id STRING NOT NULL,
    customer_id STRING NOT NULL,
    account_type STRING NOT NULL,  -- 'Checking', 'Savings', 'Credit', 'Investment'
    account_status STRING NOT NULL,  -- 'Active', 'Frozen', 'Closed'
    opened_date DATE NOT NULL,
    currency STRING DEFAULT 'USD',
    current_balance NUMERIC NOT NULL,
    credit_limit NUMERIC,
    interest_rate FLOAT64
);

CREATE OR REPLACE TABLE `{project}.{dataset}.transactions` (
    transaction_id STRING NOT NULL,
    account_id STRING NOT NULL,
    transaction_timestamp TIMESTAMP NOT NULL,
    transaction_date DATE NOT NULL,
    transaction_type STRING NOT NULL,  -- 'Deposit', 'Withdrawal', 'Transfer', 'Payment', 'Refund'
    amount NUMERIC NOT NULL,
    currency STRING DEFAULT 'USD',
    merchant_name STRING,
    merchant_category STRING,
    channel STRING NOT NULL,  -- 'ATM', 'Online', 'Mobile', 'Branch', 'POS'
    status STRING NOT NULL,  -- 'Completed', 'Pending', 'Failed', 'Reversed'
    reference_id STRING,
    description STRING
);

CREATE OR REPLACE TABLE `{project}.{dataset}.fraud_alerts` (
    alert_id STRING NOT NULL,
    transaction_id STRING NOT NULL,
    alert_timestamp TIMESTAMP NOT NULL,
    alert_type STRING NOT NULL,  -- 'Suspicious Amount', 'Unusual Location', 'Velocity', 'Pattern'
    severity STRING NOT NULL,  -- 'Low', 'Medium', 'High', 'Critical'
    status STRING NOT NULL,  -- 'Open', 'Investigating', 'Confirmed Fraud', 'False Positive', 'Resolved'
    risk_score FLOAT64 NOT NULL,
    notes STRING
);

CREATE OR REPLACE TABLE `{project}.{dataset}.monthly_summaries` (
    summary_id STRING NOT NULL,
    account_id STRING NOT NULL,
    year_month STRING NOT NULL,  -- 'YYYY-MM' format
    opening_balance NUMERIC NOT NULL,
    closing_balance NUMERIC NOT NULL,
    total_deposits NUMERIC DEFAULT 0,
    total_withdrawals NUMERIC DEFAULT 0,
    transaction_count INT64 DEFAULT 0,
    avg_transaction_amount NUMERIC,
    largest_transaction NUMERIC
);
"""


def load_data() -> dict:
    """Load sample data from JSON file."""
    data_file = Path(__file__).parent / "data" / "bigquery_data.json"
    if not data_file.exists():
        print(f"Data file not found: {data_file}")
        sys.exit(1)

    with Path(data_file).open(encoding="utf-8") as f:
        return json.load(f)


def create_dataset(client: bigquery.Client, config: dict) -> None:
    """Create the dataset if it doesn't exist."""
    dataset_ref = f"{config['project_id']}.{config['dataset']}"
    dataset = bigquery.Dataset(dataset_ref)
    dataset.location = config["location"]

    try:
        client.create_dataset(dataset, exists_ok=True)
        print(f"Dataset '{config['dataset']}' ready")
    except Exception as e:
        print(f"Failed to create dataset: {e}")
        raise


def create_tables(client: bigquery.Client, config: dict) -> None:
    """Create all tables using DDL statements."""
    sql = SCHEMA_SQL.format(project=config["project_id"], dataset=config["dataset"])

    statements = [s.strip() for s in sql.split(";") if s.strip() and "CREATE" in s]

    for stmt in statements:
        try:
            query_job = client.query(stmt + ";")
            query_job.result()
            if "`" in stmt:
                full_ref = stmt.split("`")[1]
                table_name = full_ref.split(".")[-1]
                print(f"  Created table: {table_name}")
        except Exception as e:
            print(f"Failed to create table: {e}")
            raise


def load_data_to_table(
    client: bigquery.Client, config: dict, table_name: str, data: list[dict]
) -> None:
    """Load data to table using batch load (works on free tier).

    Uses load_table_from_json which is a batch load operation,
    unlike insert_rows_json which uses streaming insert (not allowed on free tier).
    """
    import io

    table_id = f"{config['project_id']}.{config['dataset']}.{table_name}"

    json_data = "\n".join(json.dumps(row) for row in data)
    json_file = io.BytesIO(json_data.encode("utf-8"))

    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
    )

    # Load data
    load_job = client.load_table_from_file(
        json_file,
        table_id,
        job_config=job_config,
    )

    # Wait for the job to complete
    load_job.result()

    # Get loaded row count
    table = client.get_table(table_id)
    print(f"  Loaded {table.num_rows} rows into {table_name}")


def seed_bigquery(config_name: str, agent_name: str | None = None) -> None:
    """Main entry point for seeding BigQuery."""
    config = load_config(config_name, agent_name)

    if not config["project_id"]:
        print(
            "project_id is required in bigquery_config (or set GOOGLE_CLOUD_PROJECT env var)"
        )
        sys.exit(1)

    print(f"Connecting to BigQuery project '{config['project_id']}'...")
    print(f"  Dataset: {config['dataset']}, Location: {config['location']}")

    client = bigquery.Client(project=config["project_id"])
    print("Connected to BigQuery")

    # Create dataset and tables
    print("Creating dataset...")
    create_dataset(client, config)

    print("Creating tables...")
    create_tables(client, config)

    # Load and insert data
    data = load_data()

    print("Loading data...")
    load_data_to_table(client, config, "customers", data["customers"])
    load_data_to_table(client, config, "accounts", data["accounts"])
    load_data_to_table(client, config, "transactions", data["transactions"])
    load_data_to_table(client, config, "fraud_alerts", data["fraud_alerts"])
    load_data_to_table(client, config, "monthly_summaries", data["monthly_summaries"])

    print(f"\nBigQuery seeded successfully for agent '{config['agent_name']}'!")


def main() -> None:
    """Entry point."""
    parser = argparse.ArgumentParser(
        description="Seed BigQuery with financial transactions data"
    )
    parser.add_argument(
        "--config",
        "-c",
        default="amex",
        help="Config file name (without .yaml extension)",
    )
    parser.add_argument(
        "--agent",
        "-a",
        default="financial_transactions",
        help="Agent name within the config (default: first agent with bigquery_config)",
    )
    args = parser.parse_args()
    seed_bigquery(args.config, args.agent)


if __name__ == "__main__":
    main()
