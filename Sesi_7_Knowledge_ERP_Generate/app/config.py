from pydantic_settings import BaseSettings
import os


class Settings(BaseSettings):
    erp_api_base: str = "http://127.0.0.1:8005"
    embed_model: str = "all-MiniLM-L6-v2"
    embed_dim: int = 384

    llm_model_gguf: str = "qwen2.5-0.5b-instruct-q4_k_m.gguf"
    llama_port: int = 8083
    llama_ctx: int = 2048
    llama_ngl: int = 0
    llama_threads: int = 3
    llama_ready_timeout: int = 90
    llama_base_url: str = "http://127.0.0.1:8083"

    app_port: int = 8007
    default_report_days: int = 7
    low_stock_threshold: int = 10

    class Config:
        env_file = ".env"


settings = Settings()
