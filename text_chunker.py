import os
import re
import logging
import time
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings

load_dotenv()

from config import OUTPUT_DIR, CHUNK_SIZE, CHUNK_OVERLAP, EMBEDDING_MODEL, INPUT_PDF_DIR, PINECONE_API_KEY, PINECONE_INDEX_NAME
from pinecone import Pinecone as PineconeClient
from langchain_pinecone import PineconeVectorStore


def chunk_all_text_files(input_dir: str, chunk_size: int, chunk_overlap: int, target_sources: set[str] = None) -> list[Document]:
    """
    Reads cached text files for active PDFs, splits them into token-aware chunks,
    and preserves file name and page number metadata.
    """
    input_pdf_dir = Path(INPUT_PDF_DIR)
    cache_dir = Path(input_dir) / "cache"

    if not input_pdf_dir.exists() or not input_pdf_dir.is_dir():
        logger.error("PDF directory not found: %s", input_pdf_dir.absolute())
        return []

    if not cache_dir.exists() or not cache_dir.is_dir():
        logger.error("Cache directory not found: %s", cache_dir.absolute())
        return []

    texts = []
    metadatas = []

    pdf_paths = sorted(input_pdf_dir.glob("*.pdf"))
    if not pdf_paths:
        logger.warning("No PDF files found to index.")
        return []

    for pdf_path in pdf_paths:
        if target_sources is not None and pdf_path.name not in target_sources:
            continue

        cache_file_true = cache_dir / f"{pdf_path.name}_ocr_True.txt"
        cache_file_false = cache_dir / f"{pdf_path.name}_ocr_False.txt"

        cache_file = None
        if cache_file_true.exists() and cache_file_false.exists():
            cache_file = cache_file_true if cache_file_true.stat().st_mtime >= cache_file_false.stat().st_mtime else cache_file_false
        elif cache_file_true.exists():
            cache_file = cache_file_true
        elif cache_file_false.exists():
            cache_file = cache_file_false

        if not cache_file:
            logger.warning("No cached text found for: %s", pdf_path.name)
            continue

        logger.info("Parsing cache file: %s", cache_file.name)
        try:
            content = cache_file.read_text(encoding="utf-8")
            pattern = r"--- Page (\d+) ---\n"
            parts = re.split(pattern, content)

            pages = []
            if len(parts) > 1:
                for i in range(1, len(parts), 2):
                    page_num = int(parts[i])
                    page_text = parts[i + 1].strip()
                    if page_text:
                        pages.append((page_num, page_text))

            if not pages and content.strip():
                pages.append((1, content.strip()))

            for page_num, page_text in pages:
                texts.append(page_text)
                metadatas.append({"source": pdf_path.name, "page": page_num})
        except Exception as e:
            logger.error("Failed to read or parse cache for %s: %s", pdf_path.name, e)

    if not texts:
        logger.warning("No text segments found to chunk.")
        return []

    logger.info("Initializing token-aware text splitter (Size: %s, Overlap: %s)...", chunk_size, chunk_overlap)
    splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        encoding_name="cl100k_base",
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""]
    )

    logger.info("Splitting text into metadata-aware documents...")
    docs = splitter.create_documents(texts, metadatas=metadatas)
    return docs


def _get_google_keys() -> list[str]:
    keys = []
    if os.getenv("GOOGLE_API_KEY"):
        keys.append(os.getenv("GOOGLE_API_KEY"))
    for i in range(1, 10):
        k = os.getenv(f"GOOGLE_API_KEY_{i}")
        if k and k not in keys:
            keys.append(k)
    if not keys:
        raise ValueError("No GOOGLE_API_KEY or GOOGLE_API_KEY_N found in .env")
    return keys


def _embed_with_retry(batch: list[str], max_retries: int = 8) -> list:
    """
    Embed a batch of texts using embed_documents() with key rotation and backoff.
    """
    keys = _get_google_keys()
    key_idx = 0
    
    for attempt in range(max_retries):
        api_key = keys[key_idx]
        try:
            embeddings_model = GoogleGenerativeAIEmbeddings(model=EMBEDDING_MODEL, google_api_key=api_key)
            return embeddings_model.embed_documents(batch)
        except Exception as e:
            err_msg = str(e).lower()
            if "rate limit" in err_msg or "429" in err_msg or "resource_exhausted" in err_msg or "quota" in err_msg:
                if len(keys) > 1:
                    old_idx = key_idx
                    key_idx = (key_idx + 1) % len(keys)
                    logger.warning(
                        "Google embedding rate limit hit (429). Rotating key: %s -> %s",
                        old_idx + 1, key_idx + 1
                    )
                    time.sleep(2)
                    continue
                else:
                    delay = 5 * (2 ** attempt)
                    logger.warning(
                        "Rate limit on batch embed (attempt %s/%s). Backing off %ss...",
                        attempt + 1, max_retries, delay
                    )
                    time.sleep(delay)
                    continue
            raise
    raise RuntimeError(f"Embedding failed after {max_retries} attempts.")


