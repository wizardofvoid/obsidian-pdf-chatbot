import os
import sys
from pathlib import Path
from dotenv import load_dotenv

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# Load env variables from .env
load_dotenv()

# Helper to retrieve active Groq API Key
def get_groq_key() -> str:
    key = os.getenv("GROQ_API_KEY")
    if not key:
        for i in range(1, 10):
            k = os.getenv(f"GROQ_API_KEY_{i}")
            if k:
                return k
    return key

def transcribe_audio_groq(audio_bytes: bytes, format: str, translate: bool = False, language: str = None) -> str:
    import requests
    api_key = get_groq_key()
    if not api_key:
        raise ValueError("GROQ_API_KEY not found in environment (.env).")
        
    endpoint = "translations" if translate else "transcriptions"
    url = f"https://api.groq.com/openai/v1/audio/{endpoint}"
    
    headers = {
        "Authorization": f"Bearer {api_key}"
    }
    
    filename = f"audio.{format}"
    mime_type = f"audio/{format}"
    
    files = {
        "file": (filename, audio_bytes, mime_type)
    }
    
    # Custom instructions for Whisper
    prompt_instruction = (
        "The audio contains Indian language speech. Please transcribe the speech accurately in the spoken language's original script."
        if not translate else
        "The audio contains Indian language speech. Please translate this speech accurately into standard English text. Do NOT transliterate the pronunciation (e.g., do not write 'Aap kaise hain' or 'Namaskaram', translate it directly to 'How are you' or 'Hello')."
    )
    
    data = {
        "model": "whisper-large-v3",
        "prompt": prompt_instruction,
        "response_format": "json"
    }
    if language and not translate:
        data["language"] = language
        
    response = requests.post(url, headers=headers, files=files, data=data, timeout=30)
    response.raise_for_status()
    return response.json().get("text", "")


def main():
    print("=" * 65)
    print("LIVE INDIAN LANGUAGE SPEECH INTEGRATION TEST")
    print("=" * 65)
    
    # Check for gTTS package
    try:
        from gtts import gTTS
    except ImportError:
        print("gTTS package not found. Installing gTTS for text-to-speech generation...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "gtts"])
        from gtts import gTTS
        print("gTTS installed successfully!")

    # Test cases for different Indian Languages
    test_cases = [
        {
            "language": "Gujarati",
            "lang_code": "gu",
            "text": "નમસ્તે, તમે કેમ છો અને આજે હવામાન કેવું છે?"
        },
        {
            "language": "Hindi",
            "lang_code": "hi",
            "text": "नमस्ते, आप कैसे हैं and आज का मौसम कैसा है?"
        },
        {
            "language": "Tamil",
            "lang_code": "ta",
            "text": "வணக்கம், நீங்கள் எப்படி இருக்கிறீர்கள்?"
        },
        {
            "language": "Telugu",
            "lang_code": "te",
            "text": "నమస్కారం, మీరు ఎలా ఉన్నారు?"
        },
        {
            "language": "Bengali",
            "lang_code": "bn",
            "text": "নমস্কার, আপনি কেমন আছেন?"
        }
    ]
    
    temp_dir = Path("temp_test_audio")
    temp_dir.mkdir(exist_ok=True)
    
    print("\n--- Starting Live TTS -> STT Roundtrip Tests ---\n")
    
    for case in test_cases:
        lang = case["language"]
        code = case["lang_code"]
        text = case["text"]
        
        print(f"[{lang}] Original Text: '{text}'")
        
        # Step 1: Text-To-Speech (Generate Audio)
        print(f"[{lang}] 🔊 Generating audio file...")
        tts = gTTS(text=text, lang=code)
        audio_file = temp_dir / f"test_{code}.mp3"
        tts.save(str(audio_file))
        
        audio_bytes = audio_file.read_bytes()
        
        # Step 2: Speech-To-Text Transcription
        print(f"[{lang}] 🎙️ Running Transcription (Native Script)...")
        try:
            transcription = transcribe_audio_groq(audio_bytes, format="mp3", translate=False, language=code)
            print(f"[{lang}] Result: '{transcription}'")
        except Exception as e:
            print(f"[{lang}] Transcription Error: {e}")
            
        # Step 3: Speech-To-Text Translation
        print(f"[{lang}] 🌐 Running Translation (English)...")
        try:
            translation = transcribe_audio_groq(audio_bytes, format="mp3", translate=True, language=code)
            print(f"[{lang}] Result: '{translation}'")
        except Exception as e:
            print(f"[{lang}] Translation Error: {e}")
            
        print("-" * 65)
        
    # Clean up temp files
    for file in temp_dir.glob("*.mp3"):
        try:
            file.unlink()
        except:
            pass
    try:
        temp_dir.rmdir()
    except:
        pass
        
    print("\nLive roundtrip integration test complete!")

if __name__ == "__main__":
    main()
