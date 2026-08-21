from pydantic import (
    Field,
    SecretStr,
)
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)


class Settings(BaseSettings):
    app_env: str = "local"
    app_debug: bool = False

    database_url: str

    llm_provider: str | None = None

    llm_api_key: SecretStr | None = None

    llm_model: str | None = None

    llm_timeout_seconds: float = Field(
        default=30.0,
        gt=0,
        le=300,
    )

    llm_max_retries: int = Field(
        default=1,
        ge=0,
        le=5,
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()