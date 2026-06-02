import os
from dotenv import load_dotenv
from google import genai
from PIL import Image

load_dotenv()

_client = None

def _get_client():
    global _client
    if _client is None:
        api_key = os.getenv("GOOGLE_API_KEY")
        # Support fallback list keys from rotating setup
        if not api_key:
            api_key = os.getenv("GOOGLE_API_KEY_1")
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
            "Extract all text from this image accurately. Return only the visible text, no commentary, no markdown unless present in the image",
            img,
        ],
    )
    return response.text or ""
