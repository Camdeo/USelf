import os


def database_url() -> str:
    value = os.getenv("DATABASE_URL", "sqlite:///./uself_local.db")
    if value.startswith("postgresql://"):
        return value.replace("postgresql://", "postgresql+psycopg://", 1)
    if value.startswith("postgres://"):
        return value.replace("postgres://", "postgresql+psycopg://", 1)
    return value


APP_ENV = os.getenv("APP_ENV", "development")
