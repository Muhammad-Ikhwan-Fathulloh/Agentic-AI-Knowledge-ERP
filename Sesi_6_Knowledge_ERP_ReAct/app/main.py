"""
Sesi 6 — Knowledge ERP dengan ReAct Prompting (Port 8006)
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.llm import lifespan, state
from app.schemas import ReActRequest, ReActResponse
from app.react_erp import erp_react_loop

app = FastAPI(
    title="Sesi 6 — Knowledge ERP ReAct Agent",
    version="6.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


@app.get("/health")
async def health():
    p = state.get("process")
    return {
        "app": "ok",
        "llama_alive": p is not None and p.poll() is None,
        "llama_ready": state.get("ready", False),
        "erp_api": settings.erp_api_base,
        "require_human_confirm": settings.require_human_confirm_for_create_order,
    }


@app.post("/agent/chat", response_model=ReActResponse)
async def chat(req: ReActRequest):
    result = await erp_react_loop(
        query=req.query,
        max_steps=req.max_steps,
        temperature=req.temperature,
        pending_confirm_answer=req.confirm_answer,
    )
    return ReActResponse(
        query=req.query,
        final_answer=result["final_answer"],
        steps=result["steps"],
        need_human_confirm=result.get("need_human_confirm", False),
        prompt_confirm=result.get("prompt_confirm"),
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.app_port)
