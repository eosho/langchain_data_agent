"""Data Agent with intent detection and multi-agent routing.

This module provides the main entry point for the NL2SQL platform,
with automatic intent detection to route queries to the appropriate data agent.
"""

import contextlib
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Union
from uuid import uuid4

from langchain_community.utilities.sql_database import SQLDatabase
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command, interrupt

from data_agent.adapters import CosmosAdapter, create_sql_database
from data_agent.config import (
    AgentConfig,
    AzureSQLDatasource,
    BigQueryDatasource,
    CosmosDatasource,
    DataAgentConfig,
    DatabricksDatasource,
    PostgresDatasource,
    SynapseDatasource,
)
from data_agent.config_loader import ConfigLoader
from data_agent.graph import create_data_agent
from data_agent.llm import get_llm
from data_agent.models.state import AgentState, InputState, OutputState
from data_agent.utils.callbacks import AgentCallback
from data_agent.utils.message_utils import get_recent_history

if TYPE_CHECKING:
    from langchain_core.runnables import RunnableConfig

logger = logging.getLogger(__name__)

# Type alias for datasources
Datasource = Union[SQLDatabase, CosmosAdapter]


class DataAgentFlow:
    """Multi-agent data flow with intent detection and routing."""

    def __init__(
        self,
        config_path: str | Path | None = None,
        config: AgentConfig | None = None,
        azure_endpoint: str | None = None,
        api_key: str | None = None,
        deployment_name: str | None = None,
        api_version: str = "2024-08-01-preview",
        shared_db: SQLDatabase | None = None,
    ) -> None:
        """Initialize the Data Agent Flow.

        Args:
            config_path: Path to YAML configuration file. Mutually exclusive with config.
            config: Pre-loaded AgentConfig instance. Mutually exclusive with config_path.
            azure_endpoint: Azure OpenAI endpoint URL.
            api_key: Azure OpenAI API key.
            deployment_name: Name of the deployed model.
            api_version: Azure OpenAI API version.
            shared_db: Optional shared SQLDatabase instance for agents.

        Raises:
            ValueError: If neither config_path nor config is provided.
        """
        if config is not None:
            self.config = config
        elif config_path is not None:
            self.config = ConfigLoader.load(config_path)
        else:
            raise ValueError("Either config_path or config must be provided")

        self.datasources: dict[str, Datasource] = {}
        self.data_agents: dict[str, CompiledStateGraph] = {}
        self._agent_descriptions: dict[str, str] = {}
        self._shared_db = shared_db

        self._intent_llm = get_llm(
            provider=self.config.intent_detection.llm_config.provider,
            azure_endpoint=azure_endpoint,
            api_key=api_key,
            deployment_name=self.config.intent_detection.llm_config.model
            or deployment_name,
            api_version=self.config.intent_detection.llm_config.api_version
            or api_version,
            temperature=self.config.intent_detection.llm_config.temperature,
        )

        self._default_llm_settings = {
            "azure_endpoint": azure_endpoint,
            "api_key": api_key,
            "deployment_name": deployment_name,
            "api_version": api_version,
        }

        self._callback = AgentCallback(agent_name="data_agent_flow")

        self._initialize_agents()

        self._graph = self._build_workflow()

    def _initialize_agents(self) -> None:
        """Initialize database connections and data agent graphs from config."""
        for agent_config in self.config.data_agents:
            name = agent_config.name
            ds = agent_config.datasource

            datasource = self._create_datasource(name, ds)
            if datasource:
                self.datasources[name] = datasource
                self._create_agent_graph(name, agent_config)

            self._agent_descriptions[name] = self._build_agent_description(agent_config)

    def _create_datasource(self, name: str, ds: Any) -> Datasource | None:
        """Create the appropriate database connection for a datasource."""
        if ds is None:
            if self._shared_db is not None:
                logger.debug("Agent '%s' using shared SQLDatabase connection.", name)
                return self._shared_db
            logger.warning("Agent '%s' has no datasource configured.", name)
            return None

        match ds:
            case DatabricksDatasource():
                return create_sql_database(
                    "databricks",
                    host=ds.hostname,
                    http_path=ds.path,
                    access_token=ds.access_token,
                    catalog=ds.catalog,
                    schema=ds.db_schema,
                )
            case CosmosDatasource():
                return CosmosAdapter(
                    endpoint=ds.endpoint,
                    database=ds.database,
                    container=ds.container,
                    key=ds.key,
                    connection_string=ds.connection_string,
                    use_aad=ds.use_aad,
                )
            case PostgresDatasource():
                if ds.connection_string:
                    return create_sql_database(
                        "postgres",
                        connection_string=ds.connection_string,
                        schema=ds.db_schema,
                    )
                return create_sql_database(
                    "postgres",
                    host=ds.host,
                    port=ds.port,
                    database=ds.database,
                    username=ds.username,
                    password=ds.password,
                    schema=ds.db_schema,
                )
            case AzureSQLDatasource():
                if ds.connection_string:
                    return create_sql_database(
                        "azure_sql",
                        connection_string=ds.connection_string,
                        schema=ds.db_schema,
                    )
                return create_sql_database(
                    "azure_sql",
                    host=ds.server,
                    database=ds.database,
                    username=ds.username,
                    password=ds.password,
                    use_aad=ds.use_aad,
                    driver=ds.driver,
                    schema=ds.db_schema,
                )
            case SynapseDatasource():
                if ds.connection_string:
                    return create_sql_database(
                        "synapse",
                        connection_string=ds.connection_string,
                        schema=ds.db_schema,
                    )
                return create_sql_database(
                    "synapse",
                    host=ds.server,
                    database=ds.database,
                    username=ds.username,
                    password=ds.password,
                    use_aad=ds.use_aad,
                    driver=ds.driver,
                    schema=ds.db_schema,
                )
            case BigQueryDatasource():
                return create_sql_database(
                    "bigquery",
                    project=ds.project or ds.project_id,
                    dataset=ds.dataset,
                    credentials_path=ds.credentials_path,
                )
            case _:
                logger.warning("Agent '%s' has unknown datasource type.", name)
                return None

    def _create_agent_graph(self, name: str, agent_config: DataAgentConfig) -> None:
        """Create the LangGraph agent for a data agent."""
        llm_cfg = agent_config.llm_config
        agent_llm = get_llm(
            provider=llm_cfg.provider or "azure_openai",
            azure_endpoint=self._default_llm_settings["azure_endpoint"],
            api_key=self._default_llm_settings["api_key"],
            deployment_name=llm_cfg.model
            or self._default_llm_settings["deployment_name"],
            api_version=llm_cfg.api_version
            or self._default_llm_settings["api_version"],
            temperature=llm_cfg.temperature,
        )
        self.data_agents[name] = create_data_agent(
            llm=agent_llm,
            datasource=self.datasources[name],
            config=agent_config,
            max_retries=self.config.max_retries,
        )

    def _build_agent_description(self, agent_config: DataAgentConfig) -> str:
        """Build a description of the agent for intent detection.

        Args:
            agent_config: Data agent configuration.

        Returns:
            Description string for the agent.
        """
        parts = [f"Agent '{agent_config.name}'"]

        if agent_config.description:
            parts.append(f": {agent_config.description}")

        if agent_config.table_schemas:
            tables = [schema.name for schema in agent_config.table_schemas]
            if agent_config.description:
                parts.append(f" Tables: {', '.join(tables)}.")
            else:
                parts.append(f" handles queries about: {', '.join(tables)}.")
                if agent_config.table_schemas[0].description:
                    parts.append(f" {agent_config.table_schemas[0].description}")

        return "".join(parts)

    def _build_workflow(self) -> CompiledStateGraph:
        """Build the intent detection and routing workflow.

        Returns:
            Compiled StateGraph with intent detection and agent routing.
        """
        agent_names = list(self.data_agents.keys())
        agent_descriptions = self._agent_descriptions
        intent_llm = self._intent_llm
        intent_system_prompt = self.config.intent_detection.system_prompt

        def intent_detection_node(state: AgentState) -> dict[str, Any]:
            """Detect user intent and select the appropriate data agent."""
            question = state["question"]

            agent_list = "\n".join(
                [f"- {name}: {desc}" for name, desc in agent_descriptions.items()]
            )

            system_content = intent_system_prompt.format(agent_descriptions=agent_list)

            # Get recent conversation history for multi-turn context
            history = get_recent_history(state.get("messages", []), max_messages=4)

            messages = [
                SystemMessage(content=system_content),
                *history,  # Previous turns help detect "more of the same" patterns
                HumanMessage(content=question),
            ]

            response = intent_llm.invoke(messages)
            content = response.content
            selected_agent = (
                content.strip()
                if isinstance(content, str)
                else str(content[0]).strip() if content else ""
            )

            if selected_agent not in agent_names:
                clarification = interrupt(
                    {
                        "type": "clarification_needed",
                        "message": "I couldn't understand your question. Could you please provide more details or rephrase it?",
                        "original_question": question,
                        "hint": "Try being more specific about what data you're looking for.",
                    }
                )
                clarified_question = (
                    clarification.get("question")
                    if isinstance(clarification, dict)
                    else str(clarification) if clarification else None
                )
                if clarified_question:
                    messages = [
                        SystemMessage(content=system_content),
                        HumanMessage(content=clarified_question),
                    ]
                    response = intent_llm.invoke(messages)
                    content = response.content
                    selected_agent = (
                        content.strip()
                        if isinstance(content, str)
                        else str(content[0]).strip() if content else ""
                    )
                    if selected_agent in agent_names:
                        return {
                            "question": clarified_question,
                            "datasource_name": selected_agent,
                            "error": None,
                            "messages": [
                                HumanMessage(content=clarified_question, name="user"),
                                AIMessage(
                                    content=f"Detected intent: {selected_agent}",
                                    name="intent_detector",
                                ),
                            ],
                        }

                selected_agent = None

            return {
                "datasource_name": selected_agent or "",
                "error": None if selected_agent else "out_of_scope",
                "messages": [
                    HumanMessage(content=question, name="user"),
                    AIMessage(
                        content=f"Detected intent: {selected_agent or 'out_of_scope'}",
                        name="intent_detector",
                    ),
                ],
            }

        def query_rewrite_node(state: AgentState) -> dict[str, Any]:
            """Rewrite the user's question for the selected agent's context."""
            question = state["question"]
            datasource = state.get("datasource_name", "")

            if not datasource or datasource not in agent_descriptions:
                return {}

            agent_desc = agent_descriptions[datasource]

            # Get recent conversation history for context
            history = get_recent_history(state.get("messages", []), max_messages=4)

            # Build conversation context summary for the rewriter
            conversation_context = ""
            if history:
                conversation_context = "\n## Conversation History (for context)\n"
                for msg in history:
                    msg_type = getattr(msg, "type", "unknown")
                    content = getattr(msg, "content", str(msg))[:500]
                    conversation_context += f"- {msg_type}: {content}\n"

            rewrite_prompt = f"""You are a query rewriter. Your job is to rewrite user questions to be more specific and clear for a database query system.

## Target Agent
{agent_desc}

## Conversation Context
{conversation_context}

## Instructions
1. Keep the original intent of the question
2. If this is a follow-up question (e.g., "what's the average?", "show me the same for X", "filter those by Y"), use the conversation history to expand the question with the relevant context
3. For follow-up questions, make the implicit references explicit (e.g., "What's the average?" → "What is the average transaction amount?" if previous query was about transactions)
4. Make the question more specific if needed
5. If the question is already clear and specific, return it unchanged
6. Do NOT add information that wasn't implied by the original question or conversation

## Original Question
{question}

## Rewritten Question
Respond with ONLY the rewritten question, nothing else."""

            messages = [HumanMessage(content=rewrite_prompt)]
            response = intent_llm.invoke(messages)
            content = response.content
            rewritten = (
                content.strip()
                if isinstance(content, str)
                else str(content[0]).strip() if content else question
            )

            return {
                "question": rewritten,
                "rewritten_question": rewritten,
                "messages": [
                    AIMessage(
                        content=f"Rewritten question: {rewritten}",
                        name="query_rewriter",
                    ),
                ],
            }

        def route_to_agent(state: AgentState) -> str:
            """Route to the appropriate data agent or end if out of scope."""
            datasource = state.get("datasource_name", "")
            if not datasource or state.get("error") == "out_of_scope":
                return "out_of_scope"
            return datasource

        def out_of_scope_node(state: AgentState) -> dict[str, Any]:
            """Handle out-of-scope requests."""
            agent_list = "\n".join(
                [f"- {desc}" for desc in agent_descriptions.values()]
            )
            response = (
                "I'm sorry, but I cannot help with that request. "
                "Your question is outside the scope of available data.\n\n"
                f"I can help you with queries related to:\n{agent_list}"
            )
            return {
                "final_response": response,
                "error": "out_of_scope",
                "messages": [
                    AIMessage(content=response, name="out_of_scope"),
                ],
            }

        workflow = StateGraph(
            AgentState,
            input_schema=InputState,
            output_schema=OutputState,
        )

        workflow.add_node("intent_detection", intent_detection_node)
        workflow.add_node("query_rewrite", query_rewrite_node)
        workflow.add_node("out_of_scope", out_of_scope_node)

        for name, agent in self.data_agents.items():
            workflow.add_node(name, agent)

        workflow.add_edge(START, "intent_detection")

        def route_after_intent(state: AgentState) -> str:
            """Route to query_rewrite or out_of_scope after intent detection."""
            datasource = state.get("datasource_name", "")
            if not datasource or state.get("error") == "out_of_scope":
                return "out_of_scope"
            return "query_rewrite"

        workflow.add_conditional_edges(
            "intent_detection",
            route_after_intent,
            path_map=["query_rewrite", "out_of_scope"],
        )

        routing_map: dict[str, str] = {name: name for name in agent_names}

        workflow.add_conditional_edges(
            "query_rewrite",
            route_to_agent,
            path_map=list(routing_map.keys()),
        )

        workflow.add_edge("out_of_scope", END)
        for name in agent_names:
            workflow.add_edge(name, END)

        checkpointer = InMemorySaver()

        return workflow.compile(
            checkpointer=checkpointer,
            name="data_agent_flow",
        )

    async def connect(self) -> None:
        """Connect to all registered datasources.

        Note: SQLDatabase connections are eager (connected on creation).
        This method connects CosmosAdapter instances.

        Raises:
            ConnectionError: If any connection fails.
        """
        for name, datasource in self.datasources.items():
            if isinstance(datasource, CosmosAdapter):
                try:
                    await datasource.connect()
                except Exception as e:
                    raise ConnectionError(f"Failed to connect to {name}: {e}") from e

    async def disconnect(self) -> None:
        """Disconnect from all datasources."""
        for datasource in self.datasources.values():
            if isinstance(datasource, CosmosAdapter):
                with contextlib.suppress(Exception):
                    await datasource.disconnect()

    async def run(
        self,
        question: str | None = None,
        thread_id: str | None = None,
        resume_value: dict[str, Any] | None = None,
    ) -> OutputState | dict[str, Any]:
        """Execute a natural language query with automatic routing.

        The intent detection will automatically route to the appropriate
        data agent based on the question.

        Args:
            question: Natural language question to answer. Required unless resuming.
            thread_id: Thread ID for conversation persistence. If not provided, a UUID will be generated.
                Required when resuming an interrupted execution.
            resume_value: Value to resume an interrupted execution with.
                Pass {"question": "clarified question"} to resume after an interrupt.

        Returns:
            OutputState with generated SQL, results, and response.
            If interrupted, returns dict with __interrupt__ key.

        Raises:
            ValueError: If neither question nor resume_value is provided,
                or if resume_value is provided without thread_id.
        """
        if resume_value:
            if thread_id is None:
                raise ValueError(
                    "thread_id is required when resuming an interrupted execution"
                )
            input_data: InputState | Command = Command(resume=resume_value)
        elif question:
            input_data = {"question": question, "datasource_name": ""}
        else:
            raise ValueError("Either question or resume_value must be provided")

        if thread_id is None:
            thread_id = uuid4().hex

        config: RunnableConfig = {
            "configurable": {"thread_id": thread_id},
            "callbacks": [self._callback],
            "recursion_limit": 50,
        }

        result = await self._graph.ainvoke(input_data, config)

        if "__interrupt__" in result:
            return dict(result)

        return OutputState(
            generated_sql=result.get("generated_sql", ""),
            final_response=result.get("final_response", ""),
            result=result.get("result", {}),
            error=result.get("error"),
            datasource_name=result.get("datasource_name", ""),
            rewritten_question=result.get("rewritten_question", ""),
            messages=result.get("messages", []),
        )

    def get_agent_names(self) -> list[str]:
        """Get list of registered data agent names.

        Returns:
            List of agent names.
        """
        return list(self.data_agents.keys())

    async def health_check(self) -> dict[str, bool]:
        """Check health of all registered datasources.

        Returns:
            Dict mapping datasource names to health status.
        """
        results = {}
        for name, datasource in self.datasources.items():
            try:
                if isinstance(datasource, CosmosAdapter):
                    results[name] = await datasource.health_check()
                else:
                    # SQLDatabase - run a simple query
                    datasource.run("SELECT 1")
                    results[name] = True
            except Exception:
                results[name] = False
        return results

    async def __aenter__(self) -> "DataAgentFlow":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.disconnect()
