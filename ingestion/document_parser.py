import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from pypdf import PdfReader


CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "500"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "100"))


@dataclass
class DocumentChunk:
    chunk_id: str
    text: str
    source_document: str
    service: str
    issue_type: str
    recommendation: str


def _extract_markdown(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _extract_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _extract_pdf(path: Path) -> str:
    reader = PdfReader(str(path))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n\n".join(pages)


def extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".md":
        return _extract_markdown(path)
    elif suffix == ".txt":
        return _extract_text(path)
    elif suffix == ".pdf":
        return _extract_pdf(path)
    raise ValueError(f"Unsupported document format: {suffix}")


def clean_text(text: str) -> str:
    text = re.sub(r"```[^\n]*\n", "", text)
    text = re.sub(r"```", "", text)
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^[-*_]{3,}\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\|[-| :]+\|$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _infer_service(text: str) -> str:
    text_lower = text.lower()
    if any(k in text_lower for k in ("ebs", "gp2", "gp3", "volume")):
        return "EBS"
    if any(k in text_lower for k in ("ec2", "instance", "rightsizing")):
        return "EC2"
    if any(k in text_lower for k in ("rds", "database")):
        return "RDS"
    return "AWS"


def _infer_issue_type(text: str) -> str:
    text_lower = text.lower()
    if "gp2" in text_lower and any(k in text_lower for k in ("gp3", "migration", "storage")):
        return "LEGACY_STORAGE"
    if any(k in text_lower for k in ("unattached", "orphaned", "available")):
        return "ORPHANED_STORAGE"
    if any(k in text_lower for k in ("idle", "cpu", "utilization", "rightsizing")):
        return "IDLE_RESOURCE"
    return "COST_OPTIMIZATION"


def _extract_recommendation(text: str) -> str:
    rec_match = re.search(r"recommendation[:\s]+([^\n\.]+[\.]?)", text, flags=re.IGNORECASE)
    if rec_match:
        return rec_match.group(1).strip()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if lines:
        return lines[0][:150]
    return "Evaluate resource configuration for AWS cost optimization."


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    chunks = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = min(start + chunk_size, text_len)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= text_len:
            break
        step = max(1, chunk_size - overlap)
        start += step

    return chunks


def parse_document(path: Path, s3_key: Optional[str] = None) -> list[DocumentChunk]:
    source_document = s3_key if s3_key else path.name
    raw_text = extract_text(path)
    cleaned_text = clean_text(raw_text)

    if not cleaned_text:
        return []

    raw_chunks = chunk_text(cleaned_text)
    chunks = []

    for idx, chunk_text_content in enumerate(raw_chunks):
        chunk_id = f"{path.stem}_chunk_{idx:04d}"
        chunks.append(
            DocumentChunk(
                chunk_id=chunk_id,
                text=chunk_text_content,
                source_document=source_document,
                service=_infer_service(chunk_text_content),
                issue_type=_infer_issue_type(chunk_text_content),
                recommendation=_extract_recommendation(chunk_text_content),
            )
        )

    return chunks


def parse_documents_from_paths(paths: list[Path]) -> list[DocumentChunk]:
    all_chunks = []
    for path in paths:
        try:
            chunks = parse_document(path)
            all_chunks.extend(chunks)
        except Exception as e:
            print(f"Error parsing {path.name}: {e}")
    return all_chunks
