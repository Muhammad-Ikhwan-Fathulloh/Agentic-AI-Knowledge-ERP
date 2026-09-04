import os, time, platform, subprocess, asyncio
from contextlib import asynccontextmanager
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


def _tail(n=3000):
    try:
        with open(LOG_PATH, "r", errors="ignore") as f:
            return f.read()[-n:]
    except OSError:
        return ""


async def start_llama_server():
    if not os.path.isfile(LLAMA_SERVER_EXE):
        raise RuntimeError(f"llama-server tidak ditemukan: {LLAMA_SERVER_EXE}")
    if not os.path.isfile(MODEL_PATH):
        print(f"[WARN] Model GGUF tidak ada: {MODEL_PATH}")
        state["ready"] = False
        return
    cmd = [
        LLAMA_SERVER_EXE, "-m", MODEL_PATH,
        "--host", "127.0.0.1", "--port", str(settings.llama_port),
        "-c", str(settings.llama_ctx),
        "--n-gpu-layers", str(settings.llama_ngl),
        "--threads", str(settings.llama_threads),
        "--threads-batch", str(settings.llama_threads),
    ]
    print(f"[S8] llama-server port {settings.llama_port}")
    log_file = open(LOG_PATH, "w")
    p = subprocess.Popen(cmd, cwd=BIN_DIR, stdout=log_file, stderr=subprocess.STDOUT)
    state["process"] = p
    async with httpx.AsyncClient(timeout=5.0) as probe:
        deadline = time.monotonic() + settings.llama_ready_timeout
        while time.monotonic() < deadline:
            if p.poll() is not None:
                raise RuntimeError(f"exit {p.returncode}\n{_tail()}")
            try:
                r = await probe.get(f"{settings.llama_base_url}/health")
                if r.status_code == 200:
                    state["ready"] = True
                    print("[S8] llama-server siap.")
                    return
            except httpx.HTTPError:
                pass
            await asyncio.sleep(1)
    raise RuntimeError(f"timeout\n{_tail()}")


def stop_llama_server():
    p = state.get("process")
    if p and p.poll() is None:
        p.terminate()
        try: p.wait(timeout=5)
        except subprocess.TimeoutExpired: p.kill()


@asynccontextmanager
async def lifespan(app):
    state["client"] = httpx.AsyncClient(timeout=240.0)
    from app.database import init_db
    init_db()
    try:
        await start_llama_server()
    except Exception as e:
        print(f"[S8] ERROR startup llama: {e}")
    yield
    stop_llama_server()
    await state["client"].aclose()


async def llm_complete(prompt, max_tokens=700, temperature=0.3, stop=None) -> str:
    if not state.get("ready"):
        return "[LLM tidak siap]"
    client: httpx.AsyncClient = state["client"]
    payload = {"prompt": prompt, "n_predict": max_tokens, "temperature": temperature}
    if stop:
        payload["stop"] = stop if isinstance(stop, list) else [stop]
    try:
        resp = await client.post(f"{settings.llama_base_url}/completion", json=payload)
        return resp.json().get("content", "").strip()
    except Exception as e:
        return f"[ERROR: {e}]"
