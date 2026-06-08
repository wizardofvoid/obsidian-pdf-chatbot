import asyncio
import re
import requests
import edge_tts
import logging

logger = logging.getLogger(__name__)

def clean_text_for_tts(text: str) -> str:
    """
    Cleans markdown syntax, code blocks, citations, tables, and special characters
    to make assistant responses speakable.
    """
    # Remove YAML metadata block
    text = re.sub(r'^---[\s\S]*?---', '', text)
    # Remove markdown code blocks
    text = re.sub(r'```[\s\S]*?```', '', text)
    # Remove inline code formatting
    text = re.sub(r'`([^`]+)`', r'\1', text)
    # Remove bold/italic markup
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'\*([^*]+)\*', r'\1', text)
    # Remove source indicator tokens e.g. [SOURCE: MATERIALS]
    text = re.sub(r'\[SOURCE:\s*(MATERIALS|GENERAL|HYBRID)\]', '', text)
    # Remove citations like [[Note Name]] or [[Note Name|Label]]
    text = re.sub(r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]', r'\1', text)
    # Clean up markdown links [text](url) -> text
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    # Clean up markdown tables
    text = re.sub(r'\|.*\|', '', text)
    # Remove markdown headers (#, ##, etc)
    text = re.sub(r'#+\s+', '', text)
    # Remove any lingering markdown lists, bullet points, numbering
    text = re.sub(r'^\s*[-*+]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)
    # Replace multiple spaces and newlines with a single space
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def text_to_speech(text: str, rate: str = "-10%") -> bytes:
    """
    Generates TTS MP3 bytes from cleaned text using Microsoft Edge Neural TTS voices, 
    matching regional scripts and custom rates.
    """
    # Script range detection mapping to Microsoft Neural Voices
    voice = 'en-IN-NeerjaNeural' # Default premium Indian English voice
    
    if re.search(r'[\u0900-\u097F]', text): # Devanagari (Hindi, Marathi, etc.)
        voice = 'hi-IN-MadhurNeural'
    elif re.search(r'[\u0A80-\u0AFF]', text): # Gujarati
        voice = 'gu-IN-DhwaniNeural'
    elif re.search(r'[\u0B80-\u0BFF]', text): # Tamil
        voice = 'ta-IN-PallaviNeural'
    elif re.search(r'[\u0C00-\u0C7F]', text): # Telugu
        voice = 'te-IN-ShrutiNeural'
    elif re.search(r'[\u0980-\u09FF]', text): # Bengali
        voice = 'bn-IN-TanishaNeural'
    elif re.search(r'[\u0C80-\u0CFF]', text): # Kannada
        voice = 'kn-IN-SapnaNeural'
    elif re.search(r'[\u0D00-\u0D7F]', text): # Malayalam
        voice = 'ml-IN-SobhanaNeural'
    elif re.search(r'[\u0A00-\u0A7F]', text): # Punjabi
        voice = 'pa-IN-OjasNeural'
        
    logger.info(f"Generating high-fidelity neural speech with voice: '{voice}' at rate: '{rate}'...")
    
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
        logger.error(f"TTS Generation failed: {e}")
        return b""

def transcribe_audio(audio_bytes: bytes, groq_api_key: str, format: str = "webm", translate: bool = False) -> str:
    """
    Sends audio bytes containing Indian languages to Groq's Whisper API.
    If translate is True, uses the translations endpoint to get English text.
    Otherwise, uses transcriptions endpoint to get text in the native script.
    """
    if not groq_api_key:
        logger.error("GROQ_API_KEY not provided for transcription.")
        return ""
    
    if format.startswith("."):
        format = format[1:]
    
    filename = f"audio.{format}"
    mime_type = f"audio/{format}"
    
    endpoint = "translations" if translate else "transcriptions"
    url = f"https://api.groq.com/openai/v1/audio/{endpoint}"
    
    headers = {
        "Authorization": f"Bearer {groq_api_key}"
    }
    
    files = {
        "file": (filename, audio_bytes, mime_type)
    }
    
    prompt_instruction = (
        "The audio contains ONLY Indian language speech (like Hindi, Gujarati, Tamil, Telugu, Bengali, Kannada, Marathi, Hinglish, etc.) or English. "
        "Do NOT transcribe as other global languages (e.g. Chinese, Spanish, Welsh, etc.). "
        "Please transcribe the speech accurately in the spoken language's original script or English."
        if not translate else
        "The audio contains ONLY Indian language speech (like Hindi, Gujarati, Tamil, Telugu, Bengali, Kannada, Marathi, Hinglish, etc.) or English. "
        "Please translate this speech accurately into standard English text."
    )
    
    data = {
        "model": "whisper-large-v3",
        "prompt": prompt_instruction,
        "response_format": "json"
    }
    
    logger.info(f"Sending {len(audio_bytes)} bytes to Groq Whisper {endpoint} API...")
    try:
        response = requests.post(url, headers=headers, files=files, data=data, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        transcription = result.get("text", "").strip()
        logger.info(f"STT Result: '{transcription}'")
        return transcription
        
    except Exception as e:
        logger.error(f"Failed to transcribe/translate audio: {e}")
        return ""
