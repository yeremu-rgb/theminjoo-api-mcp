from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    base_url: str = "https://theminjoo.kr/main/sub/news"
    request_timeout: float = 15.0
    cache_ttl_seconds: int = 300
    user_agent: str = "theminjoo-api-mcp/0.1 (+https://github.com/)"
    default_page_size: int = 20
    max_page_size: int = 100

    model_config = SettingsConfigDict(env_prefix="THEMINJOO_", env_file=".env")


settings = Settings()
