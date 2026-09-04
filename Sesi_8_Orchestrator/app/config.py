from pydantic_settings import BaseSettings
import os


class Settings(BaseSettings):
    knowledge_api_base: str = "http://127.0.0.1:8001"
    erp_api_base: str = "http://127.0.0.1:8005"
    erp_report_api_base: str = "http://127.0.0.1:8007"

    embed_model: str = "all-MiniLM-L6-v2"
    embed_dim: int = 384
    duckdb_path: str = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "orchestrator.duckdb",
    )

    llm_model_gguf: str = "qwen2.5-0.5b-instruct-q4_k_m.gguf"
    llama_port: int = 8088
    llama_ctx: int = 2048
    llama_ngl: int = 0
    llama_threads: int = 3
    llama_ready_timeout: int = 90
    llama_base_url: str = "http://127.0.0.1:8088"

    app_port: int = 8000
    semantic_cache_threshold: float = 0.15
    max_react_steps: int = 5
    router_max_retry: int = 2
    knowledge_agent_mode: str = "planner"  # planner | react

    class Config:
        env_file = ".env"


settings = Settings()
