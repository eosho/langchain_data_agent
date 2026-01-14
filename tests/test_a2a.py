"""Test client for the A2A Data Agent server.

Run the A2A server first:
    uv run data-agent a2a --config contoso --port 8001

Then run this script:
    uv run python tests/test_a2a.py
"""

import asyncio
import logging
from uuid import uuid4

import httpx
from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
from a2a.types import (
  AgentCard,
  Message,
  Part,
  Role,
  TextPart,
)
from a2a.utils.constants import (
  AGENT_CARD_WELL_KNOWN_PATH,
  EXTENDED_AGENT_CARD_PATH,
)

logger = logging.getLogger(__name__)


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    base_url = "http://localhost:8001"

    async with httpx.AsyncClient(timeout=120.0) as httpx_client:
        resolver = A2ACardResolver(
            httpx_client=httpx_client,
            base_url=base_url,
        )

        final_agent_card_to_use: AgentCard | None = None

        try:
            logger.info(
                f"Attempting to fetch public agent card from: {base_url}{AGENT_CARD_WELL_KNOWN_PATH}"
            )
            _public_card = await resolver.get_agent_card()
            logger.info("Successfully fetched public agent card:")
            logger.info(_public_card.model_dump_json(indent=2, exclude_none=True))
            final_agent_card_to_use = _public_card
            logger.info("\nUsing PUBLIC agent card for client initialization.")

            if _public_card.supports_authenticated_extended_card:
                try:
                    logger.info(
                        "\nPublic card supports authenticated extended card. "
                        f"Attempting to fetch from: {base_url}{EXTENDED_AGENT_CARD_PATH}"
                    )
                    auth_headers_dict = {
                        "Authorization": "Bearer dummy-token-for-extended-card"
                    }
                    _extended_card = await resolver.get_agent_card(
                        relative_card_path=EXTENDED_AGENT_CARD_PATH,
                        http_kwargs={"headers": auth_headers_dict},
                    )
                    logger.info(
                        "Successfully fetched authenticated extended agent card:"
                    )
                    logger.info(
                        _extended_card.model_dump_json(indent=2, exclude_none=True)
                    )
                    final_agent_card_to_use = _extended_card
                    logger.info(
                        "\nUsing AUTHENTICATED EXTENDED agent card for client initialization."
                    )
                except Exception as e_extended:
                    logger.warning(
                        f"Failed to fetch extended agent card: {e_extended}. "
                        "Will proceed with public card.",
                        exc_info=True,
                    )
            else:
                logger.info(
                    "\nPublic card does not indicate support for an extended card. Using public card."
                )

        except Exception as e:
            logger.error(
                f"Critical error fetching public agent card: {e}", exc_info=True
            )
            raise RuntimeError(
                "Failed to fetch the public agent card. Cannot continue."
            ) from e

        config = ClientConfig(httpx_client=httpx_client)
        factory = ClientFactory(config)
        client = factory.create(card=final_agent_card_to_use)
        logger.info("A2A Client initialized via ClientFactory.")

        logger.info("Test 1: Simple Query")

        message = Message(
            role=Role.user,
            parts=[Part(root=TextPart(text="Find all products with low inventory"))],
            message_id=uuid4().hex,
        )

        async for event in client.send_message(message):
            if isinstance(event, Message):
                logger.info("Response message:")
                logger.info(event.model_dump(mode="json", exclude_none=True))
            else:
                task, task_event = event
                logger.info(
                    f"Task state: {task.status.state if task.status else 'unknown'}"
                )
                if task_event:
                    logger.info(
                        f"Event: {task_event.model_dump(mode='json', exclude_none=True)}"
                    )

        logger.info("Test 2: Multi-turn Conversation")

        message2 = Message(
            role=Role.user,
            parts=[Part(root=TextPart(text="How many shipments are in transit?"))],
            message_id=uuid4().hex,
        )

        logger.info("First response:")
        async for event in client.send_message(message2):
            if isinstance(event, Message):
                logger.info("Response message:")
                logger.info(event.model_dump(mode="json", exclude_none=True))
            else:
                task, task_event = event
                logger.info(
                    f"Task state: {task.status.state if task.status else 'unknown'}"
                )
                if task_event:
                    logger.info(
                        f"Event: {task_event.model_dump(mode='json', exclude_none=True)}"
                    )


if __name__ == "__main__":
    asyncio.run(main())
