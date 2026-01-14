# Prompts Module

This module manages system prompts for the Data Agent's LLM interactions. It provides a modular, extensible prompt architecture that supports multiple database dialects and customization through configuration.

## Architecture

```
src/data_agent/prompts/
├── __init__.py      # Public exports
├── builder.py       # Prompt assembly logic
├── defaults.py      # Default prompt templates
└── dialects.py      # Database-specific SQL guidelines
```

## Components

### defaults.py - Core Prompt Templates

Contains the default system prompts used across the agent:

| Prompt | Purpose |
|--------|---------|
| `DEFAULT_INTENT_DETECTION_PROMPT` | Routes user questions to the appropriate data agent |
| `DEFAULT_GENERAL_CHAT_PROMPT` | Handles greetings and capability questions |
| `DEFAULT_SQL_PROMPT` | Guides SQL generation with schema context |
| `DEFAULT_RESPONSE_PROMPT` | Formats query results into natural language |
| `VISUALIZATION_SYSTEM_PROMPT` | Generates matplotlib visualization code |
| `COSMOS_PROMPT_ADDENDUM` | Cosmos DB-specific constraints and best practices |

### dialects.py - Database-Specific Guidelines

Provides SQL dialect guidelines that are automatically appended based on datasource type:

| Dialect | Datasource Types |
|---------|------------------|
| BigQuery | `bigquery` |
| PostgreSQL | `postgres`, `postgresql` |
| Azure SQL / SQL Server | `azure_sql`, `mssql`, `sqlserver` |
| Azure Synapse | `synapse` |
| Databricks | `databricks` |
| Cosmos DB | `cosmos`, `cosmosdb` |

Each dialect includes:
- Syntax conventions (date functions, data types, quoting)
- Aggregation function usage
- String manipulation functions
- Performance best practices

### builder.py - Prompt Assembly

The `build_prompt()` function assembles the final system prompt:

```
┌─────────────────────────────────────┐
│     Date Context (current date)     │
├─────────────────────────────────────┤
│  Base Prompt (custom or default)    │
│  - Schema context                   │
│  - Few-shot examples                │
├─────────────────────────────────────┤
│     Dialect Guidelines              │
│  (based on datasource type)         │
├─────────────────────────────────────┤
│  Cosmos Addendum (if applicable)    │
│  - Partition key constraints        │
└─────────────────────────────────────┘
```

## Usage

### Basic Prompt Building

```python
from data_agent.prompts import build_prompt

# Build a prompt for PostgreSQL
prompt = build_prompt(
    datasource_type="postgres",
    schema_context="Tables: customers (id, name, email), orders (id, customer_id, total)",
    few_shot_examples="Q: How many customers?\nA: SELECT COUNT(*) FROM customers",
)
```

### Custom Prompts via Configuration

Teams can override default prompts in their agent YAML configuration using `system_prompt` and `response_prompt`:

```yaml
data_agents:
  - name: my_agent
    description: E-commerce sales database
    datasource:
      type: postgres
      # ...
    system_prompt: |
      You are a SQL expert for our e-commerce database.
      Focus on sales metrics and customer behavior.

      {schema_context}

      {few_shot_examples}
    response_prompt: |
      Provide insights focused on business impact.
      Always mention revenue implications.
    table_schemas:
      # ...
```

### Getting Dialect Guidelines

```python
from data_agent.prompts import get_dialect_guidelines

# Get BigQuery-specific SQL guidelines
guidelines = get_dialect_guidelines("bigquery")
```

## Prompt Template Variables

The following variables are automatically substituted:

| Variable | Description | Used In |
|----------|-------------|---------|
| `{schema_context}` | Database schema information | SQL prompt |
| `{few_shot_examples}` | Example Q&A pairs | SQL prompt |
| `{agent_descriptions}` | Available data agents | Intent detection, general chat |
| `{partition_key}` | Cosmos DB partition key | Cosmos addendum |

## Extending

### Adding a New Dialect

1. Add guidelines constant to `dialects.py`:

```python
MY_DATABASE_GUIDELINES = """## My Database SQL Guidelines

1. **Syntax conventions:**
   - Use MY_DATE_FUNC() for date operations
   - ...
"""
```

2. Register in `DIALECT_GUIDELINES_MAP`:

```python
DIALECT_GUIDELINES_MAP: dict[str, str] = {
    # ... existing entries
    "mydatabase": MY_DATABASE_GUIDELINES,
}
```

### Adding a New Prompt Type

1. Add the template to `defaults.py`:

```python
MY_NEW_PROMPT = """You are a specialized assistant for...

{custom_variable}
"""
```

2. Export in `__init__.py`:

```python
from data_agent.prompts.defaults import MY_NEW_PROMPT

__all__ = [
    # ... existing exports
    "MY_NEW_PROMPT",
]
```
