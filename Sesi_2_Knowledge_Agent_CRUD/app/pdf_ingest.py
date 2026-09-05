from pypdf import PdfReader
from pypdf.errors import EmptyFileError, PdfReadError
import io


def extract_chunks_from_pdf(file_bytes: bytes, chunk_size: int = 1000, overlap: int = 150) -> list[str]:
    """
    Baca PDF dari bytes, gabungkan semua teks, lalu pecah jadi chunk
    ber-overlap (biar konteks antar-chunk tidak putus, sama seperti
    strategi chunking di Sesi 1).

    Mengembalikan list kosong jika: file_bytes kosong, PDF header tidak
    valid, atau tidak ada teks yang bisa diekstrak (misal PDF hasil
    scan/gambar).
    """
    if not file_bytes:
        return []
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
    except (EmptyFileError, PdfReadError, OSError, ValueError):
        return []

    pages_text = []
    for page in reader.pages:
        try:
            pages_text.append(page.extract_text() or "")
        except Exception:
            pages_text.append("")
    full_text = "\n".join(pages_text).strip()

    if not full_text:
        return []

    if overlap >= chunk_size:
        overlap = max(0, chunk_size // 4)

    chunks: list[str] = []
    start = 0
    safe_step = chunk_size - overlap if chunk_size > overlap else chunk_size
    if safe_step <= 0:
        safe_step = chunk_size
    while start < len(full_text):
        end = min(start + chunk_size, len(full_text))
        chunk = full_text[start:end]
        if chunk.strip():
            chunks.append(chunk)
        start += safe_step
    return chunks