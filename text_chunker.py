import os
import re
import logging
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# pyrefly: ignore [missing-import]
from langchain_core.documents import Document
# pyrefly: ignore [missing-import]
from langchain_text_splitters import RecursiveCharacterTextSplitter
# pyrefly: ignore [missing-import]
from langchain_google_genai import GoogleGenerativeAIEmbeddings
# pyrefly: ignore [missing-import]
from langchain_community.vectorstores import FAISS

# Load environment variables (e.g., GOOGLE_API_KEY)
load_dotenv()

# =========================================================
# CONFIG
# =========================================================
from config import OUTPUT_DIR, CHUNK_SIZE, CHUNK_OVERLAP, EMBEDDING_MODEL, INPUT_PDF_DIR, PINECONE_API_KEY, PINECONE_INDEX_NAME
from pinecone import Pinecone as PineconeClient
from langchain_community.vectorstores import Pinecone

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

    # Find the active PDF cache files
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
            if cache_file_true.stat().st_mtime >= cache_file_false.stat().st_mtime:
                cache_file = cache_file_true
            else:
                cache_file = cache_file_false
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
            
            # Parse pages
            pattern = r"--- Page (\d+) ---\n"
            parts = re.split(pattern, content)
            
            pages = []
            if len(parts) > 1:
                for i in range(1, len(parts), 2):
                    page_num = int(parts[i])
                    page_text = parts[i+1].strip()
                    if page_text:
                        pages.append((page_num, page_text))
            
            if not pages and content.strip():
                pages.append((1, content.strip()))

            for page_num, page_text in pages:
                texts.append(page_text)
                metadatas.append({
                    "source": pdf_path.name,
                    "page": page_num
                })
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

def create_vectorstore(docs: list[Document]):
    """
    Generates embeddings for documents and creates an in-memory FAISS vector store.
    """
    if not docs:
        return None

    chunks = [doc.page_content for doc in docs]
    metadatas = [doc.metadata for doc in docs]

    logger.info("Initializing Google Embeddings Model (%s)...", EMBEDDING_MODEL)
    
    try:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            api_key = os.getenv("GOOGLE_API_KEY_1")
        embeddings_model = GoogleGenerativeAIEmbeddings(model=EMBEDDING_MODEL, google_api_key=api_key)
    except Exception as e:
        logger.error("Failed to initialize embeddings model. Make sure GOOGLE_API_KEY is set. Details: %s", e)
        return None

    try:
        import concurrent.futures
        import time
        
        embeddings_list = [None] * len(chunks)
        logger.info("Generating embeddings for %s chunks concurrently with safe throttling...", len(chunks))

        def embed_single_chunk(item):
            idx, chunk = item
            last_error = None
            for attempt in range(5):
                try:
                    # Space out requests naturally to avoid hitting the burst RPM limit
                    time.sleep(0.15)
                    return idx, embeddings_model.embed_query(chunk)
                except Exception as e:
                    last_error = e
                    err_msg = str(e).lower()
                    if "rate limit" in err_msg or "429" in err_msg or "resource_exhausted" in err_msg:
                        delay = 4 * (attempt + 1)
                        logger.warning("Rate limit hit on chunk %s (Attempt %s/5). Backing off for %ss...", idx + 1, attempt + 1, delay)
                        time.sleep(delay)
                        continue
                    time.sleep(1)
            
            logger.error("Failed to embed chunk %s after 5 attempts: %s", idx + 1, last_error)
            raise last_error

        # Use max_workers=2 to prevent rapid concurrent request bursts
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(embed_single_chunk, enumerate(chunks)))
            
        for idx, emb in results:
            embeddings_list[idx] = emb
            
        logger.info("All embeddings generated successfully.")
        
        import uuid
        ids = [str(uuid.uuid4()) for _ in chunks]
        text_embeddings = list(zip(chunks, embeddings_list))
        
        # Initialize Pinecone Client
        pc = PineconeClient(api_key=PINECONE_API_KEY)
        index = pc.Index(PINECONE_INDEX_NAME)
        
        # Upsert in batches of 100
        batch_size = 100
        for i in range(0, len(text_embeddings), batch_size):
            batch = text_embeddings[i:i+batch_size]
            batch_ids = ids[i:i+batch_size]
            batch_meta = metadatas[i:i+batch_size]
            
            vectors = []
            for j, (text, emb) in enumerate(batch):
                meta = batch_meta[j]
                meta["text"] = text  # Langchain Pinecone requires text in metadata
                vectors.append((batch_ids[j], emb, meta))
                
            index.upsert(vectors=vectors, namespace="pdfs")
            
        return True
    except Exception as e:
        logger.error("Pinecone creation failed: %s", e)
        return False

