import shutil
from pathlib import Path
import logging
from config import INPUT_PDF_DIR, OUTPUT_DIR, PINECONE_API_KEY, PINECONE_INDEX_NAME

logger = logging.getLogger(__name__)

class DocumentManager:
    """Manages physical files, directories, and synchronization with the UI."""

    @staticmethod
    def sync_streamlit_uploads(uploaded_files: list, prev_uploaded_files: list) -> tuple[list, list, list]:
        """
        Synchronizes the Streamlit uploaded files with the local filesystem storage.
        Returns: (saved_names, removed_names, current_file_names)
        """
        input_dir = Path(INPUT_PDF_DIR)
        input_dir.mkdir(exist_ok=True, parents=True)

        saved_names = []
        removed_names = []
        current_file_names = [f.name for f in uploaded_files] if uploaded_files else []

        # Save new uploads
        if uploaded_files:
            for uploaded_file in uploaded_files:
                file_path = input_dir / uploaded_file.name
                if not file_path.exists():
                    try:
                        with open(file_path, "wb") as f:
                            f.write(uploaded_file.getbuffer())
                        saved_names.append(uploaded_file.name)
                    except Exception as e:
                        logger.error("Failed to save uploaded file %s: %s", uploaded_file.name, e)

        # Remove deleted uploads
        for existing_file in input_dir.glob("*.pdf"):
            if existing_file.name in prev_uploaded_files and existing_file.name not in current_file_names:
                try:
                    existing_file.unlink()
                    removed_names.append(existing_file.name)
                    # Clear its cached text files
                    for ocr_state in ["True", "False"]:
                        cache_file = Path(OUTPUT_DIR) / "cache" / f"{existing_file.name}_ocr_{ocr_state}.txt"
                        if cache_file.exists():
                            cache_file.unlink()
                except Exception as e:
                    logger.error("Failed to delete file %s: %s", existing_file.name, e)

        return saved_names, removed_names, current_file_names

    @staticmethod
    def factory_reset() -> bool:
        """
        Deletes all uploaded PDFs, extracted text caches, and the Pinecone 'pdfs' vector namespace.
        Re-creates empty directories.
        """
        try:
            input_dir = Path(INPUT_PDF_DIR)
            if input_dir.exists():
                shutil.rmtree(input_dir)
            input_dir.mkdir(parents=True, exist_ok=True)
            
            output_dir = Path(OUTPUT_DIR)
            if output_dir.exists():
                shutil.rmtree(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            try:
                from pinecone import Pinecone as PineconeClient
                pc = PineconeClient(api_key=PINECONE_API_KEY)
                index = pc.Index(PINECONE_INDEX_NAME)
                index.delete(delete_all=True, namespace="pdfs")
            except Exception as e:
                logger.error("Failed to clear Pinecone index during reset: %s", e)

            return True
        except Exception as e:
            logger.error("Factory reset failed: %s", e)
            return False
