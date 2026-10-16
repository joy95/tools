from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Media Tools API"
    database_url: str = "sqlite:///./data/media_tools.db"
    redis_url: str = "redis://localhost:6379/0"
    media_root: str = "./media"
    public_media_prefix: str = "/media"
    speech_model_size: str = "tiny"
    ytdlp_cookies_file: str | None = None


settings = Settings()
