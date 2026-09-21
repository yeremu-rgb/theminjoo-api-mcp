from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    base_url: str = "https://theminjoo.kr/main/sub/news"
    request_timeout: float = 15.0
    cache_ttl_seconds: int = 300
    user_agent: str = "theminjoo-api-mcp/0.3 (+https://github.com/yeremu-rgb/theminjoo-api-mcp)"
    default_page_size: int = 20
    max_page_size: int = 100
    mcp_token: str | None = None
    cors_origins: str = "*"
    public_url: str | None = None
    oauth_secret: str = "dev-only-change-me"

    model_config = SettingsConfigDict(env_prefix="THEMINJOO_", env_file=".env")

    @property
    def allowed_origins(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


settings = Settings()
