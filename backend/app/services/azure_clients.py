"""Factories for Azure SDK clients.

Both API-key and Managed-Identity auth modes are supported. Each factory
raises a clear error if the necessary configuration is missing.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Optional

from ..config import settings


def _credential():
    """Lazy import of azure.identity DefaultAzureCredential."""
    from azure.identity import DefaultAzureCredential

    return DefaultAzureCredential()


# --------------------------------------------------------------------- Blob
@lru_cache(maxsize=1)
def blob_service_client():
    from azure.storage.blob import BlobServiceClient

    if settings.use_managed_identity:
        if not settings.storage_account:
            raise RuntimeError("AZURE_STORAGE_ACCOUNT not set")
        url = f"https://{settings.storage_account}.blob.core.windows.net"
        return BlobServiceClient(account_url=url, credential=_credential())

    if settings.storage_connection_string:
        return BlobServiceClient.from_connection_string(settings.storage_connection_string)

    raise RuntimeError("Set AZURE_STORAGE_CONNECTION_STRING or use AZURE_AUTH_MODE=managed_identity")


# ---------------------------------------------------------------- Search
@lru_cache(maxsize=1)
def search_index_client():
    from azure.core.credentials import AzureKeyCredential
    from azure.search.documents.indexes import SearchIndexClient

    if not settings.search_endpoint:
        raise RuntimeError("AZURE_SEARCH_ENDPOINT not set")

    if settings.use_managed_identity:
        return SearchIndexClient(endpoint=settings.search_endpoint, credential=_credential())
    if not settings.search_admin_key:
        raise RuntimeError("AZURE_SEARCH_ADMIN_KEY not set")
    return SearchIndexClient(
        endpoint=settings.search_endpoint,
        credential=AzureKeyCredential(settings.search_admin_key),
    )


@lru_cache(maxsize=1)
def search_client():
    from azure.core.credentials import AzureKeyCredential
    from azure.search.documents import SearchClient

    if not settings.search_endpoint:
        raise RuntimeError("AZURE_SEARCH_ENDPOINT not set")

    if settings.use_managed_identity:
        return SearchClient(
            endpoint=settings.search_endpoint,
            index_name=settings.search_index_name,
            credential=_credential(),
        )
    if not settings.search_admin_key:
        raise RuntimeError("AZURE_SEARCH_ADMIN_KEY not set")
    return SearchClient(
        endpoint=settings.search_endpoint,
        index_name=settings.search_index_name,
        credential=AzureKeyCredential(settings.search_admin_key),
    )


# ---------------------------------------------------------------- OpenAI
@lru_cache(maxsize=1)
def openai_client():
    from openai import AzureOpenAI

    if not settings.openai_endpoint:
        raise RuntimeError("AZURE_OPENAI_ENDPOINT not set")

    if settings.use_managed_identity:
        from azure.identity import get_bearer_token_provider

        token_provider = get_bearer_token_provider(
            _credential(), "https://cognitiveservices.azure.com/.default"
        )
        return AzureOpenAI(
            azure_endpoint=settings.openai_endpoint,
            api_version=settings.openai_api_version,
            azure_ad_token_provider=token_provider,
        )

    if not settings.openai_api_key:
        raise RuntimeError("AZURE_OPENAI_API_KEY not set")
    return AzureOpenAI(
        azure_endpoint=settings.openai_endpoint,
        api_version=settings.openai_api_version,
        api_key=settings.openai_api_key,
    )


# -------------------------------------------------------- Document Intelligence
@lru_cache(maxsize=1)
def document_intelligence_client():
    from azure.ai.documentintelligence import DocumentIntelligenceClient
    from azure.core.credentials import AzureKeyCredential

    if not settings.docintel_endpoint:
        raise RuntimeError("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT not set")

    if settings.use_managed_identity:
        return DocumentIntelligenceClient(
            endpoint=settings.docintel_endpoint, credential=_credential()
        )
    if not settings.docintel_key:
        raise RuntimeError("AZURE_DOCUMENT_INTELLIGENCE_KEY not set")
    return DocumentIntelligenceClient(
        endpoint=settings.docintel_endpoint,
        credential=AzureKeyCredential(settings.docintel_key),
    )
