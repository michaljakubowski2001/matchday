from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MATCHDAY_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://matchday:matchday@localhost:5432/matchday"
    # Signs session cookies. Required: there is deliberately no default.
    secret_key: str
    # "fake" serves generated fixtures; "football-data" calls football-data.org.
    provider: str = "fake"
    football_data_token: str = ""
    # football-data.org competition codes: Champions League and Premier League.
    competitions: list[str] = ["CL", "PL"]
    timezone: str = "Europe/Warsaw"
    secure_cookies: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
