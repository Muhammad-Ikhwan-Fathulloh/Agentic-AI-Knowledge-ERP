from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    vector_backend: str = "duckdb"
    embed_model: str = "all-MiniLM-L6-v2"
    embed_dim: int = 384
    duckdb_path: str = "knowledge.duckdb"
    app_port: int = 8001

    class Config:
        env_file = ".env"

settings = Settings()