def create_vectorstore(docs: list[Document]):
    """
    Generates embeddings for documents in batches and upserts to Pinecone.
    Uses embed_documents() for O(n/batch) API calls instead of O(n).
    """
    if not docs:
        return None

    chunks = [doc.page_content for doc in docs]
    metadatas = [doc.metadata for doc in docs]

    # --- Batch embedding: single API call per batch instead of one per chunk ---
    EMBED_BATCH_SIZE = 50  # Gemini supports up to 100 texts per embed_documents call
    all_embeddings = []

    logger.info("Generating embeddings for %s chunks in batches of %s...", len(chunks), EMBED_BATCH_SIZE)
    for i in range(0, len(chunks), EMBED_BATCH_SIZE):
        batch = chunks[i: i + EMBED_BATCH_SIZE]
        logger.info("  Embedding batch %s/%s (%s chunks)...",
                    i // EMBED_BATCH_SIZE + 1,
                    (len(chunks) + EMBED_BATCH_SIZE - 1) // EMBED_BATCH_SIZE,
                    len(batch))
        try:
            batch_embeddings = _embed_with_retry(batch)
            all_embeddings.extend(batch_embeddings)
        except Exception as e:
            logger.error("Failed to embed batch starting at chunk %s: %s", i, e)
            return False

    logger.info("All %s embeddings generated successfully.", len(all_embeddings))

    # --- Pinecone upsert in batches of 200 ---
    try:
        import uuid
        pc = PineconeClient(api_key=PINECONE_API_KEY)
        index = pc.Index(PINECONE_INDEX_NAME)

        UPSERT_BATCH_SIZE = 200
        total_upserted = 0
        for i in range(0, len(chunks), UPSERT_BATCH_SIZE):
            batch_chunks = chunks[i: i + UPSERT_BATCH_SIZE]
            batch_embs = all_embeddings[i: i + UPSERT_BATCH_SIZE]
            batch_meta = metadatas[i: i + UPSERT_BATCH_SIZE]

            vectors = []
            for chunk_text, emb, meta in zip(batch_chunks, batch_embs, batch_meta):
                meta_with_text = {**meta, "text": chunk_text}
                vectors.append((str(uuid.uuid4()), emb, meta_with_text))

            index.upsert(vectors=vectors, namespace="pdfs")
            total_upserted += len(vectors)
            logger.info("  Upserted %s/%s vectors to Pinecone.", total_upserted, len(chunks))

        return True
    except Exception as e:
        logger.error("Pinecone upsert failed: %s", e)
        return False


def main() -> bool:
    input_pdf_dir = Path(INPUT_PDF_DIR)
    pdf_paths = sorted(input_pdf_dir.glob("*.pdf"))
    active_pdfs = {pdf_path.name for pdf_path in pdf_paths}

    pc = PineconeClient(api_key=PINECONE_API_KEY)
    index = pc.Index(PINECONE_INDEX_NAME)

    import json
    cache_file = input_pdf_dir / ".pinecone_sync_cache.json"

    existing_sources = {}
    if cache_file.exists():
        try:
            existing_sources = json.loads(cache_file.read_text())
        except Exception:
            pass

    if not active_pdfs:
        try:
            index.delete(delete_all=True, namespace="pdfs")
            logger.info("All PDFs removed. Cleared Pinecone 'pdfs' namespace.")
            if cache_file.exists():
                cache_file.unlink()
        except Exception as e:
            logger.error("Failed to clear Pinecone: %s", e)
        return True

    sources_to_delete = set(existing_sources.keys()) - active_pdfs
    sources_to_index = active_pdfs - set(existing_sources.keys())

    for pdf_name in active_pdfs:
        if pdf_name in existing_sources:
            pdf_path = input_pdf_dir / pdf_name
            if pdf_path.stat().st_mtime > existing_sources[pdf_name]:
                sources_to_delete.add(pdf_name)
                sources_to_index.add(pdf_name)

    logger.info(
        "Sync Plan:\n       - Active PDFs: %s\n       - To Delete/Re-index: %s\n       - To Generate/Add: %s",
        active_pdfs, sources_to_delete, sources_to_index
    )

    if not sources_to_delete and not sources_to_index:
        logger.info("Pinecone vector store is already up to date. Skipping re-indexing.")
        return True

    if sources_to_delete:
        for source in sources_to_delete:
            try:
                index.delete(filter={"source": source}, namespace="pdfs")
                logger.info("Deleted old chunks for %s from Pinecone.", source)
                existing_sources.pop(source, None)
            except Exception as e:
                logger.warning("Failed to delete chunks for %s: %s", source, e)

    if sources_to_index:
        logger.info("Chunking new/modified documents: %s...", sources_to_index)
        chunks = chunk_all_text_files(str(OUTPUT_DIR), CHUNK_SIZE, CHUNK_OVERLAP, target_sources=sources_to_index)

        if not chunks:
            logger.warning("No text chunks generated for the new/modified documents.")
        else:
            logger.info("Generated %s chunks. Building and uploading embeddings...", len(chunks))
            success = create_vectorstore(chunks)
            if not success:
                logger.error("Failed to generate and upload embeddings to Pinecone.")
                return False

            for source in sources_to_index:
                pdf_path = input_pdf_dir / source
                if pdf_path.exists():
                    existing_sources[source] = pdf_path.stat().st_mtime

    cache_file.write_text(json.dumps(existing_sources))
    logger.info("Pinecone vector store successfully updated!")
    return True


if __name__ == "__main__":
    main()
