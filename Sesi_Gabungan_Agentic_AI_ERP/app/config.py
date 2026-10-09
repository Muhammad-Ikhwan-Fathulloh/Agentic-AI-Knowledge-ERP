from pydantic_settings import BaseSettings
import os


class Settings(BaseSettings):
    embed_model: str = "all-MiniLM-L6-v2"
    embed_dim: int = 384

    duckdb_path: str = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "agentic_ai_erp.duckdb",
    )

    chunk_size: int = 400
    chunk_overlap: int = 80

    llm_model_gguf: str = "qwen2.5-0.5b-instruct-q4_k_m.gguf"
    llama_port: int = 8088
    llama_ctx: int = 2048
    llama_ngl: int = 0
    llama_threads: int = 3
    llama_ready_timeout: int = 90
    llama_base_url: str = "http://127.0.0.1:8088"

    app_port: int = 8080
    default_report_days: int = 7
    low_stock_threshold: int = 10

    class Config:
        env_file = ".env"


settings = Settings()
