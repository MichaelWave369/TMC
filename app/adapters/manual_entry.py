"""Manual adapter helpers."""
from app.memory.models import IngestRequest


def from_text(text: str, source_ref: str = 'manual') -> IngestRequest:
    return IngestRequest(source_type='manual', source_ref=source_ref, text=text)
