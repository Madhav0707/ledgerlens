import csv
import io
from dataclasses import dataclass
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import Document, DocumentChunk

MAX_FILE_SIZE = 10 * 1024 * 1024
ALLOWED_TYPES = {"pdf", "csv"}


@dataclass(frozen=True)
class ExtractedDocument:
    filename: str
    file_type: str
    text: str
    pages: tuple[tuple[int | None, str], ...]


def extract_document(filename: str, data: bytes) -> ExtractedDocument:
    suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if suffix not in ALLOWED_TYPES:
        raise ValueError("Only PDF and CSV files are supported.")
    if not data:
        raise ValueError("The uploaded document is empty.")
    if len(data) > MAX_FILE_SIZE:
        raise ValueError("The document exceeds the 10 MB limit.")

    if suffix == "csv":
        try:
            rows = csv.reader(io.StringIO(data.decode("utf-8-sig")))
            text = "\n".join(" | ".join(row) for row in rows)
        except UnicodeDecodeError as error:
            raise ValueError("CSV must be UTF-8 encoded.") from error
        return ExtractedDocument(filename, suffix, text.strip(), ((None, text.strip()),))

    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(data))
        pages = tuple((index + 1, page.extract_text() or "") for index, page in enumerate(reader.pages))
    except Exception as error:
        raise ValueError("The PDF could not be read.") from error
    text = "\n\n".join(page_text for _, page_text in pages).strip()
    if not text:
        raise ValueError("No extractable text was found in the PDF.")
    return ExtractedDocument(filename, suffix, text, pages)


def save_document(session: Session, *, business_id: int, extracted: ExtractedDocument) -> Document:
    document = Document(
        business_id=business_id,
        filename=extracted.filename,
        file_type=extracted.file_type,
        content_text=extracted.text,
    )
    session.add(document)
    session.flush()
    chunk_size = 1200
    chunk_index = 0
    for page_number, page_text in extracted.pages:
        words = page_text.split()
        for start in range(0, len(words), chunk_size):
            content = " ".join(words[start:start + chunk_size]).strip()
            if content:
                session.add(DocumentChunk(
                    business_id=business_id,
                    document_id=document.id,
                    chunk_index=chunk_index,
                    page_number=page_number,
                    content=content,
                ))
                chunk_index += 1
    session.flush()
    return document


INSTRUCTION_PATTERN = re.compile(
    r"(?:ignore|disregard|forget)\s+(?:all\s+)?(?:previous|prior|above)\s+instructions?[^.!?\n]*(?:[.!?]|$)|"
    r"(?:system|developer)\s+message\s*:[^.!?\n]*(?:[.!?]|$)",
    re.IGNORECASE,
)


def search_chunks(session: Session, *, business_id: int, query: str) -> list[DocumentChunk]:
    terms = {term.lower() for term in query.split() if len(term) > 2}
    chunks = session.scalars(
        select(DocumentChunk).where(DocumentChunk.business_id == business_id)
    ).all()
    ranked = []
    for chunk in chunks:
        content = chunk.content.lower()
        score = sum(content.count(term) for term in terms)
        if score:
            ranked.append((score, chunk))
    ranked.sort(key=lambda item: (-item[0], item[1].chunk_index))
    return [chunk for _, chunk in ranked[:5]]


def safe_document_context(chunks: list[DocumentChunk]) -> str:
    """Format retrieved text as untrusted evidence, never as instructions."""
    sections = []
    for chunk in chunks:
        content = INSTRUCTION_PATTERN.sub("[instruction-like text removed]", chunk.content)
        sections.append(
            f"SOURCE document_id={chunk.document_id} page={chunk.page_number or 'N/A'}\n{content}"
        )
    return "\n\n---\n\n".join(sections)