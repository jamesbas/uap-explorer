"""In-memory document store loaded once at startup."""
from __future__ import annotations

from typing import Dict, List, Optional

from ..config import settings
from ..models import DocumentRecord
from .csv_loader import load_documents


class DocumentStore:
    def __init__(self) -> None:
        self._docs: List[DocumentRecord] = []
        self._by_id: Dict[str, DocumentRecord] = {}

    def load(self) -> None:
        self._docs = load_documents(settings.csv_path, settings.file_root)
        self._by_id = {d.document_id: d for d in self._docs}

    @property
    def documents(self) -> List[DocumentRecord]:
        return self._docs

    def get(self, document_id: str) -> Optional[DocumentRecord]:
        return self._by_id.get(document_id)


store = DocumentStore()
