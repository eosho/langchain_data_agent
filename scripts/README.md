# Scripts

Seed scripts for populating sample data into various databases.

## Seed Scripts

| Script | Database | Description |
|--------|----------|-------------|
| `seed_databricks.py` | Databricks | Sales data (customers, orders) |
| `seed_cosmos.py` | Azure Cosmos DB | Product catalog |
| `seed_postgres.py` | PostgreSQL | Inventory data (warehouses, inventory, shipments) |
| `seed_azure_sql.py` | Azure SQL | HR data (departments, employees, reviews, time off) |
| `seed_synapse.py` | Azure Synapse | Hotel analytics (reservations, guests, rooms) |
| `seed_bigquery.py` | Google BigQuery | Financial transactions (accounts, transactions, fraud alerts) |

## Usage

1. **Configure environment variables** in `.env` (see `.env.example`)

2. **Run a seed script**

   ```bash
   uv run python scripts/seed_databricks.py
   ```

## Data Files

Sample data is stored in `scripts/data/` as JSON files:

| File | Contents |
|------|----------|
| `databricks_data.json` | Customers and orders |
| `cosmos_data.json` | Product catalog |
| `postgres_data.json` | Warehouses, inventory, shipments |
| `azure_sql_data.json` | HR data |
| `synapse_data.json` | Hotel reservations |
| `bigquery_data.json` | Financial transactions |

## Environment Variables

All configuration can come from either YAML files in `src/data_agent/config/` or environment variables. **Environment variables take precedence over YAML values.**

You can configure everything in `.env` without using YAML config files if preferred.

### Databricks

| Variable | Description |
|----------|-------------|
| `DATABRICKS_HOSTNAME` | Workspace hostname (e.g., `workspace.azuredatabricks.net`) |
| `DATABRICKS_HTTP_PATH` | SQL warehouse HTTP path |
| `DATABRICKS_CATALOG` | Unity Catalog name |
| `DATABRICKS_SCHEMA` | Database schema name |
| `DATABRICKS_TOKEN` | **Required** - Personal access token |

### Azure SQL Database

| Variable | Description |
|----------|-------------|
| `AZURE_SQL_CONNECTION_STRING` | Full connection string (takes precedence) |
| `AZURE_SQL_SERVER` | Server hostname |
| `AZURE_SQL_DATABASE` | Database name |
| `AZURE_SQL_USERNAME` | Username |
| `AZURE_SQL_PASSWORD` | Password (required if `use_aad: false` and no connection string) |
| `AZURE_SQL_USE_AAD` | `true` or `false` - Use Azure AD authentication |
| `AZURE_SQL_DRIVER` | ODBC driver name |

### Azure Synapse Analytics

| Variable | Description |
|----------|-------------|
| `SYNAPSE_CONNECTION_STRING` | Full connection string (takes precedence) |
| `SYNAPSE_SERVER` | Synapse SQL endpoint |
| `SYNAPSE_DATABASE` | Database name |
| `SYNAPSE_USERNAME` | Username |
| `SYNAPSE_PASSWORD` | Password (required if `use_aad: false` and no connection string) |
| `SYNAPSE_USE_AAD` | `true` or `false` - Use Azure AD authentication |
| `SYNAPSE_DRIVER` | ODBC driver name |
| `SYNAPSE_POOL` | Pool name (default: `Built-in`) |

### Azure Cosmos DB

| Variable | Description |
|----------|-------------|
| `COSMOS_CONNECTION_STRING` | Full connection string (takes precedence) |
| `COSMOS_ENDPOINT` | Account endpoint URL |
| `COSMOS_DATABASE` | Database name |
| `COSMOS_CONTAINER` | Container name |
| `COSMOS_KEY` | Account key (required if `use_aad: false` and no connection string) |
| `COSMOS_USE_AAD` | `true` or `false` - Use Azure AD authentication |

### PostgreSQL

| Variable | Description |
|----------|-------------|
| `POSTGRES_CONNECTION_STRING` | Full connection string (takes precedence) |
| `POSTGRES_HOST` | Database host |
| `POSTGRES_PORT` | Database port (default: `5432`) |
| `POSTGRES_DATABASE` | Database name |
| `POSTGRES_USERNAME` | Username |
| `POSTGRES_PASSWORD` | Password (required if no connection string and not using AAD) |
| `POSTGRES_SCHEMA` | Schema name (default: `public`) |
| `POSTGRES_USE_AAD` | `true` or `false` - Use Azure AD authentication |

### Google BigQuery

| Variable | Description |
|----------|-------------|
| `GOOGLE_CLOUD_PROJECT` | GCP project ID |
| `BIGQUERY_DATASET` | BigQuery dataset name |
| `BIGQUERY_LOCATION` | Dataset location (default: `US`) |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to service account JSON file |
| `BIGQUERY_CREDENTIALS_JSON` | Service account JSON as string |
