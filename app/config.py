from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment/.env."""

    cosmos_connection_string: str = ""
    cosmos_database_name: str = "sparc"
    redis_url: str = "redis://localhost:6379/0"
    tenant_cache_ttl_seconds: int = 300
    flag_cache_ttl_seconds: int = 60
    role_cache_ttl_seconds: int = 300

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
