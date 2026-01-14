"""LLM provider implementations.

This module contains concrete provider implementations for different
LLM services like Azure OpenAI.
"""

from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_openai import AzureChatOpenAI

from data_agent.llm.base import BaseProvider


class AzureOpenAIProvider(BaseProvider):
    """Azure OpenAI LLM provider.

    Attributes:
        name: Provider identifier ('azure_openai').
    """

    name = "azure_openai"

    def create_llm(self, **kwargs: Any) -> BaseChatModel:
        """Create an Azure OpenAI chat model.

        Args:
            azure_endpoint: Azure OpenAI endpoint URL.
            api_key: Azure OpenAI API key.
            deployment_name: Name of the deployed model.
            api_version: API version (default: '2024-08-01-preview').
            temperature: Sampling temperature (default: 0).
            **kwargs: Additional AzureChatOpenAI parameters.

        Returns:
            Configured AzureChatOpenAI instance.
        """
        # Build kwargs dict, only including non-None values to allow env var fallback
        llm_kwargs: dict[str, Any] = {
            "api_version": kwargs.get("api_version", "2024-08-01-preview"),
            "temperature": kwargs.get("temperature", 0),
        }

        if kwargs.get("azure_endpoint"):
            llm_kwargs["azure_endpoint"] = kwargs["azure_endpoint"]
        if kwargs.get("api_key"):
            llm_kwargs["api_key"] = kwargs["api_key"]
        if kwargs.get("deployment_name"):
            llm_kwargs["azure_deployment"] = kwargs["deployment_name"]

        return AzureChatOpenAI(**llm_kwargs)
