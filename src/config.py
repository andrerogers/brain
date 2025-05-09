from typing import Dict, Any, Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Server settings
    host: str = Field("0.0.0.0", env="HOST")
    port: int = Field(8000, env="PORT")

    # LLM settings
    engine_type: str = Field("anthropic", env="ENGINE_TYPE")

    # RAG settings
    rag_top_k: int = Field(3, env="RAG_TOP_K")

    # Anthropic settings
    anthropic_api_key: Optional[str] = Field(None, env="ANTHROPIC_API_KEY")
    anthropic_embedding_model: str = Field("claude-3-7-embeddings-v1",
                                           env="ANTHROPIC_EMBEDDING_MODEL")
    anthropic_llm_model: str = Field("claude-3-7-sonnet-20250219",
                                     env="ANTHROPIC_LLM_MODEL")

    # OpenAI settings
    openai_api_key: Optional[str] = Field(None, env="OPENAI_API_KEY")
    openai_embedding_model: str = Field("text-embedding-3-large",
                                        env="OPENAI_EMBEDDING_MODEL")
    openai_llm_model: str = Field("gpt-4", env="OPENAI_LLM_MODEL")

    # General LLM settings
    max_tokens: int = Field(1000, env="MAX_TOKENS")

    # Debug mode
    debug: bool = Field(False, env="DEBUG")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    def get_engine_config(self) -> Dict[str, Any]:
        """Get the configuration dictionary for the selected engine type."""
        # Changed rag_type to engine_type to match the field name
        if self.engine_type.lower() == 'anthropic':
            if not self.anthropic_api_key:
                raise ValueError("ANTHROPIC_API_KEY is required "
                                 "when ENGINE_TYPE is 'anthropic'")
            return {
                'api_key': self.anthropic_api_key,
                'embedding_model': self.anthropic_embedding_model,
                'llm_model': self.anthropic_llm_model,
                'max_tokens': self.max_tokens
            }
        elif self.engine_type.lower() == 'openai':
            if not self.openai_api_key:
                raise ValueError("OPENAI_API_KEY is required "
                                 "when ENGINE_TYPE is 'openai'")
            return {
                'api_key': self.openai_api_key,
                'embedding_model': self.openai_embedding_model,
                'llm_model': self.openai_llm_model,
                'max_tokens': self.max_tokens
            }
        else:
            # Changed rag_type to engine_type to match the field name
            raise ValueError(f"Unsupported ENGINE_TYPE: {self.engine_type}")


def get_settings() -> Settings:
    return Settings()
