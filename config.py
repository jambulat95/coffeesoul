from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # NOTE: default "" so imports don't crash when env missing.
    # main.py will validate that token is set before starting polling.
    bot_token: str
    database_url: str 
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        extra="ignore"  # Игнорировать лишние переменные (POSTGRES_*) в .env
    )

settings = Settings()
