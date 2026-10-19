"""Notes adapter wrapper."""
from app.memory.models import IngestRequest


def from_note(text: str, note_path: str) -> IngestRequest:
    return IngestRequest(source_type='note', source_ref=note_path, text=text, tags=['note'])
