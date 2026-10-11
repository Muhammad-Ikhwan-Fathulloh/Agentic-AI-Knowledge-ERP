import requests
import json

BASE = "http://127.0.0.1:8080"

r = requests.post(f"{BASE}/chat/send", json={
    "message": "Apa produk yang stoknya paling rendah?",
    "session_id": None,
    "agentic_mode": True
}, timeout=120)

d = r.json()
print("FULL RESPONSE KEYS:", list(d.keys()))
print("STATUS:", d.get("status"))
print("ERROR:", d.get("error"))
print("SESSION_ID:", d.get("session_id"))
print("MEMORY_USED:", d.get("memory_used"))
print("\n=== JAWABAN AI ===")
print(repr(d.get("answer", "")))
print("\n=== AGENTIC STEPS ===")
for s in d.get("agentic_steps", []):
    print(f"  - {s['action']}: {json.dumps(s.get('result', {}), ensure_ascii=False)[:300]}")
