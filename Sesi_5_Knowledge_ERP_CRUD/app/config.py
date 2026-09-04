from pydantic_settings import BaseSettings
import os


class Settings(BaseSettings):
    embed_model: str = "all-MiniLM-L6-v2"
    embed_dim: int = 384
    duckdb_path: str = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..",
        "erp.duckdb",
    )
    app_port: int = 8005

    class Config:
        env_file = ".env"


settings = Settings()
