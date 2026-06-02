import os
from pathlib import Path
from dotenv import load_dotenv

# Define local project paths
BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
LINKER_ENV_PATH = BASE_DIR.parent / "obsidian-linker" / ".env"

# Copy .env from obsidian-linker if it exists and doesn't exist here
if not ENV_PATH.exists() and LINKER_ENV_PATH.exists():
    try:
        ENV_PATH.write_text(LINKER_ENV_PATH.read_text(encoding="utf-8"), encoding="utf-8")
        print("[CONFIG] Copied .env successfully from obsidian-linker project.")
    except Exception as e:
        print(f"[CONFIG] Warning: Could not copy .env from obsidian-linker: {e}")

# Load environment variables
load_dotenv(dotenv_path=ENV_PATH)

# Directory configurations
INPUT_PDF_DIR = BASE_DIR / "inputPDF"
INPUT_PDF_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_TEXT = OUTPUT_DIR / "output.txt"

# Default Obsidian Vault directory (can be overridden in environment)
OBSIDIAN_VAULT_DIR = Path(os.getenv("OBSIDIAN_VAULT_DIR", r"C:\Users\saraf\Documents\VOID"))
OBSIDIAN_CACHE_FILE = OBSIDIAN_VAULT_DIR / ".linker_cache.json"

# Local vector index storage
VECTORSTORE_DIR = BASE_DIR / "faiss_index"
FAISS_INDEX_FILE = VECTORSTORE_DIR / "index.faiss"

# Model configurations
EMBEDDING_MODEL = "models/gemini-embedding-2"
LLM_MODEL = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")

# RAG and Chunking configurations
RETRIEVAL_K = 3
CHUNK_SIZE = 500
CHUNK_OVERLAP = 100
MIN_IMAGE_SIZE = 150
