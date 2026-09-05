import sys
import os
import tempfile
import io

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    tmp = tempfile.NamedTemporaryFile(suffix=".duckdb", delete=False)
    tmp.close()
    tmp_path = tmp.name

    from app.config import Settings

    _original = Settings.model_config.get("env_file")
    Settings.model_config["env_file"] = None

    from app import config as cfg_mod

    prev = cfg_mod.settings
    from app.config import settings as s

    s.duckdb_path = tmp_path
    s.vector_backend = "duckdb"

    from app import database as db_mod

    db_mod.store = db_mod.DocStore()

    from app.main import app

    c = TestClient(app)
    yield c

    Settings.model_config["env_file"] = _original
    cfg_mod.settings = prev
    try:
        os.unlink(tmp_path)
    except OSError:
        pass


def _make_minimal_pdf_bytes() -> bytes:
    content = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>
endobj
4 0 obj
<< /Length 88 >>
stream
BT
/F1 12 Tf
50 720 Td
(Ini adalah teks PDF untuk test upload knowledge base.) Tj
ET
endstream
endobj
5 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000111 00000 n 
0000000226 00000 n 
0000000364 00000 n 
trailer
<< /Size 6 /Root 1 0 R >>
startxref
440
%%EOF
"""
    return content


def test_upload_pdf_non_pdf_rejected(client):
    r = client.post(
        "/documents/upload-pdf",
        files={"file": ("test.txt", b"ini bukan pdf", "text/plain")},
    )
    assert r.status_code == 400


def test_upload_pdf_empty_text_rejected(client):
    empty_pdf_like = b"%PDF-1.4\n%EOF"
    r = client.post(
        "/documents/upload-pdf",
        files={"file": ("empty.pdf", empty_pdf_like, "application/pdf")},
    )
    assert r.status_code == 422
