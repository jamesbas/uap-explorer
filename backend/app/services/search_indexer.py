"""Azure AI Search pull-indexer pipeline for UAP PDFs.

Builds and operates a fully Azure-native ingestion path:

    Blob (uap-files)  ──►  Indexer  ──►  Skillset  ──►  Index v2
                                              │
                              ┌───────────────┼───────────────┐
                              ▼               ▼               ▼
                   DocumentIntelligence    SplitSkill    AzureOpenAIEmbedding
                       LayoutSkill        (chunking)        (vectorize)

Index projections write one document per chunk into the v2 index. Query-time
embeddings are produced by an AzureOpenAIVectorizer attached to the vector
profile.

These objects are Search-service-internal (data source, skillset, index,
indexer, vectorizer) and are managed via the Search REST API using the admin
key already configured in settings.

All names are prefixed with ``uap-`` to avoid colliding with other tenants
of the same Search service.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx

from ..config import settings

log = logging.getLogger(__name__)

# ---- Object names ---------------------------------------------------------
DATASOURCE_NAME = "uap-blob-datasource"
SKILLSET_NAME = "uap-skillset"
INDEX_V2_NAME = "uap-explorer-chunks-v2"
INDEXER_NAME = "uap-explorer-indexer"

# ---- Vector / vectorizer config ------------------------------------------
VECTOR_PROFILE_NAME = "uap-v2-vector-profile"
ALGO_NAME = "uap-v2-hnsw"
VECTORIZER_NAME = "uap-v2-aoai-vectorizer"

# Use a preview API version that supports DocumentIntelligenceLayoutSkill
# and AzureOpenAIEmbeddingSkill + integrated vectorization.
API_VERSION = "2024-11-01-preview"


# --------------------------------------------------------------------- HTTP
def _endpoint() -> str:
    if not settings.search_endpoint:
        raise RuntimeError("AZURE_SEARCH_ENDPOINT not set")
    return settings.search_endpoint.rstrip("/")


def _headers() -> Dict[str, str]:
    if not settings.search_admin_key:
        raise RuntimeError("AZURE_SEARCH_ADMIN_KEY not set")
    return {
        "api-key": settings.search_admin_key,
        "Content-Type": "application/json",
    }


def _url(path: str) -> str:
    sep = "&" if "?" in path else "?"
    return f"{_endpoint()}/{path}{sep}api-version={API_VERSION}"


def _put(path: str, body: Dict[str, Any]) -> Dict[str, Any]:
    r = httpx.put(_url(path), headers=_headers(), json=body, timeout=60.0)
    if r.status_code >= 400:
        raise RuntimeError(f"PUT {path} failed: {r.status_code} {r.text}")
    if r.text:
        try:
            return r.json()
        except Exception:  # noqa: BLE001
            return {"status_code": r.status_code, "body": r.text}
    return {"status_code": r.status_code}


def _post(path: str) -> Dict[str, Any]:
    r = httpx.post(_url(path), headers=_headers(), timeout=60.0)
    if r.status_code >= 400:
        raise RuntimeError(f"POST {path} failed: {r.status_code} {r.text}")
    return {"status_code": r.status_code}


def _get(path: str) -> Dict[str, Any]:
    r = httpx.get(_url(path), headers=_headers(), timeout=30.0)
    if r.status_code == 404:
        return {"_not_found": True}
    if r.status_code >= 400:
        raise RuntimeError(f"GET {path} failed: {r.status_code} {r.text}")
    return r.json()


def _delete(path: str) -> Dict[str, Any]:
    r = httpx.delete(_url(path), headers=_headers(), timeout=30.0)
    if r.status_code in (200, 204, 404):
        return {"status_code": r.status_code}
    raise RuntimeError(f"DELETE {path} failed: {r.status_code} {r.text}")


# --------------------------------------------------------------- Definitions
def _data_source_def() -> Dict[str, Any]:
    if not settings.storage_connection_string:
        raise RuntimeError("AZURE_STORAGE_CONNECTION_STRING not set")
    return {
        "name": DATASOURCE_NAME,
        "type": "azureblob",
        "credentials": {"connectionString": settings.storage_connection_string},
        "container": {"name": settings.storage_container},
        "dataChangeDetectionPolicy": {
            "@odata.type": "#Microsoft.Azure.Search.HighWaterMarkChangeDetectionPolicy",
            "highWaterMarkColumnName": "metadata_storage_last_modified",
        },
    }


def _skillset_def() -> Dict[str, Any]:
    """Two-skill pipeline: Split → AOAI embedding.

    PDF text extraction is handled by the blob indexer's native parser
    (``parsingMode: default``) — no OCR skill, no Cognitive Services account
    required. Scanned PDFs without embedded text won't yield content; those
    are best handled by a one-off pre-processing pass.

    - SplitSkill: chunks ``/document/content`` into ~chunk_chars pages with
      200-char overlap.
    - AzureOpenAIEmbeddingSkill: vectorizes each chunk via the configured
      AOAI embedding deployment.

    Index projections in the skillset write one document per chunk into the
    v2 index.
    """
    if not settings.openai_endpoint or not settings.openai_api_key:
        raise RuntimeError("AZURE_OPENAI_ENDPOINT / _API_KEY not set; required for embedding skill")
    if not settings.openai_embedding_deployment:
        raise RuntimeError("AZURE_OPENAI_EMBEDDING_DEPLOYMENT not set")

    return {
        "name": SKILLSET_NAME,
        "description": "UAP pull-ingest: Split + AOAI embedding (native PDF parsing)",
        "skills": [
            {
                "@odata.type": "#Microsoft.Skills.Text.SplitSkill",
                "name": "split",
                "description": "Chunk extracted text for retrieval",
                "context": "/document",
                "textSplitMode": "pages",
                "maximumPageLength": settings.chunk_chars,
                "pageOverlapLength": 200,
                "defaultLanguageCode": "en",
                "inputs": [{"name": "text", "source": "/document/content"}],
                "outputs": [{"name": "textItems", "targetName": "pages"}],
            },
            {
                "@odata.type": "#Microsoft.Skills.Text.AzureOpenAIEmbeddingSkill",
                "name": "embed",
                "description": "Vectorize each chunk via Azure OpenAI",
                "context": "/document/pages/*",
                "resourceUri": settings.openai_endpoint.rstrip("/"),
                "apiKey": settings.openai_api_key,
                "deploymentId": settings.openai_embedding_deployment,
                "modelName": settings.openai_embedding_deployment,
                "dimensions": settings.openai_embedding_dimensions,
                "inputs": [{"name": "text", "source": "/document/pages/*"}],
                "outputs": [{"name": "embedding", "targetName": "content_vector"}],
            },
        ],
        "indexProjections": {
            "selectors": [
                {
                    "targetIndexName": INDEX_V2_NAME,
                    "parentKeyFieldName": "parent_id",
                    "sourceContext": "/document/pages/*",
                    "mappings": [
                        {"name": "content", "source": "/document/pages/*"},
                        {
                            "name": "content_vector",
                            "source": "/document/pages/*/content_vector",
                        },
                        {"name": "title", "source": "/document/metadata_storage_name"},
                        {"name": "source_url", "source": "/document/metadata_storage_path"},
                        {"name": "blob_name", "source": "/document/metadata_storage_name"},
                    ],
                }
            ],
            "parameters": {"projectionMode": "skipIndexingParentDocuments"},
        },
    }


def _index_v2_def() -> Dict[str, Any]:
    return {
        "name": INDEX_V2_NAME,
        "fields": [
            {
                "name": "chunk_id",
                "type": "Edm.String",
                "key": True,
                "filterable": True,
                "sortable": True,
                "analyzer": "keyword",
            },
            {
                "name": "parent_id",
                "type": "Edm.String",
                "filterable": True,
                "sortable": True,
            },
            {
                "name": "blob_name",
                "type": "Edm.String",
                "filterable": True,
                "facetable": True,
            },
            {
                "name": "title",
                "type": "Edm.String",
                "searchable": True,
                "filterable": True,
                "sortable": True,
            },
            {"name": "source_url", "type": "Edm.String"},
            {"name": "content", "type": "Edm.String", "searchable": True},
            {
                "name": "content_vector",
                "type": "Collection(Edm.Single)",
                "searchable": True,
                "retrievable": True,
                "dimensions": settings.openai_embedding_dimensions,
                "vectorSearchProfile": VECTOR_PROFILE_NAME,
            },
        ],
        "vectorSearch": {
            "algorithms": [
                {
                    "name": ALGO_NAME,
                    "kind": "hnsw",
                    "hnswParameters": {
                        "m": 4,
                        "efConstruction": 400,
                        "efSearch": 500,
                        "metric": "cosine",
                    },
                }
            ],
            "profiles": [
                {
                    "name": VECTOR_PROFILE_NAME,
                    "algorithm": ALGO_NAME,
                    "vectorizer": VECTORIZER_NAME,
                }
            ],
            "vectorizers": [
                {
                    "name": VECTORIZER_NAME,
                    "kind": "azureOpenAI",
                    "azureOpenAIParameters": {
                        "resourceUri": settings.openai_endpoint.rstrip("/"),
                        "deploymentId": settings.openai_embedding_deployment,
                        "modelName": settings.openai_embedding_deployment,
                        "apiKey": settings.openai_api_key,
                    },
                }
            ],
        },
    }


def _indexer_def() -> Dict[str, Any]:
    """Indexer config.

    ``maxFailedItems = -1`` keeps the run going past per-blob failures (e.g.
    blobs larger than the tier's per-blob indexer limit, or unparseable
    scanned PDFs with no embedded text).
    """
    return {
        "name": INDEXER_NAME,
        "dataSourceName": DATASOURCE_NAME,
        "skillsetName": SKILLSET_NAME,
        "targetIndexName": INDEX_V2_NAME,
        "parameters": {
            "batchSize": 1,
            "maxFailedItems": -1,
            "maxFailedItemsPerBatch": -1,
            "configuration": {
                "dataToExtract": "contentAndMetadata",
                "parsingMode": "default",
                "indexedFileNameExtensions": ".pdf",
            },
        },
        "fieldMappings": [],
        "outputFieldMappings": [],
    }


# ---------------------------------------------------------------- Operations
def setup_all() -> Dict[str, Any]:
    """Create-or-update data source, index v2, skillset, indexer (in order)."""
    out: Dict[str, Any] = {}
    out["data_source"] = _put(f"datasources/{DATASOURCE_NAME}", _data_source_def())
    out["index_v2"] = _put(f"indexes/{INDEX_V2_NAME}", _index_v2_def())
    out["skillset"] = _put(f"skillsets/{SKILLSET_NAME}", _skillset_def())
    out["indexer"] = _put(f"indexers/{INDEXER_NAME}", _indexer_def())
    log.info("Search indexer setup complete: %s", list(out.keys()))
    return {
        "data_source": DATASOURCE_NAME,
        "index_v2": INDEX_V2_NAME,
        "skillset": SKILLSET_NAME,
        "indexer": INDEXER_NAME,
        "api_version": API_VERSION,
    }


def run() -> Dict[str, Any]:
    """Trigger an indexer run."""
    _post(f"indexers/{INDEXER_NAME}/run")
    return {"started": True, "indexer": INDEXER_NAME}


def reset() -> Dict[str, Any]:
    """Clear indexer change-tracking so the next run reprocesses everything."""
    _post(f"indexers/{INDEXER_NAME}/reset")
    return {"reset": True, "indexer": INDEXER_NAME}


def status() -> Dict[str, Any]:
    """Return current status + last execution summary."""
    raw = _get(f"indexers/{INDEXER_NAME}/status")
    if raw.get("_not_found"):
        return {"exists": False}
    last = raw.get("lastResult") or {}
    return {
        "exists": True,
        "status": raw.get("status"),
        "last_result": {
            "status": last.get("status"),
            "errorMessage": last.get("errorMessage"),
            "startTime": last.get("startTime"),
            "endTime": last.get("endTime"),
            "itemsProcessed": last.get("itemsProcessed"),
            "itemsFailed": last.get("itemsFailed"),
            "errors": last.get("errors", [])[:20],
            "warnings": last.get("warnings", [])[:20],
        },
        "execution_history_count": len(raw.get("executionHistory", [])),
    }


def teardown() -> Dict[str, Any]:
    """Delete indexer, skillset, index v2, and data source (for clean tests)."""
    out = {
        "indexer": _delete(f"indexers/{INDEXER_NAME}"),
        "skillset": _delete(f"skillsets/{SKILLSET_NAME}"),
        "index_v2": _delete(f"indexes/{INDEX_V2_NAME}"),
        "data_source": _delete(f"datasources/{DATASOURCE_NAME}"),
    }
    return out
