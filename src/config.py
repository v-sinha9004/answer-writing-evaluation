"""Configuration module for RAG and UPSC evaluation pipeline."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root
ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=ROOT_DIR / ".env")

# OpenAI Settings
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
EMBEDDING_DIMENSIONS = int(os.getenv("EMBEDDING_DIMENSIONS", "1536"))

# Storage & Paths
DATA_DIR = ROOT_DIR / "data"
CHROMA_PERSIST_DIR = Path(os.getenv("CHROMA_PERSIST_DIR", str(DATA_DIR / "chromadb")))
BM25_PERSIST_DIR = Path(os.getenv("BM25_PERSIST_DIR", str(DATA_DIR / "bm25")))
RESOURCES_DIR = DATA_DIR / "resources" / "gs1_modern_history"

# Spectrum PDF Source (checks resources dir first, then repo root)
_local_resource_pdf = RESOURCES_DIR / "gs1_modern_history_spectrum.pdf"
_root_resource_pdf = ROOT_DIR / "gs1_modern_history_spectrum.pdf"
SPECTRUM_PDF_PATH = _local_resource_pdf if _local_resource_pdf.exists() else _root_resource_pdf

# Collection & Chunking Defaults
DEFAULT_COLLECTION_NAME = "gs1_modern_history"
CHUNK_SIZE_TOKENS = 600
CHUNK_OVERLAP_TOKENS = 120
BATCH_SIZE = 100

def ensure_directories():
    """Ensure persistent storage directories exist."""
    CHROMA_PERSIST_DIR.mkdir(parents=True, exist_ok=True)
    BM25_PERSIST_DIR.mkdir(parents=True, exist_ok=True)
    RESOURCES_DIR.mkdir(parents=True, exist_ok=True)
