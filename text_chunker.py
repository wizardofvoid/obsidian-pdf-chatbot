import os
import re
from pathlib import Path
from dotenv import load_dotenv

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
from config import OUTPUT_DIR, CHUNK_SIZE, CHUNK_OVERLAP, EMBEDDING_MODEL, VECTORSTORE_DIR, INPUT_PDF_DIR

def chunk_all_text_files(input_dir: str, chunk_size: int, chunk_overlap: int, target_sources: set[str] = None) -> list[Document]:
    """
    Reads cached text files for active PDFs, splits them into token-aware chunks,
    and preserves file name and page number metadata.
    """
    input_pdf_dir = Path(INPUT_PDF_DIR)
    cache_dir = Path(input_dir) / "cache"

    if not input_pdf_dir.exists() or not input_pdf_dir.is_dir():
        print(f"[ERROR] PDF directory not found: {input_pdf_dir.absolute()}")
        return []

    if not cache_dir.exists() or not cache_dir.is_dir():
        print(f"[ERROR] Cache directory not found: {cache_dir.absolute()}")
        return []

    texts = []
    metadatas = []

    # Find the active PDF cache files
    pdf_paths = sorted(input_pdf_dir.glob("*.pdf"))
    if not pdf_paths:
        print("[WARNING] No PDF files found to index.")
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
            print(f"[WARNING] No cached text found for: {pdf_path.name}")
            continue

        print(f"[INFO] Parsing cache file: {cache_file.name}")
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
            print(f"[ERROR] Failed to read or parse cache for {pdf_path.name}: {e}")

    if not texts:
        print("[WARNING] No text segments found to chunk.")
        return []

    print(f"[INFO] Initializing token-aware text splitter (Size: {chunk_size}, Overlap: {chunk_overlap})...")
    
    splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        encoding_name="cl100k_base",
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""]
    )

    print("[INFO] Splitting text into metadata-aware documents...")
    docs = splitter.create_documents(texts, metadatas=metadatas)
    return docs

def create_and_save_vectorstore(docs: list[Document]):
    """
    Generates embeddings for documents and saves them with metadata in a local FAISS vector store.
    """
    if not docs:
        return None

    chunks = [doc.page_content for doc in docs]
    metadatas = [doc.metadata for doc in docs]

    print(f"[INFO] Initializing Google Embeddings Model ({EMBEDDING_MODEL})...")
    
    try:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            api_key = os.getenv("GOOGLE_API_KEY_1")
        embeddings_model = GoogleGenerativeAIEmbeddings(model=EMBEDDING_MODEL, google_api_key=api_key)
    except Exception as e:
        print(f"[ERROR] Failed to initialize embeddings model. Make sure GOOGLE_API_KEY is set. Details: {e}")
        return None

    try:
        import concurrent.futures
        import time
        
        embeddings_list = [None] * len(chunks)
        print(f"[INFO] Generating embeddings for {len(chunks)} chunks concurrently with safe throttling...")

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
                        print(f"\n[WARNING] Rate limit hit on chunk {idx+1} (Attempt {attempt+1}/5). Backing off for {delay}s...")
                        time.sleep(delay)
                        continue
                    time.sleep(1)
            
            print(f"\n[ERROR] Failed to embed chunk {idx+1} after 5 attempts: {last_error}")
            raise last_error

        # Use max_workers=2 to prevent rapid concurrent request bursts
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(embed_single_chunk, enumerate(chunks)))
            
        for idx, emb in results:
            embeddings_list[idx] = emb
            
        print("[INFO] All embeddings generated successfully.")
        
        # Create FAISS vector store from the manually generated embeddings with metadata
        text_embeddings = list(zip(chunks, embeddings_list))
        vectorstore = FAISS.from_embeddings(
            text_embeddings=text_embeddings,
            embedding=embeddings_model,
            metadatas=metadatas
        )
        
        vectorstore.save_local(str(VECTORSTORE_DIR))
        print(f"[SUCCESS] FAISS vector store successfully saved to '{VECTORSTORE_DIR}' directory!")
        
        return vectorstore
    except Exception as e:
        print(f"\n[ERROR] FAISS creation failed: {e}")
        return None

