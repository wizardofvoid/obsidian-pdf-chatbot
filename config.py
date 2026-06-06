import os
import logging
from pathlib import Path
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Define local project paths
BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
LINKER_ENV_PATH = BASE_DIR.parent / "obsidian-linker" / ".env"

# Load environment variables
load_dotenv(dotenv_path=ENV_PATH)

# Directory configurations
INPUT_PDF_DIR = BASE_DIR / "inputPDF"

OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_TEXT = OUTPUT_DIR / "output.txt"

# Default Obsidian Vault directory (can be overridden in environment)
# Fallback to an 'ObsidianVault' folder inside the project if not set in .env
OBSIDIAN_VAULT_DIR = Path(os.getenv("OBSIDIAN_VAULT_DIR", str(BASE_DIR / "ObsidianVault")))
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


def init() -> None:
    """Initialize config: ensure .env is copied and required directories exist."""
    if not ENV_PATH.exists() and LINKER_ENV_PATH.exists():
        try:
            ENV_PATH.write_text(LINKER_ENV_PATH.read_text(encoding="utf-8"), encoding="utf-8")
            logger.info("Copied .env successfully from obsidian-linker project.")
        except Exception as e:
            logger.warning(f"Could not copy .env from obsidian-linker: {e}")

    INPUT_PDF_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
