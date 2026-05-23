from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    MONGODB_URI: str
    DATABASE_NAME: str
    OPENAI_API_KEY: str
    OPENAI_MODEL: str = "gpt-4o"
    UPLOAD_DIR: str = "uploads"
    MAX_FILE_SIZE_MB: int = 50
    ALLOWED_ORIGINS: List[str] = ["*"]

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
