from typing import Any, Dict, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Load environment variables from .env and system environment
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # Server settings
    host: str = Field(default="0.0.0.0", validation_alias="HOST")
    port: int = Field(default=8000, validation_alias="PORT")

    # Debug mode
    debug: bool = Field(default=False, validation_alias="DEBUG")

    # LLM settings
    engine_type: str = Field(default="anthropic", validation_alias="ENGINE_TYPE")

    # General LLM settings
    max_tokens: int = Field(default=1000, validation_alias="MAX_TOKENS")

    # Anthropic settings
    anthropic_api_key: Optional[str] = Field(
        default=None, validation_alias="ANTHROPIC_API_KEY"
    )
    anthropic_embedding_model: str = Field(
        default="claude-3-7-embeddings-v1",
        validation_alias="ANTHROPIC_EMBEDDING_MODEL",
    )
    anthropic_llm_model: str = Field(
        default="claude-3-7-sonnet-20250219",
        validation_alias="ANTHROPIC_LLM_MODEL",
    )

    # OpenAI settings
    openai_api_key: Optional[str] = Field(
        default=None, validation_alias="OPENAI_API_KEY"
    )
    openai_embedding_model: str = Field(
        default="text-embedding-3-large",
        validation_alias="OPENAI_EMBEDDING_MODEL",
    )
    openai_llm_model: str = Field(
        default="gpt-4",
        validation_alias="OPENAI_LLM_MODEL",
    )

    # MCP Server API Key
    exa_api_key: Optional[str] = Field(default=None, validation_alias="EXA_API_KEY")

    # Logfire settings
    logfire_enabled: bool = Field(default=False, validation_alias="LOGFIRE_ENABLED")
    logfire_token: Optional[str] = Field(default=None, validation_alias="LOGFIRE_TOKEN")
    logfire_service_name: str = Field(
        default="brain", validation_alias="LOGFIRE_SERVICE_NAME"
    )

    def get_llm_config(self) -> Dict[str, Any]:
        """Return the engine-specific configuration dictionary."""
        llm_engine = self.engine_type.lower()
        if llm_engine == "anthropic":
            if not self.anthropic_api_key:
                raise ValueError(
                    "ANTHROPIC_API_KEY is required when ENGINE_TYPE is 'anthropic'"
                )
            return {
                "api_key": self.anthropic_api_key,
                "embedding_model": self.anthropic_embedding_model,
                "llm_model": self.anthropic_llm_model,
                "max_tokens": self.max_tokens,
                "exa_api_key": self.exa_api_key,
            }
        elif llm_engine == "openai":
            if not self.openai_api_key:
                raise ValueError(
                    "OPENAI_API_KEY is required when ENGINE_TYPE is 'openai'"
                )
            return {
                "api_key": self.openai_api_key,
                "embedding_model": self.openai_embedding_model,
                "llm_model": self.openai_llm_model,
                "max_tokens": self.max_tokens,
            }
        else:
            raise ValueError(f"Unsupported ENGINE_TYPE: {self.engine_type}")


def get_settings() -> Settings:
    """Instantiate and return the Settings object."""
    return Settings()
