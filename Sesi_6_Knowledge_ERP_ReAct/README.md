# Sesi 6 — Knowledge ERP ReAct Agent (Port 8006)

## Ringkasan
Menyambungkan **loop ReAct** dengan **tool registry ERP** (Sesi 5 API). Agent sekarang bisa **melakukan aksi bisnis** bukan cuma mencari informasi.

## Tool yang Tersedia
| Tool | Kapan dipakai |
|---|---|
| `list_products` | User ingin lihat daftar produk / "tampilkan semua" |
| `check_stock` | User nanya stok / ketersediaan produk |
| `list_customers` | Sebelum create_order (agent harus dapat `customer_id`) |
| `get_order_status` | User nanya status order berdasarkan ID |
| `create_order` | Agent "stage" order (BELUM final, perlu konfirmasi user) |
| `confirm_create_order` | Finalisasi order bila jawaban user = YA/SETUJU |

## Guardrail Penting
- **Human-in-the-loop**: `create_order` hanya distage → user harus jawab **YA** via field `confirm_answer` di request berikutnya.
- Agent di-prod (via prompt) **wajib** panggil `check_stock` dan `list_customers` sebelum `create_order`.

## Cara Run
```cmd
run.bat
```
(Otomatis spawning Sesi 5 ERP CRUD + Sesi 6 Agent ReAct)

## Endpoint
| Endpoint | Method | Body |
|---|---|---|
| `POST /agent/chat` | POST | `{"query":"...","confirm_answer":"ya"}` (opsional) |

Contoh percakapan 2-langkah:
1. Request 1: `{"query":"Saya ingin beli 2 NocMouse untuk Budi Santoso"}`
   → Response: `need_human_confirm: true`, prompt_confirm minta konfirmasi.
2. Request 2: `{"query":"lanjutkan","confirm_answer":"ya"}`
   → Order final disimpan.

## Struktur
```
Sesi_6_Knowledge_ERP_ReAct/
├── app/
│   ├── config.py / schemas.py / llm.py   (llama port 8082)
│   ├── tools.py       # ERPTools class (panggil HTTP Sesi 5)
│   ├── react_erp.py   # ReAct loop + ERP_REACT_SYSTEM prompt + parse step
│   └── main.py
└── tests/test_erp_react.py  # Test parser Thought/Action/Action Input
```
