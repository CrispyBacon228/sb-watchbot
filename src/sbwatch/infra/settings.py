from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABENTO_API_KEY: str
    DB_DATASET: str = "GLBX.MDP3"
    DB_SCHEMA: str = "ohlcv-1m"
    FRONT_SYMBOL: str = "NQU5"
    PRICE_DIVISOR: int = 1_000_000_000
    DISCORD_WEBHOOK_URL: str

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
