"""
Model Downloader — Download model GGUF dari HuggingFace.
Digunakan untuk auto-download model saat startup (Docker friendly)
atau via API manual (POST /ai/models/download).
"""
import os
import json
import asyncio
from typing import Optional

import httpx

from app.config import settings

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT_DIR = os.path.dirname(BASE_DIR)
MODELS_DIR = os.path.join(ROOT_DIR, "models")
STATE_FILE = os.path.join(MODELS_DIR, "_model_state.json")

HF_BASE = "https://huggingface.co"

DEFAULT_MODEL_CATALOG = [
    {
        "id": "qwen2.5-0.5b-instruct-q4_k_m",
        "filename": "qwen2.5-0.5b-instruct-q4_k_m.gguf",
        "hf_repo": "Qwen/Qwen2.5-0.5B-Instruct-GGUF",
        "hf_file": "qwen2.5-0.5b-instruct-q4_k_m.gguf",
        "size_mb": 370,
        "description": "Qwen 2.5 0.5B Instruct (Q4_K_M) — kecil & cepat, cocok untuk Docker/CPU.",
    },
    {
        "id": "qwen1.5b-q8",
        "filename": "qwen1.5b-q8.gguf",
        "hf_repo": "Qwen/Qwen2.5-1.5B-Instruct-GGUF",
        "hf_file": "qwen2.5-1.5b-instruct-q8_0.gguf",
        "size_mb": 1590,
        "description": "Qwen 2.5 1.5B Instruct (Q8_0) — akurasi lebih baik, ukuran lebih besar.",
    },
    {
        "id": "qwen3b-q8",
        "filename": "qwen3b-q8.gguf",
        "hf_repo": "Qwen/Qwen2.5-3B-Instruct-GGUF",
        "hf_file": "qwen2.5-3b-instruct-q8_0.gguf",
        "size_mb": 3180,
        "description": "Qwen 2.5 3B Instruct (Q8_0) — kualitas terbaik, butuh RAM lebih besar.",
    },
]


def _ensure_models_dir() -> None:
    os.makedirs(MODELS_DIR, exist_ok=True)


def _load_state() -> dict:
    if os.path.isfile(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_state(state: dict) -> None:
    _ensure_models_dir()
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def list_catalog() -> list:
    local_files = set()
    if os.path.isdir(MODELS_DIR):
        local_files = {f for f in os.listdir(MODELS_DIR) if f.endswith(".gguf")}

    catalog = []
    for m in DEFAULT_MODEL_CATALOG:
        item = dict(m)
        item["downloaded"] = m["filename"] in local_files
        if item["downloaded"]:
            fpath = os.path.join(MODELS_DIR, m["filename"])
            item["local_size_mb"] = round(os.path.getsize(fpath) / (1024 * 1024), 1)
        catalog.append(item)
    return catalog


def get_active_model() -> Optional[dict]:
    target = settings.llm_model_gguf
    for m in list_catalog():
        if m["filename"] == target:
            return m
    fpath = os.path.join(MODELS_DIR, target)
    if os.path.isfile(fpath):
        return {
            "id": target,
            "filename": target,
            "downloaded": True,
            "local_size_mb": round(os.path.getsize(fpath) / (1024 * 1024), 1),
        }
    return None


async def download_model(
    model_id: str,
    custom_url: Optional[str] = None,
    custom_filename: Optional[str] = None,
) -> dict:
    _ensure_models_dir()

    model = next((m for m in DEFAULT_MODEL_CATALOG if m["id"] == model_id), None)
    if model is None and custom_url is None:
        raise ValueError(f"Model ID '{model_id}' tidak ditemukan di katalog.")

    if custom_url:
        url = custom_url
        filename = custom_filename or os.path.basename(custom_url)
        size_mb = 0
    else:
        hf_repo = model["hf_repo"]
        hf_file = model["hf_file"]
        filename = custom_filename or model["filename"]
        mirror = settings.hf_mirror.rstrip("/") if settings.hf_mirror else HF_BASE
        url = f"{mirror}/{hf_repo}/resolve/main/{hf_file}"
        size_mb = model.get("size_mb", 0)

    dest = os.path.join(MODELS_DIR, filename)
    tmp_dest = dest + ".part"

    print(f"[Model] Downloading {filename} dari {url} ...")
    async with httpx.AsyncClient(
        timeout=settings.model_download_timeout_sec, follow_redirects=True
    ) as client:
        async with client.stream("GET", url) as resp:
            resp.raise_for_status()
            total = int(resp.headers.get("content-length", 0))
            downloaded = 0
            with open(tmp_dest, "wb") as f:
                async for chunk in resp.aiter_bytes(chunk_size=1024 * 1024):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        pct = downloaded * 100 // total
                        if pct % 10 == 0:
                            print(f"[Model]   {filename}: {pct}%")

    if os.path.isfile(dest):
        os.remove(dest)
    os.rename(tmp_dest, dest)

    actual_mb = round(os.path.getsize(dest) / (1024 * 1024), 1)
    state = _load_state()
    state["active"] = filename
    state["downloads"] = state.get("downloads", []) + [filename]
    _save_state(state)

    print(f"[Model] Selesai: {filename} ({actual_mb} MB).")
    return {"filename": filename, "size_mb": actual_mb, "path": dest}


def set_active_model(filename: str) -> dict:
    fpath = os.path.join(MODELS_DIR, filename)
    if not os.path.isfile(fpath):
        raise FileNotFoundError(f"Model {filename} tidak ada di {MODELS_DIR}")
    state = _load_state()
    state["active"] = filename
    _save_state(state)
    return {"active": filename, "path": fpath}
