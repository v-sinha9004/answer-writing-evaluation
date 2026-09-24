"""Configuration module for RAG and UPSC evaluation pipeline."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root
ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=ROOT_DIR / ".env")

# OpenAI Settings
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Langfuse Observability Settings
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "").strip()
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "").strip()
LANGFUSE_HOST = (os.getenv("LANGFUSE_HOST") or os.getenv("LANGFUSE_BASE_URL") or "https://cloud.langfuse.com").strip()
LANGFUSE_ENVIRONMENT = (
    os.getenv("LANGFUSE_ENVIRONMENT")
    or os.getenv("LANGFUSE_TRACING_ENVIRONMENT")
    or os.getenv("ENVIRONMENT")
    or "development"
).strip().lower()

# Ensure standard env vars are populated for Langfuse SDK
os.environ["LANGFUSE_HOST"] = LANGFUSE_HOST
os.environ["LANGFUSE_BASEURL"] = LANGFUSE_HOST
os.environ["LANGFUSE_TRACING_ENVIRONMENT"] = LANGFUSE_ENVIRONMENT
os.environ["LANGFUSE_ENVIRONMENT"] = LANGFUSE_ENVIRONMENT

def is_langfuse_enabled() -> bool:
    """Check if Langfuse credentials are configured."""
    return bool(LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY)

# Default Agent Model
_env_model = (os.getenv("OPENAI_MODEL") or os.getenv("AGENT_MODEL") or os.getenv("EVALUATION_MODEL") or "").strip()
OPENAI_MODEL = _env_model if _env_model else "gpt-4o"
AGENT_MODEL = OPENAI_MODEL
EVALUATION_MODEL = OPENAI_MODEL

# Per-Agent Model Configurations
DEMAND_AGENT_MODEL = (os.getenv("DEMAND_AGENT_MODEL") or "").strip() or AGENT_MODEL
INTRO_AGENT_MODEL = (os.getenv("INTRO_AGENT_MODEL") or "").strip() or AGENT_MODEL
STRUCTURE_AGENT_MODEL = (os.getenv("STRUCTURE_AGENT_MODEL") or "").strip() or AGENT_MODEL
CONCLUSION_AGENT_MODEL = (os.getenv("CONCLUSION_AGENT_MODEL") or "").strip() or AGENT_MODEL
FACT_AGENT_MODEL = (os.getenv("FACT_AGENT_MODEL") or "").strip() or AGENT_MODEL
MASTER_ARBITER_MODEL = (os.getenv("MASTER_ARBITER_MODEL") or "").strip() or AGENT_MODEL
VISION_AGENT_MODEL = (os.getenv("VISION_AGENT_MODEL") or "").strip() or AGENT_MODEL

def get_agent_models() -> dict[str, str]:
    """Return the configured models for each agent."""
    return {
        "demand": DEMAND_AGENT_MODEL,
        "intro": INTRO_AGENT_MODEL,
        "structure": STRUCTURE_AGENT_MODEL,
        "conclusion": CONCLUSION_AGENT_MODEL,
        "fact": FACT_AGENT_MODEL,
        "master_arbiter": MASTER_ARBITER_MODEL,
        "vision": VISION_AGENT_MODEL,
    }

# Embedding Settings
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
EMBEDDING_DIMENSIONS = int(os.getenv("EMBEDDING_DIMENSIONS", "1536"))

# Storage & Paths
DATA_DIR = ROOT_DIR / "data"
DATABASE_PATH = Path(os.getenv("DATABASE_PATH", str(DATA_DIR / "evaluations.db")))
CHROMA_PERSIST_DIR = Path(os.getenv("CHROMA_PERSIST_DIR", str(DATA_DIR / "chromadb")))
BM25_PERSIST_DIR = Path(os.getenv("BM25_PERSIST_DIR", str(DATA_DIR / "bm25")))
RESOURCES_DIR = DATA_DIR / "resources"
ROOT_RESOURCES_DIR = ROOT_DIR / "resources"



# Collection & Chunking Defaults
DEFAULT_COLLECTION_NAME = os.getenv("DEFAULT_COLLECTION_NAME", "upsc_knowledge_base")
CHUNK_SIZE_TOKENS = 600
CHUNK_OVERLAP_TOKENS = 120
BATCH_SIZE = 100

def get_resource_search_paths() -> list[Path]:
    """Return all directories to search for syllabus resource PDFs."""
    paths = []
    if RESOURCES_DIR.exists():
        paths.append(RESOURCES_DIR)
    if ROOT_RESOURCES_DIR.exists():
        paths.append(ROOT_RESOURCES_DIR)
    if not paths:
        paths.append(RESOURCES_DIR)
    return paths

def ensure_directories():
    """Ensure persistent storage directories exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CHROMA_PERSIST_DIR.mkdir(parents=True, exist_ok=True)
    BM25_PERSIST_DIR.mkdir(parents=True, exist_ok=True)
    RESOURCES_DIR.mkdir(parents=True, exist_ok=True)

