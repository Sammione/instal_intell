"""Configuration, read from environment variables (or a .env file)."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    products_api_url: str = "https://aba-craft.vercel.app/api/products"
    products_api_key: str | None = None          # sent as Bearer token if set
    catalog_refresh_seconds: int = 300           # re-fetch catalog every 5 min
    request_timeout_seconds: float = 10.0

    intent_confidence_threshold: float = 0.35    # below this -> clarify / handoff
    product_match_threshold: int = 75            # fuzzy score 0-100
    semantic_match_threshold: float = 0.15       # TF-IDF cosine similarity

    memory_ttl_seconds: int = 1800               # remember last product for 30 min
    max_products_in_list: int = 5

    service_api_key: str | None = None           # if set, callers must send X-API-Key
    store_name: str = "Aba Craft"


settings = Settings()
