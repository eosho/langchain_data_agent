"""Chainlit UI application for Data Agent."""

import logging
import os
from typing import cast

import chainlit as cl
import pandas as pd
from chainlit.element import Element
from dotenv import load_dotenv

from data_agent.agent import DataAgentFlow
from data_agent.config import CONFIG_DIR
from data_agent.config_loader import ConfigLoader
from data_agent.core.logging import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

load_dotenv()

CONFIGS = {f.stem: f for f in CONFIG_DIR.glob("*.yaml")}

CONFIG_DESCRIPTIONS = {
    "all": "Access all configured agents with automatic query routing.",
    "contoso": "Contoso retail sales database with products, customers, and orders data.",
    "amex": "American Express financial transactions and merchant data.",
    "adventure_works": "Adventure Works sample database with sales and product information.",
}

CONFIG_ICONS = {
    "all": "https://img.icons8.com/fluency/96/data-configuration.png",
    "contoso": "https://img.icons8.com/fluency/96/shop.png",
    "amex": "https://img.icons8.com/color/96/amex.png",
    "adventure_works": "https://img.icons8.com/fluency/96/mountain.png",
}


def get_azure_credentials() -> tuple[str, str, str]:
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
    api_key = os.getenv("AZURE_OPENAI_API_KEY", "")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
    return endpoint, api_key, deployment


@cl.set_chat_profiles
async def chat_profiles(user: cl.User | None = None, thread_id: str | None = None):
    profiles = []

    profiles.append(
        cl.ChatProfile(
            name="All Agents",
            markdown_description=f"**All Agents**\n\n{CONFIG_DESCRIPTIONS.get('all', '')}",
            icon=CONFIG_ICONS.get(
                "all", "https://img.icons8.com/fluency/96/data-configuration.png"
            ),
            default=True,
        )
    )

    for name in sorted(CONFIGS.keys()):
        description = CONFIG_DESCRIPTIONS.get(
            name, f"Query the {name} agent using natural language."
        )
        icon = CONFIG_ICONS.get(name, "https://img.icons8.com/fluency/96/database.png")
        profiles.append(
            cl.ChatProfile(
                name=name.replace("_", " ").title(),
                markdown_description=f"**{name.replace('_', ' ').title()}**\n\n{description}",
                icon=icon,
                default=False,
            )
        )
    return profiles


@cl.on_chat_start
async def on_chat_start():
    chat_profile = cl.user_session.get("chat_profile")
    if not chat_profile:
        chat_profile = "All Agents"

    config_name = chat_profile.lower().replace(" ", "_")

    if config_name == "all_agents":
        try:
            config = ConfigLoader.load_all()
            display_name = "All Agents"
        except Exception as e:
            await cl.Message(content=f"Failed to load configurations: {e}").send()
            return
    else:
        config_path = CONFIGS.get(config_name)
        if not config_path:
            await cl.Message(
                content=f"Configuration '{config_name}' not found. Available: {', '.join(CONFIGS.keys())}"
            ).send()
            return
        try:
            config = ConfigLoader.load(config_path)
            display_name = chat_profile
        except Exception as e:
            await cl.Message(content=f"Failed to load configuration: {e}").send()
            return

    endpoint, api_key, deployment = get_azure_credentials()
    if not endpoint or not api_key:
        await cl.Message(
            content="Missing Azure OpenAI credentials. Please set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY."
        ).send()
        return

    try:
        flow = DataAgentFlow(
            config=config,
            azure_endpoint=endpoint,
            api_key=api_key,
            deployment_name=deployment,
        )
        await flow.connect()

        cl.user_session.set("flow", flow)
        cl.user_session.set("config_name", config_name)
        cl.user_session.set("thread_id", cl.context.session.id)

        agents = flow.get_agent_names()

        await cl.Message(
            content=f"👋 Connected to **{display_name}**!\n\n"
            f"Available data agents: {', '.join(f'`{a}`' for a in agents)}\n\n"
            f"Ask me anything about your data in natural language."
        ).send()

    except Exception as e:
        await cl.Message(content=f"Failed to initialize: {e}").send()


@cl.on_chat_end
async def on_chat_end():
    flow = cl.user_session.get("flow")
    if flow:
        await flow.disconnect()


