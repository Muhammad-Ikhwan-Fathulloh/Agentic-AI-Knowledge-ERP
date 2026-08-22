# app/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    vector_backend: str = "duckdb"
    embed_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    embed_dim: int = 384
    duckdb_path: str = "knowledge.duckdb"
    # postgres_url: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/knowledge"

    class Config:
        env_file = ".env"

settings = Settings()