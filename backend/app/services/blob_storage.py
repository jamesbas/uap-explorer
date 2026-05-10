"""Blob storage helpers — upload originals, stream them back through the API."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable, Optional, Tuple

from ..config import settings
from .azure_clients import blob_service_client

log = logging.getLogger(__name__)


def _container():
    bsc = blob_service_client()
    container = bsc.get_container_client(settings.storage_container)
    try:
        container.create_container()
    except Exception:
        # Already exists
        pass
    return container


def upload_file(local_path: Path, blob_name: Optional[str] = None) -> str:
    """Upload a local file to blob storage; returns blob name."""
    name = blob_name or local_path.name
    container = _container()
    with local_path.open("rb") as fh:
        container.upload_blob(name=name, data=fh, overwrite=True)
    return name


def blob_exists(blob_name: str) -> bool:
    try:
        return _container().get_blob_client(blob_name).exists()
    except Exception:
        return False


def download_blob_stream(blob_name: str) -> Tuple[Iterable[bytes], int | None]:
    """Return (chunks_iterator, content_length)."""
    blob = _container().get_blob_client(blob_name)
    stream = blob.download_blob()
    size = stream.size
    return stream.chunks(), size


def download_blob_bytes(blob_name: str) -> bytes:
    blob = _container().get_blob_client(blob_name)
    return blob.download_blob().readall()


def list_blobs() -> list[str]:
    return [b.name for b in _container().list_blobs()]
