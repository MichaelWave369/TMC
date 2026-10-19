from __future__ import annotations

import hashlib
from pathlib import Path

from pypdf import PdfReader

from app.memory.models import Capsule, CapsuleKind, IngestRequest


def simple_summary(text: str, max_chars: int = 160) -> str:
    return text.strip().replace("\n", " ")[:max_chars]


def chunk_text(text: str, chunk_size: int = 600, overlap: int = 100) -> list[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = min(len(text), start + chunk_size)
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = max(0, end - overlap)
    return chunks


def parse_file(path: str) -> str:
    p = Path(path)
    if p.suffix.lower() in {".txt", ".md"}:
        return p.read_text(encoding="utf-8")
    if p.suffix.lower() == ".pdf":
        return "\n".join((page.extract_text() or "") for page in PdfReader(path).pages)
    return ""


def build_attachment(path: str, linked_capsule_ids: list[str] | None = None):
    from app.memory.models import Attachment

    p = Path(path)
    b = p.read_bytes()
    extracted = parse_file(path)
    return Attachment(
        capsule_ids=linked_capsule_ids or [],
        filename=p.name,
        mime_type="application/octet-stream",
        size_bytes=len(b),
        sha256=hashlib.sha256(b).hexdigest(),
        attachment_type=p.suffix.lower().lstrip('.') or 'generic',
        extraction_status='complete' if extracted else 'pending',
        extraction_text=extracted,
        local_path=str(p),
    )


def to_capsules(req: IngestRequest) -> list[Capsule]:
    kind = CapsuleKind.identity if req.metadata.get("identity") else CapsuleKind.standard
    out = []
    chunks = chunk_text(req.text)
    for i, t in enumerate(chunks):
        out.append(Capsule(source_type=req.source_type, source_ref=req.source_ref, text=t, summary=simple_summary(t), tags=req.tags, entities=req.entities, importance=req.importance, trust=req.trust, decay_class=req.decay_class, policy=req.policy, kind=kind, profile_id=req.profile_id, workspace_ids=req.workspace_ids, vault_id=req.vault_id, metadata={**req.metadata, "chunk_index": i, "chunk_count": len(chunks)}))
    return out
