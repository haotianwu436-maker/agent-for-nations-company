from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "media-ai-api"
    database_url: str = "postgresql+psycopg://media_ai:media_ai@127.0.0.1:5432/media_ai"
    jwt_secret: str = "replace_me"
    jwt_expire_minutes: int = 120
    litellm_base_url: str = ""
    litellm_api_key: str = ""
    litellm_model: str = ""


settings = Settings()
