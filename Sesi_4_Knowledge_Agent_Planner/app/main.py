"""
Sesi 4 - Knowledge Agent Planner-Executor (Structured JSON Prompting)
Port 8003
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.llm import lifespan, state
from app.schemas import PlannerRequest, PlannerResponse
from app.planner import plan_and_execute

app = FastAPI(
    title="Sesi 4 - Knowledge Agent Planner (JSON Structured)",
    version="4.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


@app.get("/health")
async def health():
    p = state.get("process")
    return {
        "app": "ok",
        "llama_alive": p is not None and p.poll() is None,
        "llama_ready": state.get("ready", False),
        "knowledge_api": settings.knowledge_api_base,
    }


@app.post("/agent/chat", response_model=PlannerResponse)
async def chat(req: PlannerRequest):
    result = await plan_and_execute(req.question, req.temperature)
    return PlannerResponse(
        question=req.question,
        decision=result["decision"],
        context=result["context"],
        llm_calls=result["llm_calls"],
        planner_retries=result["planner_retries"],
        final_answer=result["final_answer"],
    )


@app.get("/agent/compare_react_vs_planner")
async def compare_endpoint():
    return {
        "ReAct (Sesi 3)": {
            "style": "Iteratif Thought/Action/Observation",
            "llm_calls": "N kali (satu per langkah)",
            "cocok": "Tugas multi-langkah, investigasi bertahap",
            "kelemahan": "Lebih lambat, rawan format error pada model kecil",
            "port": 8002,
        },
        "Planner (Sesi 4)": {
            "style": "Single-shot JSON decision -> tool -> answer",
            "llm_calls": "2 kali (planner + answer)",
            "cocok": "Tugas satu langkah, FAQ, pencarian langsung",
            "kelemahan": "Tidak fleksibel untuk chain reasoning panjang",
            "port": 8003,
        },
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.app_port)
