# Sesi 4 — Knowledge Agent Planner-Executor (Structured JSON)

## Ringkasan
Alternatif dari loop ReAct: agent melakukan **dua call LLM saja**:
1. **Planner** → output JSON `{need_tool, tool, query}` untuk memutuskan perlu pencarian atau tidak.
2. **Answer** → menyusun jawaban final dari konteks yang didapat.

Pola ini lebih **cepat** dan stabil untuk FAQ / task satu-langkah, tapi kurang fleksibel dibanding ReAct untuk investigasi bertahap.

## Prasyarat
- Sesi 2 Knowledge CRUD API (Port 8001) berjalan.
- Model GGUF Qwen + binary llama-server ada di folder `../End-to-End LLM Serving/`.

## Cara Run
```cmd
run.bat
```

## Endpoint
| Endpoint | Method | Deskripsi |
|---|---|---|
| `GET /health` | GET | Cek status app, LLM, dan Knowledge API |
| `POST /agent/chat` | POST | Input `{question, temperature}` → jawaban + detail planner decision + jumlah LLM call |
| `GET /agent/compare_react_vs_planner` | GET | Ringkasan perbandingan ReAct (Sesi 3) vs Planner (Sesi 4) |

## Struktur
```
Sesi_4_Knowledge_Agent_Planner/
├── app/
│   ├── config.py / schemas.py / llm.py   (mirip Sesi 3, beda port LLM 8081)
│   ├── planner.py   # Prompt Planner + Answer + extract_json + KnowledgeTools
│   └── main.py
└── tests/test_planner.py  # Unit test extract_json (TANPA butuh LLM)
```

## Tugas Eksplorasi
1. Bandingkan latency Sesi 3 vs Sesi 4 untuk 5 pertanyaan FAQ yang sama.
2. Catat berapa kali Planner JSON tidak valid (gagal parse).
3. Tambahkan tool `create_document` di planner mode.
