import asyncio
import re
import requests
import edge_tts
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pre-compiled regex patterns — compiled once at import time, not per call
# ---------------------------------------------------------------------------
_RE_YAML_BLOCK       = re.compile(r'^---[\s\S]*?---')
_RE_CODE_BLOCK       = re.compile(r'```[\s\S]*?```')
_RE_INLINE_CODE      = re.compile(r'`([^`]+)`')
_RE_BOLD             = re.compile(r'\*\*([^*]+)\*\*')
_RE_ITALIC           = re.compile(r'\*([^*]+)\*')
_RE_SOURCE_TOKEN     = re.compile(r'\[SOURCE:\s*(MATERIALS|GENERAL|HYBRID)\]')
_RE_WIKI_LINK        = re.compile(r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]')
_RE_MD_LINK          = re.compile(r'\[([^\]]+)\]\([^\)]+\)')
_RE_MD_TABLE         = re.compile(r'\|.*\|')
_RE_MD_HEADER        = re.compile(r'#+\s+')
_RE_BULLET           = re.compile(r'^\s*[-*+]\s+', re.MULTILINE)
_RE_NUMBERED_LIST    = re.compile(r'^\s*\d+\.\s+', re.MULTILINE)
_RE_WHITESPACE       = re.compile(r'\s+')

# Script-range → voice mapping
_SCRIPT_VOICES = [
    (re.compile(r'[\u0900-\u097F]'), 'hi-IN-MadhurNeural'),   # Devanagari
    (re.compile(r'[\u0A80-\u0AFF]'), 'gu-IN-DhwaniNeural'),   # Gujarati
    (re.compile(r'[\u0B80-\u0BFF]'), 'ta-IN-PallaviNeural'),  # Tamil
    (re.compile(r'[\u0C00-\u0C7F]'), 'te-IN-ShrutiNeural'),   # Telugu
    (re.compile(r'[\u0980-\u09FF]'), 'bn-IN-TanishaNeural'),  # Bengali
    (re.compile(r'[\u0C80-\u0CFF]'), 'kn-IN-SapnaNeural'),    # Kannada
    (re.compile(r'[\u0D00-\u0D7F]'), 'ml-IN-SobhanaNeural'),  # Malayalam
    (re.compile(r'[\u0A00-\u0A7F]'), 'pa-IN-OjasNeural'),     # Punjabi
]
_DEFAULT_VOICE = 'en-IN-NeerjaNeural'


def clean_text_for_tts(text: str) -> str:
    """
    Cleans markdown syntax, code blocks, citations, tables, and special characters
    to make assistant responses speakable. Uses pre-compiled patterns for speed.
    """
    text = _RE_YAML_BLOCK.sub('', text)
    text = _RE_CODE_BLOCK.sub('', text)
    text = _RE_INLINE_CODE.sub(r'\1', text)
    text = _RE_BOLD.sub(r'\1', text)
    text = _RE_ITALIC.sub(r'\1', text)
    text = _RE_SOURCE_TOKEN.sub('', text)
    text = _RE_WIKI_LINK.sub(r'\1', text)
    text = _RE_MD_LINK.sub(r'\1', text)
    text = _RE_MD_TABLE.sub('', text)
    text = _RE_MD_HEADER.sub('', text)
    text = _RE_BULLET.sub('', text)
    text = _RE_NUMBERED_LIST.sub('', text)
    text = _RE_WHITESPACE.sub(' ', text).strip()
    return text


def text_to_speech(text: str, rate: str = "-10%") -> bytes:
    """
    Generates TTS MP3 bytes using Microsoft Edge Neural TTS voices,
    auto-selecting voice based on detected script.
    """
    voice = _DEFAULT_VOICE
    for pattern, voice_name in _SCRIPT_VOICES:
        if pattern.search(text):
            voice = voice_name
            break

    logger.info("Generating neural speech: voice='%s', rate='%s'", voice, rate)

    async def _async_tts():
        communicate = edge_tts.Communicate(text, voice, rate=rate)
        audio_bytes = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_bytes += chunk["data"]
        return audio_bytes

    try:
        return asyncio.run(_async_tts())
    except Exception as e:
        logger.error("TTS Generation failed: %s", e)
        return b""


def transcribe_audio(audio_bytes: bytes, groq_api_key: str, format: str = "webm", translate: bool = False) -> str:
    """
    Sends audio bytes to Groq's Whisper API for transcription or translation.
    """
    if not groq_api_key:
        logger.error("GROQ_API_KEY not provided for transcription.")
        return ""

    if format.startswith("."):
        format = format[1:]

    endpoint = "translations" if translate else "transcriptions"
    url = f"https://api.groq.com/openai/v1/audio/{endpoint}"

    if translate:
        prompt = (
            "The audio contains ONLY Indian language speech (Hindi, Gujarati, Tamil, Telugu, Bengali, "
            "Kannada, Marathi, Hinglish, etc.) or English. "
            "Please translate this speech accurately into standard English text."
        )
    else:
        prompt = (
            "The audio contains ONLY Indian language speech (Hindi, Gujarati, Tamil, Telugu, Bengali, "
            "Kannada, Marathi, Hinglish, etc.) or English. "
            "Do NOT transcribe as other global languages. "
            "Transcribe accurately in the spoken language's original script or English."
        )

    logger.info("Sending %s bytes to Groq Whisper %s API...", len(audio_bytes), endpoint)
    try:
        response = requests.post(
            url,
            headers={"Authorization": f"Bearer {groq_api_key}"},
            files={"file": (f"audio.{format}", audio_bytes, f"audio/{format}")},
            data={"model": "whisper-large-v3", "prompt": prompt, "response_format": "json"},
            timeout=30
        )
        response.raise_for_status()
        transcription = response.json().get("text", "").strip()
        logger.info("STT Result: '%s'", transcription)
        return transcription
    except Exception as e:
        logger.error("Failed to transcribe/translate audio: %s", e)
        return ""
