# Configuration

Data agents are configured via YAML files. See `src/data_agent/agents/contoso.yaml` for a complete example.

## Data Agent Definition

```yaml
data_agents:
  - name: "my_postgres_agent"
    description: "Agent for querying user data"
    datasource:
      type: postgres
      host: "localhost"
      port: 5432
      database: "mydb"
      username: "user"
    llm:
      model: gpt-4o
      temperature: 0.0
    validation:
      max_rows: 5000
      blocked_functions:
        - pg_sleep
        - pg_read_file
    system_prompt: |
      You are an SQL assistant...
      {schema_context}
      {few_shot_examples}
    response_prompt: |
      Given the results, provide a natural language response...
    table_schemas:
      - table_name: "users"
        table_description: "User accounts"
        columns:
          - column_name: "id"
            data_type: "INTEGER"
            description: "Primary key"
    few_shot_examples:
      - question: "How many users are there?"
        sql_query: "SELECT COUNT(*) FROM users"
        answer: "There are 1,234 users."
```

## Code Interpreter (Data Visualization)

The data agent can generate charts and visualizations from query results. When the LLM detects visualization intent (e.g., "show me a chart", "visualize", "plot"), it generates matplotlib code to create charts.

Visualization is **automatically enabled** - no YAML configuration needed. The executor is selected based on environment:

| Environment | Executor | Use Case |
|-------------|----------|----------|
| `AZURE_SESSIONS_POOL_ENDPOINT` set | Azure Sessions | Production (secure, Hyper-V isolation) |
| Not set | Local executor | Development (no sandboxing) |

```bash
# Production: Set the Azure Sessions endpoint
export AZURE_SESSIONS_POOL_ENDPOINT="https://eastus.dynamicsessions.io/subscriptions/.../sessionPools/..."
```

See [VISUALIZATION.md](VISUALIZATION.md) for Azure setup instructions and troubleshooting.

## SQL Validation

Each data agent can configure SQL validation settings to control query safety:

```yaml
validation:
  max_rows: 5000           # Maximum rows in query results (enforced via LIMIT)
  blocked_functions:       # Additional SQL functions to block
    - session_user         # BigQuery: returns user email
    - external_query       # BigQuery: federated query access
```

| Setting | Description | Default |
|---------|-------------|---------|
| `max_rows` | Maximum rows allowed in query results. Queries without LIMIT will have one added; queries with LIMIT > max_rows will be capped. | 10000 |
| `blocked_functions` | Additional SQL functions to block beyond the built-in dangerous functions list. | [] |

### Built-in Blocked Functions

The validator automatically blocks dangerous functions that can be used for SQL injection attacks.
See [OWASP SQL Injection Prevention](https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html) for background.

| Database | Blocked Functions |
|----------|------------------|
| **PostgreSQL** | `pg_sleep`, `pg_read_file`, `pg_read_binary_file`, `pg_ls_dir`, `pg_stat_file`, `lo_import`, `lo_export` |
| **MySQL** | `sleep`, `benchmark`, `load_file`, `into_outfile`, `into_dumpfile` |
| **SQL Server** | `xp_cmdshell`, `xp_fileexist`, `xp_dirtree`, `xp_regread`, `xp_regwrite`, `sp_oacreate`, `sp_oamethod`, `openrowset`, `opendatasource`, `bulk`, `waitfor` |
| **General** | `exec`, `execute`, `system`, `shell`, `reflect`, `java_method` |

Use `blocked_functions` to add domain-specific restrictions (e.g., blocking `external_query` for BigQuery federated access).

## Shared Database Connection

Pass a pre-configured `SQLDatabase` connection for agents without database config:

```python
from langchain_community.utilities.sql_database import SQLDatabase
from data_agent import DataAgentFlow

shared_db = SQLDatabase.from_uri("postgresql+psycopg://user:pass@localhost/mydb")

async with DataAgentFlow(
    config_path="config.yaml",
    azure_endpoint="...",
    api_key="...",
    deployment_name="gpt-4o",
    shared_db=shared_db,
) as flow:
    result = await flow.query("Show me all records")
```

YAML config for shared database (no database config needed):

