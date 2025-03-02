from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    secret_key: str = "SECRET_KEY"
    algorithm: str = "HS256"

    postgres_user: str = "DB_USER"
    postgres_password: str = "DB_PASSWORD"
    postgres_db: str = "DB"
    postgres_host: str = "DB_HOST"
    postgres_port: int = 5433

    redis_host: str = "REDIS_HOST"
    redis_port: int = 6379
    redis_password: str = "REDIS_PASSWORD"

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


config = Settings()