@cl.on_message
async def on_message(message: cl.Message):
    flow: DataAgentFlow | None = cl.user_session.get("flow")
    if not flow:
        await cl.Message(
            content="No database connection. Please refresh the page to reconnect."
        ).send()
        return

    thread_id = cl.user_session.get("thread_id")

    try:
        async with cl.Step(
            name="Processing query...", type="run", show_input=False
        ) as thinking_step:
            result = await flow.run(message.content, thread_id=thread_id)
            thinking_step.output = "Done"

        logger.info(f"Result type: {type(result)}, Result: {result}")

        if isinstance(result, dict) and "__interrupt__" in result:
            interrupt_data = result.get("__interrupt__", [])
            if interrupt_data:
                interrupt_obj = interrupt_data[0]
                payload = (
                    interrupt_obj.value
                    if hasattr(interrupt_obj, "value")
                    else interrupt_obj
                )
                hint = payload.get("hint", "")
                await cl.Message(
                    content=f"⚠️ I couldn't understand your question. Could you please provide more details?\n\n*Hint: {hint}*"
                ).send()
            return

        if isinstance(result, dict):
            datasource_name = result.get("datasource_name", "") or ""
            generated_sql = result.get("generated_sql", "") or ""
            query_result = result.get("result", {}) or {}
            final_response = result.get("final_response", "") or ""
            error = result.get("error") or None
        else:
            datasource_name = getattr(result, "datasource_name", "") or ""
            generated_sql = getattr(result, "generated_sql", "") or ""
            query_result = getattr(result, "result", {}) or {}
            final_response = getattr(result, "final_response", "") or ""
            error = getattr(result, "error", None)

        logger.info(
            f"Parsed - datasource: {datasource_name}, sql: {bool(generated_sql)}, "
            f"result: {bool(query_result)}, response: {bool(final_response)}, error: {error}"
        )

        if datasource_name:
            async with cl.Step(
                name=f"🔀 Routed to: {datasource_name}", type="run", show_input=False
            ) as route_step:
                route_step.output = f"Query handled by **{datasource_name}** agent"

        if generated_sql:
            async with cl.Step(
                name="📝 Generated SQL", type="tool", show_input=False
            ) as sql_step:
                sql_step.output = f"```sql\n{generated_sql}\n```"

        if query_result:
            if isinstance(query_result, dict):
                rows = query_result.get("rows", [])
                columns = query_result.get("columns", [])
                row_count = query_result.get("row_count") or len(rows) if rows else 0
            else:
                rows = getattr(query_result, "rows", [])
                columns = getattr(query_result, "columns", [])
                row_count = (
                    getattr(query_result, "row_count", None) or len(rows) if rows else 0
                )

            if columns and rows:
                df = pd.DataFrame(rows, columns=columns)
                async with cl.Step(
                    name="📊 Raw Results",
                    type="tool",
                    show_input=False,
                ) as results_step:
                    elements = [cl.Dataframe(data=df, name="Raw Results")]
                    results_step.elements = cast("list[Element]", elements)
                    results_step.output = df.to_markdown(index=False)

        if final_response:
            await cl.Message(content=final_response).send()
        elif error:
            error_msg = str(error)
            if error == "out_of_scope":
                await cl.Message(
                    content="🚫 Your question is outside the scope of available data. Try asking about the data sources listed above."
                ).send()
            else:
                await cl.Message(content=f"Error: {error_msg}").send()
        else:
            await cl.Message(
                content="Query completed but no response was generated. Please try rephrasing your question."
            ).send()

    except Exception as e:
        logger.exception("Error processing message")
        await cl.Message(content=f"An error occurred: {e}").send()


@cl.on_chat_resume
async def on_chat_resume(thread):
    await on_chat_start()


def main() -> None:
    """Run the Chainlit UI application."""
    import subprocess
    import sys
    from pathlib import Path

    app_path = str(Path(__file__).resolve())
    subprocess.run(
        [
            sys.executable,
            "-m",
            "chainlit",
            "run",
            app_path,
            "--host",
            "localhost",
            "--port",
            "8000",
        ],
        check=True,
    )
