"""Text extraction from uploaded case materials (PDF, Word, plain text).

Class negotiation cases arrive as a handful of files: general instructions plus one
confidential sheet per role, sometimes with score tables. We only need their text; the
parser (parser.parse_documents) works out which file is which.
"""

from __future__ import annotations

import io
from pathlib import Path

SUPPORTED = ("pdf", "docx", "txt", "md")


class UnreadableDocument(ValueError):
    pass


def extract_text(name: str, data: bytes) -> str:
    """Plain text of one uploaded file. Raises UnreadableDocument if nothing is extractable
    (for example a scanned PDF with no text layer)."""
    suffix = Path(name).suffix.lower().lstrip(".")
    if suffix in ("pdf", "docx"):
        try:
            text = _pdf(data) if suffix == "pdf" else _docx(data)
        except UnreadableDocument as e:
            raise UnreadableDocument(f"{name}: {e}") from e
    elif suffix in ("txt", "md"):
        text = data.decode("utf-8", errors="replace")
    else:
        raise UnreadableDocument(f"{name}: unsupported file type (use {', '.join(SUPPORTED)})")
    text = text.strip()
    if not text:
        raise UnreadableDocument(
            f"{name}: no text found (a scanned PDF? export it with a text layer or paste it)"
        )
    return text


def _pdf(data: bytes) -> str:
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(data))
        return "\n\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as e:  # noqa: BLE001 - pypdf raises many types on malformed files
        raise UnreadableDocument(f"could not read PDF: {e}") from e


def _docx(data: bytes) -> str:
    import docx

    try:
        document = docx.Document(io.BytesIO(data))
    except Exception as e:  # noqa: BLE001
        raise UnreadableDocument(f"could not read Word file: {e}") from e
    parts = [p.text for p in document.paragraphs]
    # Score tables in class cases are usually Word tables; keep them as tab-separated rows.
    for table in document.tables:
        for row in table.rows:
            parts.append("\t".join(cell.text.strip() for cell in row.cells))
    return "\n".join(parts)
