"""Base LLM factory and provider abstractions.

This module provides the factory pattern for creating LLM instances,
allowing easy swapping between different providers.
"""

from abc import ABC, abstractmethod
from typing import Any

from langchain_core.language_models import BaseChatModel


class BaseProvider(ABC):
    """Abstract base class for LLM providers.

    Attributes:
        name: Unique provider identifier.
    """

    name: str

    @abstractmethod
    def create_llm(self, **kwargs: Any) -> BaseChatModel:
        """Create an LLM instance with the given configuration.

        Args:
            **kwargs: Provider-specific configuration options.

        Returns:
            Configured BaseChatModel instance.
        """
        ...


class LLMFactory:
    """Factory for creating LLM instances from registered providers.

    Attributes:
        providers: Registered provider instances by name.

    Example:
        ```python
        factory = LLMFactory()
        factory.register_provider(AzureOpenAIProvider())

        llm = factory.create_llm(
            provider="azure_openai",
            azure_endpoint="https://xxx.openai.azure.com/",
            api_key="your-key",
            deployment_name="gpt-4",
        )
        ```
    """

    def __init__(self) -> None:
        """Initialize the factory with an empty provider registry."""
        self.providers: dict[str, BaseProvider] = {}

    def register_provider(self, provider: BaseProvider) -> None:
        """Register an LLM provider.

        Args:
            provider: Provider instance to register.
        """
        self.providers[provider.name] = provider

    def get_provider(self, name: str) -> BaseProvider:
        """Get a registered provider by name.

        Args:
            name: Provider name.

        Returns:
            The registered provider.

        Raises:
            ValueError: If provider is not registered.
        """
        if name not in self.providers:
            raise ValueError(
                f"Unknown provider: {name}. Available: {list(self.providers.keys())}"
            )
        return self.providers[name]

    def create_llm(self, provider: str, **kwargs: Any) -> BaseChatModel:
        """Create an LLM instance using the specified provider.

        Args:
            provider: Name of the provider to use.
            **kwargs: Configuration options passed to the provider.

        Returns:
            Configured BaseChatModel instance.
        """
        return self.get_provider(provider).create_llm(**kwargs)


_default_factory: LLMFactory | None = None


def get_llm(provider: str, **kwargs: Any) -> BaseChatModel:
    """Convenience function to create an LLM using the default factory.

    Lazily initializes the default factory with standard providers.

    Args:
        provider: Name of the provider to use.
        **kwargs: Configuration options passed to the provider.

    Returns:
        Configured BaseChatModel instance.
    """
    from data_agent.llm.provider import AzureOpenAIProvider

    global _default_factory
    if _default_factory is None:
        _default_factory = LLMFactory()
        _default_factory.register_provider(AzureOpenAIProvider())

    return _default_factory.create_llm(provider, **kwargs)
