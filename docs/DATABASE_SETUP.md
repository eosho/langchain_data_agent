# Database Setup

Setup instructions for each supported database.

## PostgreSQL

1. Create the database:
   ```bash
   createdb contoso_inventory
   ```

2. Run the seed script:
   ```bash
   uv run python scripts/seed_postgres.py
   ```

## Azure SQL Database

1. Create an Azure SQL Database in Azure Portal
2. Configure firewall rules to allow your IP
3. Set environment variables in `.env`:
   ```dotenv
   AZURE_SQL_SERVER=your-server.database.windows.net
   AZURE_SQL_DATABASE=ContosoHR
   AZURE_SQL_USERNAME=sqladmin
   AZURE_SQL_PASSWORD=your-password
   ```
4. Run the seed script:
   ```bash
   uv run python scripts/seed_azure_sql.py
   ```

## Azure Synapse Analytics

1. Create an Azure Synapse workspace in Azure Portal
2. Configure the serverless SQL endpoint
3. Set environment variables in `.env`:
   ```dotenv
   SYNAPSE_SERVER=your-workspace.sql.azuresynapse.net
   SYNAPSE_DATABASE=HotelAnalytics
   SYNAPSE_USERNAME=sqladmin
   SYNAPSE_PASSWORD=your-password
   ```
4. Run the seed script:
   ```bash
   uv run python scripts/seed_synapse.py
   ```

## Azure Cosmos DB

1. Create a Cosmos DB account and database in Azure Portal
2. Set the connection string in `.env`:
   ```dotenv
   COSMOS_ENDPOINT=https://your-account.documents.azure.com:443/
   COSMOS_KEY=your-cosmos-key
   ```
3. Run the seed script:
   ```bash
   uv run python scripts/seed_cosmos.py
   ```

## Databricks

1. Create a SQL Warehouse in your Databricks workspace
2. Generate a Personal Access Token (Settings > Developer > Access tokens)
3. Configure environment variables:
   ```dotenv
   DATABRICKS_HOST=https://your-workspace.azuredatabricks.net
   DATABRICKS_TOKEN=dapi...
   DATABRICKS_PATH=/sql/1.0/warehouses/your-warehouse-id
   DATABRICKS_CATALOG=your_catalog
   DATABRICKS_SCHEMA=your_schema
   ```
4. Run the seed script:
   ```bash
   uv run python scripts/seed_databricks.py
   ```

## Google BigQuery

1. Create a GCP project and enable BigQuery API
2. Create a service account with BigQuery permissions
3. Download the service account JSON key
4. Configure environment variables:
   ```dotenv
   GOOGLE_CLOUD_PROJECT=your-project-id
   BIGQUERY_DATASET=financial_data
   GOOGLE_APPLICATION_CREDENTIALS=./credentials.json
   ```
5. Run the seed script:
   ```bash
   uv run python scripts/seed_bigquery.py
   ```

## Azure AD Authentication

Several datasources support Azure AD authentication using `DefaultAzureCredential`.

### PostgreSQL
```yaml
datasource:
  type: postgres
  host: "myserver.postgres.database.azure.com"
  database: "mydb"
  username: "myuser@myserver"
```

### Azure SQL / Synapse
```yaml
datasource:
  type: azure_sql
  server: "myserver.database.windows.net"
  database: "mydb"
  use_aad: true
```

### Cosmos DB
```yaml
datasource:
  type: cosmos
  endpoint: "https://myaccount.documents.azure.com:443/"
  database: "mydb"
  container: "mycontainer"
  use_aad: true
```

**Note:** For Cosmos DB with Azure AD, assign the appropriate RBAC role:
- `Cosmos DB Built-in Data Reader` - read-only
- `Cosmos DB Built-in Data Contributor` - read/write
