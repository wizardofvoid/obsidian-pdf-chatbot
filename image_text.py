import os
import threading
from dotenv import load_dotenv
from google import genai
from PIL import Image

load_dotenv()

_client = None
_client_lock = threading.Lock()


def _get_client() -> genai.Client:
    """
    Returns a module-level singleton Gemini client.
    Thread-safe: uses a lock on first initialization only.
    """
    global _client
    if _client is not None:
        return _client

    with _client_lock:
        if _client is not None:  # double-checked locking
            return _client
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GOOGLE_API_KEY_1")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY is not set in environment.")
        _client = genai.Client(api_key=api_key)

    return _client


def extract_text_image(img_path: str) -> str:
    """Extract text from an image using Gemini. Raises on API/network errors."""
    img = Image.open(img_path)
    response = _get_client().models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            "Extract all text from this image accurately. "
            "Return only the visible text, no commentary, no markdown unless present in the image",
            img,
        ],
    )
    return response.text or ""
