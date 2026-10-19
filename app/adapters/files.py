"""File adapter wrapper."""
from app.core.service import MemoryService


def ingest_path(service: MemoryService, path: str):
    return service.ingest_file(path, source_type='file')