def main() -> bool:
    input_pdf_dir = Path(INPUT_PDF_DIR)
    pdf_paths = sorted(input_pdf_dir.glob("*.pdf"))
    active_pdfs = {pdf_path.name for pdf_path in pdf_paths}

    # If no PDFs exist at all, clear the index directory
    if not active_pdfs:
        import shutil
        if VECTORSTORE_DIR.exists():
            shutil.rmtree(VECTORSTORE_DIR)
            print("[SUCCESS] All PDFs removed. Cleared FAISS index directory.")
        else:
            print("[INFO] No PDFs found and no index to clear.")
        return True

    # 1. Check if index exists and load it to determine existing sources
    vectorstore = None
    existing_sources = set()
    index_exists = (VECTORSTORE_DIR / "index.faiss").exists()

    if index_exists:
        print("[INFO] Existing FAISS index detected. Checking currently indexed PDFs...")
        try:
            api_key = os.getenv("GOOGLE_API_KEY")
            if not api_key:
                api_key = os.getenv("GOOGLE_API_KEY_1")
            embeddings_model = GoogleGenerativeAIEmbeddings(model=EMBEDDING_MODEL, google_api_key=api_key)
            vectorstore = FAISS.load_local(
                str(VECTORSTORE_DIR),
                embeddings_model,
                allow_dangerous_deserialization=True
            )
            if vectorstore and hasattr(vectorstore, "docstore") and hasattr(vectorstore.docstore, "_dict"):
                existing_sources = {
                    doc.metadata.get("source")
                    for doc in vectorstore.docstore._dict.values()
                    if doc.metadata.get("source")
                }
            print(f"[INFO] Loaded existing FAISS index. Indexed PDFs: {existing_sources}")
        except Exception as e:
            print(f"[WARNING] Failed to load existing FAISS index: {e}. Will rebuild index from scratch.")
            vectorstore = None

    # 2. Determine modification time of index
    index_mtime = (VECTORSTORE_DIR / "index.faiss").stat().st_mtime if index_exists else 0.0

    # 3. Identify modified PDFs
    modified_pdfs = set()
    for pdf_path in pdf_paths:
        if pdf_path.name in existing_sources:
            if pdf_path.stat().st_mtime > index_mtime:
                modified_pdfs.add(pdf_path.name)

    # 4. Determine additions, deletions, and updates
    sources_to_delete = (existing_sources - active_pdfs) | modified_pdfs
    sources_to_index = (active_pdfs - existing_sources) | modified_pdfs

    print(f"[INFO] Sync Plan:")
    print(f"       - Active PDFs: {active_pdfs}")
    print(f"       - Already Indexed: {existing_sources}")
    print(f"       - To Delete/Re-index: {sources_to_delete}")
    print(f"       - To Generate/Add: {sources_to_index}")

    # No changes required!
    if not sources_to_delete and not sources_to_index:
        print("[INFO] FAISS vector store is already perfectly up to date. Skipping re-indexing.")
        return True

    # 5. Delete removed/modified PDF chunks from the loaded index
    if sources_to_delete and vectorstore:
        try:
            ids_to_delete = [
                doc_id for doc_id, doc in vectorstore.docstore._dict.items()
                if doc.metadata.get("source") in sources_to_delete
            ]
            if ids_to_delete:
                vectorstore.delete(ids_to_delete)
                print(f"[SUCCESS] Deleted {len(ids_to_delete)} old chunks from the index.")
            # If after deletion the index becomes empty, set vectorstore to None so a new clean FAISS is initialized
            if not vectorstore.docstore._dict:
                print("[INFO] Index is now empty after deletions.")
                vectorstore = None
        except Exception as e:
            print(f"[WARNING] Failed to delete chunks from existing index: {e}. Will rebuild index from scratch.")
            vectorstore = None

    # 6. Index new or modified documents
    if sources_to_index:
        print(f"[INFO] Chunking new/modified documents: {sources_to_index}...")
        chunks = chunk_all_text_files(str(OUTPUT_DIR), CHUNK_SIZE, CHUNK_OVERLAP, target_sources=sources_to_index)
        
        if not chunks:
            print("[WARNING] No text chunks generated for the new/modified documents.")
        else:
            print(f"[SUCCESS] Generated {len(chunks)} chunks to index.")
            print("[INFO] Building embeddings for new chunks...")
            
            temp_vectorstore = create_and_save_vectorstore(chunks)
            if not temp_vectorstore:
                print("[ERROR] Failed to generate embeddings for new chunks.")
                return False
                
            if vectorstore is None:
                # If there was no prior index or it was cleared, the temp index becomes our main index
                vectorstore = temp_vectorstore
            else:
                # Merge the new FAISS index into our existing one
                print("[INFO] Merging new chunks into the existing FAISS index...")
                vectorstore.merge_from(temp_vectorstore)
                print("[SUCCESS] Merged new chunks successfully.")

    # 7. Save the updated main index back to disk
    if vectorstore:
        try:
            vectorstore.save_local(str(VECTORSTORE_DIR))
            print(f"[SUCCESS] FAISS vector store successfully saved to '{VECTORSTORE_DIR}'!")
            return True
        except Exception as e:
            print(f"[ERROR] Failed to save FAISS index: {e}")
            return False
    else:
        # If vectorstore is None here, it means all PDFs were cleared
        import shutil
        if VECTORSTORE_DIR.exists():
            shutil.rmtree(VECTORSTORE_DIR)
        print("[SUCCESS] Vector store is now completely empty.")
        return True

if __name__ == "__main__":
    main()
