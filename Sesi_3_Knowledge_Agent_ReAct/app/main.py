"""
Sesi 3 — Knowledge Agent dengan ReAct Prompting (Port 8002)
============================================================
FastAPI yang membungkus ReAct loop + tools + llama-server.
Cara run:
    cd Sesi_3_Knowledge_Agent_ReAct
    pip install -r requirements.txt
    uvicorn app.main:app --port 8002 --reload
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.llm import lifespan, state
from app.schemas import ReActRequest, ReActResponse
from app.react import react_loop

app = FastAPI(
    title="Sesi 3 — Knowledge Agent ReAct",
    version="3.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    process = state.get("process")
    alive = process is not None and process.poll() is None
    return {
        "app": "ok",
        "llama_server_alive": alive,
        "llama_server_ready": state.get("ready", False),
        "knowledge_api": settings.knowledge_api_base,
    }


@app.post("/agent/chat", response_model=ReActResponse)
async def chat(req: ReActRequest):
    answer, steps = await react_loop(
        query=req.query,
        max_steps=req.max_steps,
        temperature=req.temperature,
    )
    return ReActResponse(
        query=req.query,
        final_answer=answer,
        steps=steps,
        total_steps=len(steps),
        domain="knowledge",
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.app_port)
