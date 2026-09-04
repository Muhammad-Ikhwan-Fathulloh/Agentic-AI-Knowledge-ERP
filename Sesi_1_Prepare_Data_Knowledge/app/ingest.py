import os
import io
from pypdf import PdfReader
from pypdf.errors import EmptyFileError, PdfReadError


def extract_text_from_txt(file_bytes: bytes, filename: str = "") -> tuple[str, str]:
    """Return (source_name, full_text)."""
    try:
        text = file_bytes.decode("utf-8", errors="ignore")
    except Exception:
        text = file_bytes.decode("latin-1", errors="ignore")
    return filename or "unknown.txt", text.strip()


def extract_text_from_pdf(file_bytes: bytes, filename: str = "") -> tuple[str, str]:
    """Robust PDF text extraction. Return empty string (tanpa exception) untuk
    file kosong, PDF rusak / invalid header, atau PDF image / scan tanpa text.
    """
    if not file_bytes:
        return filename or "unknown.pdf", ""
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
    except (EmptyFileError, PdfReadError, OSError, ValueError):
        return filename or "unknown.pdf", ""

    pages: list[str] = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception:
            pages.append("")
    text = "\n\n".join(pages).strip()
    return filename or "unknown.pdf", text


def extract_text_from_markdown(file_bytes: bytes, filename: str = "") -> tuple[str, str]:
    return extract_text_from_txt(file_bytes, filename)


def extract_text_from_file(file_bytes: bytes, filename: str) -> tuple[str, str]:
    ext = os.path.splitext(filename)[1].lower()
    if ext in (".pdf",):
        return extract_text_from_pdf(file_bytes, filename)
    if ext in (".md", ".markdown"):
        return extract_text_from_markdown(file_bytes, filename)
    # default: perlakukan sebagai text/plain
    return extract_text_from_txt(file_bytes, filename)