def main() -> bool:
    input_pdf_dir = Path(INPUT_PDF_DIR)
    pdf_paths = sorted(input_pdf_dir.glob("*.pdf"))
    active_pdfs = {pdf_path.name for pdf_path in pdf_paths}

    pc = PineconeClient(api_key=PINECONE_API_KEY)
    index = pc.Index(PINECONE_INDEX_NAME)

    # 1. Identify which PDFs are already in the Pinecone namespace
    # Since Pinecone doesn't easily let us list all distinct metadata values,
    # we use a local cache file to track what we've indexed from this machine.
    # In a fully serverless environment, this means we rebuild if the file is lost,
    # or we just rely on active_pdfs.
    import json
    cache_file = input_pdf_dir / ".pinecone_sync_cache.json"
    
    existing_sources = {}
    if cache_file.exists():
        try:
            existing_sources = json.loads(cache_file.read_text())
        except:
            pass

    # If no PDFs exist at all locally, we should probably clear the namespace 
    # but ONLY if we are tracking them. For now, we assume local is source of truth.
    if not active_pdfs:
        try:
            index.delete(delete_all=True, namespace="pdfs")
            logger.info("All PDFs removed. Cleared Pinecone 'pdfs' namespace.")
            if cache_file.exists():
                cache_file.unlink()
        except Exception as e:
            logger.error("Failed to clear Pinecone: %s", e)
        return True

    # 2. Determine additions, deletions, and updates
    sources_to_delete = set(existing_sources.keys()) - active_pdfs
    sources_to_index = active_pdfs - set(existing_sources.keys())
    
    # Check for modifications
    for pdf_name in active_pdfs:
        if pdf_name in existing_sources:
            pdf_path = input_pdf_dir / pdf_name
            if pdf_path.stat().st_mtime > existing_sources[pdf_name]:
                sources_to_delete.add(pdf_name)
                sources_to_index.add(pdf_name)

    logger.info("Sync Plan:\n       - Active PDFs: %s\n       - To Delete/Re-index: %s\n       - To Generate/Add: %s", active_pdfs, sources_to_delete, sources_to_index)

    # No changes required!
    if not sources_to_delete and not sources_to_index:
        logger.info("Pinecone vector store is already perfectly up to date. Skipping re-indexing.")
        return True

    # 3. Delete removed/modified PDF chunks from the index
    if sources_to_delete:
        for source in sources_to_delete:
            try:
                # Note: This requires a Pinecone plan that supports metadata filtering deletes
                index.delete(filter={"source": source}, namespace="pdfs")
                logger.info("Deleted old chunks for %s from Pinecone.", source)
                existing_sources.pop(source, None)
            except Exception as e:
                logger.warning("Failed to delete chunks for %s: %s", source, e)

    # 4. Index new or modified documents
    if sources_to_index:
        logger.info("Chunking new/modified documents: %s...", sources_to_index)
        chunks = chunk_all_text_files(str(OUTPUT_DIR), CHUNK_SIZE, CHUNK_OVERLAP, target_sources=sources_to_index)
        
        if not chunks:
            logger.warning("No text chunks generated for the new/modified documents.")
        else:
            logger.info("Generated %s chunks to index.", len(chunks))
            logger.info("Building embeddings for new chunks...")
            
            success = create_vectorstore(chunks)
            if not success:
                logger.error("Failed to generate and upload embeddings to Pinecone.")
                return False
                
            # Update cache
            for source in sources_to_index:
                pdf_path = input_pdf_dir / source
                if pdf_path.exists():
                    existing_sources[source] = pdf_path.stat().st_mtime

    # Save tracking cache
    cache_file.write_text(json.dumps(existing_sources))
    logger.info("Pinecone vector store successfully updated!")
    return True

if __name__ == "__main__":
    main()
