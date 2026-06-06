import io
import logging
import tempfile
from pathlib import Path
import concurrent.futures

import pymupdf
from PIL import Image

import image_text
from config import INPUT_PDF_DIR, OUTPUT_DIR, OUTPUT_TEXT, MIN_IMAGE_SIZE

logger = logging.getLogger(__name__)

OUTPUT_FILE = OUTPUT_TEXT.name

def extract_page_hybrid(page, doc, temp_dir: Path, skip_ocr: bool = False) -> str:
    """Extract native page text, then OCR each embedded image via image_text in parallel."""
    parts = []

    text = page.get_text().strip()
    if text:
        parts.append(text)

    # Extract tables if any exist
    try:
        tables = page.find_tables()
        for i, table in enumerate(tables):
            try:
                table_markdown = table.to_markdown()
            except AttributeError:
                # Fallback: manually construct markdown table from list of lists
                grid = table.extract()
                if not grid:
                    continue
                rows = []
                for row_idx, row in enumerate(grid):
                    clean_row = [str(cell or "").replace("\n", " ").strip() for cell in row]
                    rows.append("| " + " | ".join(clean_row) + " |")
                    if row_idx == 0:
                        rows.append("| " + " | ".join(["---"] * len(clean_row)) + " |")
                table_markdown = "\n".join(rows)
            
            if table_markdown:
                parts.append(f"\n[Table — page {page.number + 1}, table {i + 1}]\n{table_markdown}")
    except Exception as e:
        logger.warning("Table extraction failed (page %s): %s", page.number + 1, e)

    if skip_ocr:
        return "\n\n".join(parts)

    images = page.get_images(full=True)
    if not images:
        return "\n\n".join(parts)

    def process_image(img_info) -> str | None:
        img_index, img = img_info
        xref = img[0]
        try:
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            image_ext = base_image["ext"]

            pil_image = Image.open(io.BytesIO(image_bytes))
            width, height = pil_image.size
            if width <= MIN_IMAGE_SIZE or height <= MIN_IMAGE_SIZE:
                return None

            temp_path = temp_dir / f"page_{page.number + 1}_img_{img_index + 1}.{image_ext}"
            temp_path.write_bytes(image_bytes)

            logger.info("Page %s: running image OCR (%s/%s)...", page.number + 1, img_index + 1, len(images))
            ocr_text = image_text.extract_text_image(str(temp_path)).strip()
            if ocr_text:
                return f"\n[Image text — page {page.number + 1}, image {img_index + 1}]\n{ocr_text}"
        except Exception as e:
            logger.warning("Image OCR skipped (page %s, image %s): %s", page.number + 1, img_index + 1, e)
        return None

    # Run image OCR requests concurrently (up to 4 workers to balance rate limits and speed)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        ocr_results = list(executor.map(process_image, enumerate(images)))

    for res in ocr_results:
        if res:
            parts.append(res)

    return "\n\n".join(parts)

def extract_page_worker(pdf_path: Path, page_num: int, temp_dir_path: Path, skip_ocr: bool) -> tuple[int, str]:
    try:
        with pymupdf.open(pdf_path) as doc:
            page = doc[page_num - 1]
            page_text = extract_page_hybrid(page, doc, temp_dir_path, skip_ocr=skip_ocr)
            return page_num, page_text
    except Exception as e:
        logger.error("Failed to extract page %s for %s: %s", page_num, pdf_path.name, e)
        return page_num, ""

def extract_pdf(pdf_path: Path, skip_ocr: bool = False) -> str:
    sections = [f"\n{'=' * 60}\nSOURCE: {pdf_path.name}\n{'=' * 60}\n"]

    with pymupdf.open(pdf_path) as doc:
        num_pages = len(doc)

    page_results = {}
    with tempfile.TemporaryDirectory() as tmp:
        temp_dir_path = Path(tmp)
        logger.info("Extracting %s pages from %s concurrently...", num_pages, pdf_path.name)
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(extract_page_worker, pdf_path, page_num, temp_dir_path, skip_ocr): page_num
                for page_num in range(1, num_pages + 1)
            }
            for future in concurrent.futures.as_completed(futures):
                p_num = futures[future]
                try:
                    _, page_text = future.result()
                    page_results[p_num] = page_text
                except Exception as e:
                    logger.error("Page worker thread exception on page %s: %s", p_num, e)
                    page_results[p_num] = ""

    for page_num in range(1, num_pages + 1):
        page_text = page_results.get(page_num, "")
        if page_text.strip():
            sections.append(f"\n--- Page {page_num} ---\n\n{page_text}")

    return "".join(sections)

def main(skip_ocr: bool = False) -> bool:
    input_dir = Path(INPUT_PDF_DIR)
    output_dir = Path(OUTPUT_DIR)
    output_file = output_dir / OUTPUT_FILE
    cache_dir = output_dir / "cache"

    if not input_dir.exists():
        logger.error("Directory not found: %s", input_dir)
        return False

    pdfs = sorted(input_dir.glob("*.pdf"))
    if not pdfs:
        logger.warning("No PDF files found in %s", input_dir)
        return False

    cache_dir.mkdir(parents=True, exist_ok=True)

    any_cache_updated = False
    combined = []

    for pdf_path in pdfs:
        # Cache file name reflects whether OCR was skipped to avoid cache collision
        cache_file = cache_dir / f"{pdf_path.name}_ocr_{not skip_ocr}.txt"
        
        is_cache_valid = False
        if cache_file.exists():
            cache_mtime = cache_file.stat().st_mtime
            pdf_mtime = pdf_path.stat().st_mtime
            if cache_mtime >= pdf_mtime:
                is_cache_valid = True
                
        if is_cache_valid:
            logger.info("Using cached text for: %s", pdf_path.name)
            pdf_text = cache_file.read_text(encoding="utf-8")
        else:
            logger.info("Extracting text (OCR=%s): %s", not skip_ocr, pdf_path.name)
            pdf_text = extract_pdf(pdf_path, skip_ocr=skip_ocr)
            cache_file.write_text(pdf_text, encoding="utf-8")
            any_cache_updated = True

        combined.append(pdf_text)

    # Rebuild output file if caches were updated or output.txt is missing/out-of-date
    rebuild_output = any_cache_updated or not output_file.exists()
    if not rebuild_output:
        output_mtime = output_file.stat().st_mtime
        for pdf_path in pdfs:
            cache_file = cache_dir / f"{pdf_path.name}_ocr_{not skip_ocr}.txt"
            if cache_file.exists() and cache_file.stat().st_mtime > output_mtime:
                rebuild_output = True
                break

    if rebuild_output:
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file.write_text("".join(combined), encoding="utf-8")
        logger.info("Combined text saved to %s", output_file)
        return True
    else:
        logger.info("%s and all caches are up to date. Skipping extraction.", OUTPUT_FILE)
        return False

if __name__ == "__main__":
    main()
