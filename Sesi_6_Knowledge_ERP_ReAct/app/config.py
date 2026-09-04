from pydantic_settings import BaseSettings
import os


class Settings(BaseSettings):
    erp_api_base: str = "http://127.0.0.1:8005"

    llm_model_gguf: str = "qwen2.5-0.5b-instruct-q4_k_m.gguf"
    llama_port: int = 8082
    llama_ctx: int = 2048
    llama_ngl: int = 0
    llama_threads: int = 3
    llama_ready_timeout: int = 90
    llama_base_url: str = "http://127.0.0.1:8082"

    app_port: int = 8006
    max_react_steps: int = 5
    require_human_confirm_for_create_order: bool = True

    class Config:
        env_file = ".env"


settings = Settings()
