"""Chat adapter wrapper."""
from app.memory.models import IngestRequest


def from_chat_message(text: str, chat_id: str) -> IngestRequest:
    return IngestRequest(source_type='chat', source_ref=chat_id, text=text, tags=['chat'])