```yaml
data_agents:
  - name: "inventory"
    llm:
      model: gpt-4o
      temperature: 0.0
    system_prompt: |
      You are a SQL expert.
      {schema_context}
    table_schemas:
      - table_name: "products"
        columns:
          - column_name: "id"
            data_type: "INTEGER"
```

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| **Azure OpenAI** | | |
| `AZURE_OPENAI_ENDPOINT` | Endpoint URL | Yes |
| `AZURE_OPENAI_API_KEY` | API key | Yes |
| `AZURE_OPENAI_DEPLOYMENT` | Model deployment | No (default: gpt-4o) |
| **PostgreSQL** | | |
| `POSTGRES_HOST` | Host | If using |
| `POSTGRES_PORT` | Port | If using |
| `POSTGRES_DATABASE` | Database | If using |
| `POSTGRES_USER` | Username | If using |
| `POSTGRES_PASSWORD` | Password | If using |
| **Azure SQL** | | |
| `AZURE_SQL_SERVER` | Server | If using |
| `AZURE_SQL_DATABASE` | Database | If using |
| `AZURE_SQL_USERNAME` | Username | If using |
| `AZURE_SQL_PASSWORD` | Password | If using |
| **Azure Synapse** | | |
| `SYNAPSE_SERVER` | Server | If using |
| `SYNAPSE_DATABASE` | Database | If using |
| `SYNAPSE_USERNAME` | Username | If using |
| `SYNAPSE_PASSWORD` | Password | If using |
| **Cosmos DB** | | |
| `COSMOS_ENDPOINT` | Endpoint | If using |
| `COSMOS_KEY` | Key | If using |
| `COSMOS_CONNECTION_STRING` | Connection string | If using |
| **Databricks** | | |
| `DATABRICKS_HOST` | Workspace URL | If using |
| `DATABRICKS_TOKEN` | PAT | If using |
| `DATABRICKS_PATH` | Warehouse path | If using |
| `DATABRICKS_CATALOG` | Catalog | If using |
| `DATABRICKS_SCHEMA` | Schema | If using |
| **BigQuery** | | |
| `GOOGLE_CLOUD_PROJECT` | Project ID | If using |
| `BIGQUERY_DATASET` | Dataset | If using |
| `GOOGLE_APPLICATION_CREDENTIALS` | Credentials path | If using |

### Environment Variable Precedence

Environment variables **override** YAML configuration values. The merge logic works as follows:

1. YAML values are loaded first as the base configuration
2. Environment variables are checked via Pydantic's `BaseSettings`
3. Any env var that differs from the field's default value will override the YAML value

**Important behaviors to understand:**

- **Empty strings count as values**: Setting `SYNAPSE_USERNAME=` (empty) in `.env` will override any username in YAML with an empty string. This is useful for Azure AD authentication where you want `use_aad: true` without SQL credentials.

- **Shell environment takes precedence over `.env` files**: If you've previously exported environment variables in your shell session, they will persist even after updating your `.env` file. To pick up `.env` changes:
  - Close and reopen your terminal, or
  - Manually unset/update the variables: `$env:SYNAPSE_DATABASE = "pool"` (PowerShell)

- **Env vars only augment declared configs**: Environment variables are only applied to datasources that are explicitly declared in YAML. They won't create new datasource configurations on their own.

**Example: Azure AD Authentication**

To use Azure AD authentication for Azure SQL or Synapse, set empty credentials in `.env`:

```bash
# .env
AZURE_SQL_SERVER=myserver.database.windows.net
AZURE_SQL_DATABASE=mydb
AZURE_SQL_USERNAME=
AZURE_SQL_PASSWORD=
```

Then in YAML:
```yaml
datasource:
  type: azure_sql
  use_aad: true
```

The empty username/password from `.env` won't interfere with AAD auth since `use_aad: true` takes precedence in the connection logic.

**Troubleshooting: Stale Environment Variables**

If you update `.env` but changes don't take effect:

```powershell
# Check current values
$env:SYNAPSE_DATABASE

# If stale, manually update or restart terminal
$env:SYNAPSE_DATABASE = "pool"
$env:SYNAPSE_USERNAME = ""
$env:SYNAPSE_PASSWORD = ""
```
