"""Generate flow diagrams for documentation using LangGraph visualization.

This script generates PNG images for the data agent and intent detection flows
using LangGraph's built-in visualization.

Usage:
    uv run python scripts/generate_diagrams.py
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def main():
    """Generate diagrams from LangGraph and save to docs folder."""
    from unittest.mock import MagicMock

    from langchain_openai import AzureChatOpenAI

    from data_agent.config import CONFIG_DIR
    from data_agent.config_loader import ConfigLoader
    from data_agent.graph import DataAgentGraph

    docs_dir = Path(__file__).parent.parent / "docs"
    docs_dir.mkdir(exist_ok=True)

    # Load a config to get a data agent graph
    config = ConfigLoader.load(CONFIG_DIR / "amex.yaml")

    if config.data_agents:
        agent_config = config.data_agents[0]

        # Create LLM
        llm = AzureChatOpenAI(
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o"),
            api_version="2024-08-01-preview",
            temperature=0,
        )

        # Create a mock datasource for diagram generation (we won't execute queries)
        mock_datasource = MagicMock()

        # Build the graph and compile to get visualization
        graph_builder = DataAgentGraph(llm, mock_datasource, agent_config)
        compiled_graph = graph_builder.compile()

        # Generate PNG using LangGraph's visualization
        png_data = compiled_graph.get_graph().draw_mermaid_png()
        output_path = docs_dir / "data_agent_graph.png"
        output_path.write_bytes(png_data)
        print(f"Generated: {output_path}")

    print("Done!")


if __name__ == "__main__":
    main()
