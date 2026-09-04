from pydantic_settings import BaseSettings
import os


class Settings(BaseSettings):
    vector_backend: str = "duckdb"
    embed_model: str = "all-MiniLM-L6-v2"
    embed_dim: int = 384
    duckdb_path: str = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "Sesi_2",
        "knowledge.duckdb",
    )
    knowledge_api_base: str = "http://127.0.0.1:8001"

    llm_model_gguf: str = "qwen2.5-0.5b-instruct-q4_k_m.gguf"
    llama_port: int = 8080
    llama_ctx: int = 2048
    llama_ngl: int = 0
    llama_threads: int = 3
    llama_ready_timeout: int = 90
    llama_base_url: str = "http://127.0.0.1:8080"

    app_port: int = 8002

    class Config:
        env_file = ".env"


settings = Settings()
