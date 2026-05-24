"""Configuration for UAP Explorer backend."""
from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

# backend/app/config.py -> parents[2] is repo root
REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = Path(__file__).resolve().parents[1]

# Load backend/.env first (preferred for Phase 2 secrets), then repo-root .env
load_dotenv(BACKEND_ROOT / ".env")
load_dotenv(REPO_ROOT / ".env")


def _resolve(env_value: str | None, default_rel: str) -> Path:
    if env_value:
        p = Path(env_value)
        if not p.is_absolute():
            p = (REPO_ROOT / p).resolve()
        return p
    return (REPO_ROOT / default_rel).resolve()


class Settings:
    # Core
    app_env: str = os.getenv("APP_ENV", "local")
    frontend_url: str = os.getenv("FRONTEND_URL", "http://localhost:5173")
    backend_host: str = os.getenv("BACKEND_HOST", "0.0.0.0")
    backend_port: int = int(os.getenv("BACKEND_PORT", "8000"))

    # Data paths
    csv_path: Path = _resolve(os.getenv("UAP_CSV_PATH"), "data/source/uap-csv.csv")
    file_root: Path = _resolve(os.getenv("UAP_FILE_ROOT"), "ufo_release_01_files")
    # Additional release folders to search when resolving a record's local file.
    # Comma-separated env var; defaults include both known release folders.
    file_roots: list[Path] = [
        _resolve(p, p)
        for p in (
            os.getenv("UAP_FILE_ROOTS")
            or "ufo_release_01_files,ufo_release_02_files"
        ).split(",")
        if p.strip()
    ]
    processed_root: Path = _resolve(os.getenv("UAP_PROCESSED_ROOT"), "data/processed")

    # Admin
    admin_password: str = os.getenv("ADMIN_PASSWORD", "")

    # Azure auth mode: "key" or "managed_identity"
    azure_auth_mode: str = os.getenv("AZURE_AUTH_MODE", "key").strip().lower()

    # Blob
    storage_account: str = os.getenv("AZURE_STORAGE_ACCOUNT", "")
    storage_container: str = os.getenv("AZURE_STORAGE_CONTAINER", "uap-files")
    storage_connection_string: str = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "")

    # Search
    search_endpoint: str = os.getenv("AZURE_SEARCH_ENDPOINT", "")
    search_admin_key: str = os.getenv("AZURE_SEARCH_ADMIN_KEY", "")
    search_index_name: str = os.getenv("AZURE_SEARCH_INDEX_NAME", "uap-explorer-chunks")

    # OpenAI / Foundry
    openai_endpoint: str = os.getenv("AZURE_OPENAI_ENDPOINT", "")
    openai_api_key: str = os.getenv("AZURE_OPENAI_API_KEY", "")
    openai_api_version: str = os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
    openai_deployment: str = os.getenv("AZURE_OPENAI_DEPLOYMENT", "")
    openai_embedding_deployment: str = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "")
    openai_embedding_dimensions: int = int(
        os.getenv("AZURE_OPENAI_EMBEDDING_DIMENSIONS", "3072")
    )

    # Document Intelligence
    docintel_endpoint: str = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT", "")
    docintel_key: str = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY", "")

    # Ingestion
    ingestion_max_docs: int = int(os.getenv("INGESTION_MAX_DOCS", "30"))
    chunk_chars: int = int(os.getenv("INGESTION_CHUNK_CHARS", "1500"))
    chunk_overlap: int = int(os.getenv("INGESTION_CHUNK_OVERLAP", "200"))
    # Files larger than this are skipped by the ingestion pipeline rather
    # than risk hanging pypdf / Doc Intelligence. They can be processed
    # offline with a dedicated splitter.
    ingestion_max_pdf_mb: int = int(os.getenv("INGESTION_MAX_PDF_MB", "80"))
    # Wall-clock cap on the entire extract_pages() call (pypdf + DI).
    # Acts as a safety net beyond the per-service timeouts.
    ingestion_extract_timeout_seconds: int = int(
        os.getenv("INGESTION_EXTRACT_TIMEOUT_SECONDS", "420")
    )

    @property
    def use_managed_identity(self) -> bool:
        return self.azure_auth_mode == "managed_identity"


settings = Settings()
settings.processed_root.mkdir(parents=True, exist_ok=True)
(settings.processed_root / "summaries").mkdir(parents=True, exist_ok=True)
(settings.processed_root / "extracted").mkdir(parents=True, exist_ok=True)

