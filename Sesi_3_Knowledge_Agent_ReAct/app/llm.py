import os
import time
import platform
import subprocess
import asyncio
from contextlib import asynccontextmanager
import httpx

from app.config import settings

class LlamaClient:
    """Clean wrapper for launching and querying local llama-server."""
    
    def __init__(self, bin_path: str, model_path: str, port: int, ctx: int, ngl: int, threads: int, base_url: str):
        self.bin_path = bin_path
        self.model_path = model_path
        self.port = port
        self.ctx = ctx
        self.ngl = ngl
        self.threads = threads
        self.base_url = base_url
        
        self._process = None
        self._is_ready = False
        self._http_client = httpx.AsyncClient(timeout=180.0)
        self._log_path = "llama_server.log"

    def _read_log_tail(self, n_chars: int = 3000) -> str:
        try:
            with open(self._log_path, "r", errors="ignore") as f:
                return f.read()[-n_chars:]
        except OSError:
            return "(log tidak ditemukan)"

    async def start(self, timeout: int = 90) -> None:
        if not os.path.isfile(self.bin_path):
            raise RuntimeError(f"llama-server tidak ditemukan di: {self.bin_path}")
            
        if not os.path.isfile(self.model_path):
            print(f"[WARN] Model GGUF tidak ditemukan di: {self.model_path} — lanjutkan tanpa model lokal.")
            return

        cmd = [
            self.bin_path, "-m", self.model_path,
            "--host", "127.0.0.1", "--port", str(self.port),
            "-c", str(self.ctx),
            "--n-gpu-layers", str(self.ngl),
            "--threads", str(self.threads),
            "--threads-batch", str(self.threads),
        ]
        
        print(f"[LLM] Menjalankan llama-server di port {self.port}...")
        log_file = open(self._log_path, "w")
        
        self._process = subprocess.Popen(
            cmd, cwd=os.path.dirname(self.bin_path), stdout=log_file, stderr=subprocess.STDOUT
        )

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._process.poll() is not None:
                raise RuntimeError(f"llama-server berhenti (exit {self._process.returncode}).\nLog:\n{self._read_log_tail()}")
            try:
                r = await self._http_client.get(f"{self.base_url}/health", timeout=2.0)
                if r.status_code == 200:
                    self._is_ready = True
                    print("[LLM] llama-server siap melayani request.")
                    return
            except httpx.HTTPError:
                pass
            await asyncio.sleep(1)

        raise RuntimeError(f"llama-server timeout setelah {timeout}s.\nLog:\n{self._read_log_tail()}")

    def stop(self) -> None:
        if self._process and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
            
    async def close(self) -> None:
        self.stop()
        await self._http_client.aclose()

    async def complete(self, prompt: str, max_tokens: int = 512, temperature: float = 0.3, stop=None) -> str:
        if not self._is_ready:
            return "[LLM tidak siap — pastikan llama-server berjalan / model tersedia]"

        payload = {
            "prompt": prompt,
            "n_predict": max_tokens,
            "temperature": temperature,
        }
        if stop:
            payload["stop"] = stop if isinstance(stop, list) else [stop]
            
        try:
            resp = await self._http_client.post(f"{self.base_url}/completion", json=payload)
            resp.raise_for_status()
            return resp.json().get("content", "").strip()
        except Exception as e:
            return f"[ERROR LLM: {e}]"


# === Path setup specific to Sesi_3 ===
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT_DIR = os.path.dirname(os.path.dirname(BASE_DIR))
BIN_DIR = os.path.join(ROOT_DIR, "Agentic-AI-Knowledge-ERP", "Sesi_3_Knowledge_Agent_ReAct", "bin")
MODELS_DIR = os.path.join(ROOT_DIR, "Agentic-AI-Knowledge-ERP", "models")
EXE_NAME = "llama-server.exe" if platform.system() == "Windows" else "llama-server"

# Singleton instance
llama_client = LlamaClient(
    bin_path=os.path.join(BIN_DIR, EXE_NAME),
    model_path=os.path.join(MODELS_DIR, settings.llm_model_gguf),
    port=settings.llama_port,
    ctx=settings.llama_ctx,
    ngl=settings.llama_ngl,
    threads=settings.llama_threads,
    base_url=settings.llama_base_url,
)

@asynccontextmanager
async def lifespan(app):
    try:
        await llama_client.start(timeout=settings.llama_ready_timeout)
    except Exception as e:
        print(f"[S3] ERROR startup llama-server: {e}")
    yield
    await llama_client.close()

# Interface wrapper yang kompatibel dengan kode sebelumnya
async def llm_complete(prompt: str, max_tokens: int = 512, temperature: float = 0.3, stop=None) -> str:
    return await llama_client.complete(prompt, max_tokens, temperature, stop)
