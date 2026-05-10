"""Azure AI Search index management + retrieval."""
from __future__ import annotations

import logging
from typing import Iterable, List, Optional

from ..config import settings
from .azure_clients import search_client, search_index_client

log = logging.getLogger(__name__)

VECTOR_PROFILE_NAME = "uap-vector-profile"
ALGO_NAME = "uap-hnsw"


def _index_definition():
    """Build the SearchIndex definition. Lazy-imported to keep startup fast."""
    from azure.search.documents.indexes.models import (
        HnswAlgorithmConfiguration,
        SearchableField,
        SearchField,
        SearchFieldDataType,
        SearchIndex,
        SimpleField,
        VectorSearch,
        VectorSearchProfile,
    )

    fields = [
        SimpleField(name="chunk_id", type=SearchFieldDataType.String, key=True, filterable=True),
        SimpleField(name="document_id", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SearchableField(name="title", type=SearchFieldDataType.String, filterable=True, sortable=True),
        SimpleField(name="agency", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SimpleField(name="release_date", type=SearchFieldDataType.String, filterable=True, sortable=True),
        SimpleField(name="incident_date", type=SearchFieldDataType.String, filterable=True, sortable=True),
        SearchableField(name="location", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SimpleField(name="page_number", type=SearchFieldDataType.Int32, filterable=True, sortable=True),
        SimpleField(name="chunk_index", type=SearchFieldDataType.Int32, filterable=True, sortable=True),
        SearchableField(name="content", type=SearchFieldDataType.String),
        SearchField(
            name="content_vector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=settings.openai_embedding_dimensions,
            vector_search_profile_name=VECTOR_PROFILE_NAME,
        ),
        SimpleField(name="source_url", type=SearchFieldDataType.String),
    ]

    vector_search = VectorSearch(
        algorithms=[HnswAlgorithmConfiguration(name=ALGO_NAME)],
        profiles=[VectorSearchProfile(name=VECTOR_PROFILE_NAME, algorithm_configuration_name=ALGO_NAME)],
    )

    return SearchIndex(name=settings.search_index_name, fields=fields, vector_search=vector_search)


def index_exists() -> bool:
    try:
        search_index_client().get_index(settings.search_index_name)
        return True
    except Exception:
        return False


def create_or_update_index() -> dict:
    """Create the index if missing, or update it in place."""
    client = search_index_client()
    idx = _index_definition()
    result = client.create_or_update_index(idx)
    log.info("Index '%s' created/updated", result.name)
    return {"name": result.name, "fields": [f.name for f in result.fields]}


def delete_index() -> None:
    client = search_index_client()
    try:
        client.delete_index(settings.search_index_name)
    except Exception as e:  # noqa: BLE001
        log.warning("Delete index failed (may not exist): %s", e)


def recreate_index() -> dict:
    delete_index()
    return create_or_update_index()


def upload_chunks(chunks: List[dict]) -> int:
    """Upload chunks in batches of 500."""
    client = search_client()
    total = 0
    BATCH = 500
    for i in range(0, len(chunks), BATCH):
        batch = chunks[i : i + BATCH]
        client.upload_documents(documents=batch)
        total += len(batch)
    return total


def delete_document_chunks(document_id: str) -> int:
    """Remove all chunks for a given document_id."""
    client = search_client()
    results = client.search(
        search_text="*",
        filter=f"document_id eq '{document_id}'",
        select=["chunk_id"],
        top=1000,
    )
    ids = [{"chunk_id": r["chunk_id"]} for r in results]
    if ids:
        client.delete_documents(documents=ids)
    return len(ids)


def hybrid_search(
    query: str,
    query_vector: List[float],
    top: int = 8,
    document_id: Optional[str] = None,
) -> list[dict]:
    from azure.search.documents.models import VectorizedQuery

    client = search_client()
    vector_query = VectorizedQuery(
        vector=query_vector, k_nearest_neighbors=top, fields="content_vector"
    )

    kwargs: dict = {
        "search_text": query,
        "vector_queries": [vector_query],
        "top": top,
        "select": [
            "chunk_id",
            "document_id",
            "title",
            "agency",
            "page_number",
            "content",
            "source_url",
            "release_date",
            "incident_date",
            "location",
        ],
    }
    if document_id:
        kwargs["filter"] = f"document_id eq '{document_id}'"

    results = client.search(**kwargs)
    return [dict(r) for r in results]


def get_document_chunks(document_id: str, max_chunks: int = 200) -> list[dict]:
    client = search_client()
    results = client.search(
        search_text="*",
        filter=f"document_id eq '{document_id}'",
        select=["chunk_id", "page_number", "chunk_index", "content"],
        order_by=["page_number asc", "chunk_index asc"],
        top=max_chunks,
    )
    return [dict(r) for r in results]


def index_stats() -> dict:
    """Return basic stats: doc count + unique source documents."""
    client = search_client()
    try:
        count = client.get_document_count()
    except Exception:
        count = None
    return {
        "index_name": settings.search_index_name,
        "exists": index_exists(),
        "chunk_count": count,
    }
