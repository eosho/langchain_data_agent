# A2A Protocol Support

The Data Agent supports the [Agent-to-Agent (A2A) protocol](https://github.com/google/A2A), enabling interoperability with other A2A-compliant agents.

## Quick Start

```bash
# Start the A2A server with all configs (default)
uv run data-agent a2a

# Start with a specific config
uv run data-agent a2a --config contoso

# Agent card available at:
# http://localhost:8001/.well-known/agent-card.json
```

## Server Options

| Option | Default | Description |
|--------|---------|-------------|
| `--config, -c` | all | Configuration name (e.g., `contoso`). Loads all configs if not specified. |
| `--port, -p` | 8001 | Server port |
| `--host` | localhost | Bind host |
| `--log-level` | info | Logging level |

## Agent Card

The server exposes an agent card at `/.well-known/agent-card.json` describing:

- Agent capabilities (streaming, state history)
- Available skills (one per configured datasource)
- Supported input/output modes

## Python Client Example

When the server is started with all configs (default), the agent can route queries to any configured datasource based on the question's intent.

```python
import asyncio
from uuid import uuid4
import httpx
from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
from a2a.types import Message, Part, Role, TextPart

async def query_agent():
    async with httpx.AsyncClient(timeout=120.0) as http:
        # Fetch agent card
        resolver = A2ACardResolver(httpx_client=http, base_url="http://localhost:8001")
        card = await resolver.get_agent_card()

        # Show available skills (one per datasource)
        print("Available datasources:")
        for skill in card.skills:
            print(f"  - {skill.id}: {skill.description}")

        # Create client
        client = ClientFactory(ClientConfig(httpx_client=http)).create(card=card)

        # Query different datasources - the agent routes automatically
        questions = [
            # Your questions
        ]

        for question in questions:
            print(f"\n> {question}")
            message = Message(
                role=Role.user,
                parts=[Part(root=TextPart(text=question))],
                message_id=uuid4().hex,
            )

            async for event in client.send_message(message):
                if isinstance(event, Message):
                    for part in event.parts:
                        if hasattr(part, "root") and hasattr(part.root, "text"):
                            print(part.root.text)
                else:
                    task, _ = event
                    if task.status.state == "completed" and task.artifacts:
                        for artifact in task.artifacts:
                            for part in artifact.parts:
                                if hasattr(part, "root") and hasattr(part.root, "text"):
                                    print(part.root.text)

asyncio.run(query_agent())
```

## Testing

```bash
# Run test client against running server
uv run python tests/test_a2a.py
```
