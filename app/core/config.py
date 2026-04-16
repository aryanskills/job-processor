from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "Background Job Processor"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    DATABASE_URL: str = "sqlite+aiosqlite:///./jobs.db"

    # Job processing
    JOB_MIN_DELAY: int = 5   # seconds
    JOB_MAX_DELAY: int = 10  # seconds

    # Simulate random failures (0.0 – 1.0)
    JOB_FAILURE_RATE: float = 0.1

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
