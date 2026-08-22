# app/pdf_ingest.py
from pypdf import PdfReader
import io

def extract_chunks_from_pdf(file_bytes: bytes, chunk_size: int = 1000, overlap: int = 150) -> list[str]:
    """
    Baca PDF dari bytes, gabungkan semua teks, lalu pecah jadi chunk
    ber-overlap (biar konteks antar-chunk tidak putus, sama seperti
    strategi chunking di Sesi 1).
    """
    reader = PdfReader(io.BytesIO(file_bytes))
    full_text = "\n".join((page.extract_text() or "") for page in reader.pages)
    full_text = full_text.strip()

    if not full_text:
        return []

    chunks = []
    start = 0
    while start < len(full_text):
        end = start + chunk_size
        chunks.append(full_text[start:end])
        start = end - overlap  # mundur sedikit supaya overlap
    return chunks