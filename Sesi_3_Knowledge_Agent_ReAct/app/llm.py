import os
import time
import platform
import subprocess
import asyncio
from contextlib import asynccontextmanager

from dotenv import load_dotenv
import httpx

from app.config import settings

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT_DIR = os.path.dirname(os.path.dirname(BASE_DIR))
BIN_DIR = os.path.join(ROOT_DIR, "End-to-End LLM Serving", "backend", "bin")
MODELS_DIR = os.path.join(ROOT_DIR, "End-to-End LLM Serving", "models")

EXE_NAME = "llama-server.exe" if platform.system() == "Windows" else "llama-server"
LLAMA_SERVER_EXE = os.path.join(BIN_DIR, EXE_NAME)
MODEL_PATH = os.path.join(MODELS_DIR, settings.llm_model_gguf)
LOG_PATH = os.path.join(BASE_DIR, "llama_server.log")

state = {"process": None, "ready": False, "client": None}


def _read_log_tail(n_chars: int = 3000) -> str:
    try:
        with open(LOG_PATH, "r", errors="ignore") as f:
            return f.read()[-n_chars:]
    except OSError:
        return "(log tidak ditemukan)"


async def start_llama_server() -> None:
    if not os.path.isfile(LLAMA_SERVER_EXE):
        raise RuntimeError(f"llama-server tidak ditemukan: {LLAMA_SERVER_EXE}")
    if not os.path.isfile(MODEL_PATH):
        print(f"[WARN] Model GGUF tidak ada di: {MODEL_PATH} — lanjutkan tanpa model lokal")
        state["ready"] = False
        return

    cmd = [
        LLAMA_SERVER_EXE,
        "-m", MODEL_PATH,
        "--host", "127.0.0.1",
        "--port", str(settings.llama_port),
        "-c", str(settings.llama_ctx),
        "--n-gpu-layers", str(settings.llama_ngl),
        "--threads", str(settings.llama_threads),
        "--threads-batch", str(settings.llama_threads),
    ]

    print(f"[S3] Menjalankan llama-server: {' '.join(cmd)}")
    log_file = open(LOG_PATH, "w")
    process = subprocess.Popen(
        cmd, cwd=BIN_DIR, stdout=log_file, stderr=subprocess.STDOUT,
    )
    state["process"] = process

    async with httpx.AsyncClient(timeout=5.0) as probe:
        deadline = time.monotonic() + settings.llama_ready_timeout
        while time.monotonic() < deadline:
            if process.poll() is not None:
                log_file.flush()
                raise RuntimeError(
                    f"llama-server berhenti (exit {process.returncode}).\n"
                    f"--- log ---\n{_read_log_tail()}"
                )
            try:
                resp = await probe.get(f"{settings.llama_base_url}/health")
                if resp.status_code == 200:
                    print("[S3] llama-server siap.")
                    state["ready"] = True
                    return
            except httpx.HTTPError:
                pass
            await asyncio.sleep(1)

    raise RuntimeError(
        f"llama-server timeout setelah {settings.llama_ready_timeout}s.\n"
        f"--- log ---\n{_read_log_tail()}"
    )


def stop_llama_server() -> None:
    process = state.get("process")
    if process and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()


@asynccontextmanager
async def lifespan(app):
    state["client"] = httpx.AsyncClient(timeout=180.0)
    try:
        await start_llama_server()
    except Exception as e:
        print(f"[S3] ERROR startup llama-server: {e}")
    yield
    stop_llama_server()
    await state["client"].aclose()


async def llm_complete(prompt: str, max_tokens: int = 512, temperature: float = 0.3, stop=None) -> str:
    if not state.get("ready"):
        return "[LLM tidak siap — pastikan llama-server berjalan / model GGUF tersedia]"

    client: httpx.AsyncClient = state["client"]
    payload = {
        "prompt": prompt,
        "n_predict": max_tokens,
        "temperature": temperature,
    }
    if stop:
        payload["stop"] = stop if isinstance(stop, list) else [stop]

    try:
        resp = await client.post(f"{settings.llama_base_url}/completion", json=payload)
        data = resp.json()
        return data.get("content", "").strip()
    except Exception as e:
        return f"[ERROR LLM: {e}]"
