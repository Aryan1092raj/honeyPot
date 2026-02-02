import os
import base64
import hashlib
from pathlib import Path
from groq import Groq
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)


class TTSHandler:
    """
    TTS using Groq Orpheus (canopylabs/orpheus-v1-english).
    Supports vocal directions like [cheerful], [whisper], [sad] etc.
    Caches audio to avoid regenerating.
    """

    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY not found")
        self.client = Groq(api_key=api_key)
        self.model = "canopylabs/orpheus-v1-english"
        self.cache_dir = Path(__file__).resolve().parent / "audio_cache"
        self.cache_dir.mkdir(exist_ok=True)

        # Voices mapped to personas
        # troy, hannah, austin are confirmed working voices
        self.persona_voices = {
            "Elderly Teacher": "troy",       # Male voice for elderly persona
            "Young Professional": "hannah",  # Female voice for professional
            "College Student": "austin"      # Male voice for student
        }

        # Scammer always uses troy with aggressive tone
        self.scammer_voice = "troy"

    def _get_cache_path(self, text: str, voice: str) -> Path:
        text_hash = hashlib.md5(f"{text}_{voice}".encode()).hexdigest()[:12]
        return self.cache_dir / f"{text_hash}.wav"

    def generate_audio(self, text: str, voice: str = None) -> str:
        """
        Generate audio, return base64 string.
        Uses cache if available.
        """
        if not voice:
            voice = self.scammer_voice

        # Keep under 200 chars per request (Groq limit)
        if len(text) > 195:
            text = text[:195] + "..."

        cache_path = self._get_cache_path(text, voice)
        if cache_path.exists():
            with open(cache_path, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")

        try:
            response = self.client.audio.speech.create(
                model=self.model,
                voice=voice,
                input=text,
                response_format="wav"
            )

            # Response is a BinaryAPIResponse, read it directly
            audio_bytes = response.read()
            with open(cache_path, "wb") as f:
                f.write(audio_bytes)

            return base64.b64encode(audio_bytes).decode("utf-8")

        except Exception as e:
            print(f"TTS Error: {e}")
            return None

    def get_scammer_audio(self, text: str) -> str:
        """Scammer voice — aggressive tone"""
        # Add vocal direction for scammer
        directed_text = f"[confident] {text}"
        return self.generate_audio(directed_text, self.scammer_voice)

    def get_agent_audio(self, text: str, persona: str) -> str:
        """Agent voice — based on persona with appropriate tone"""
        voice = self.persona_voices.get(persona, "troy")

        # Tone varies by persona
        tone_map = {
            "Elderly Teacher": "[confused]",
            "Young Professional": "[neutral]",
            "College Student": "[nervous]"
        }
        tone = tone_map.get(persona, "[neutral]")
        directed_text = f"{tone} {text}"

        return self.generate_audio(directed_text, voice)

    def clear_cache(self):
        for f in self.cache_dir.glob("*.wav"):
            f.unlink()
        print("Audio cache cleared")


# ============================================================
# TEST (run: python tts_handler.py)
# ============================================================

if __name__ == "__main__":
    tts = TTSHandler()
    print("Testing Orpheus TTS...")

    # Test scammer
    audio = tts.get_scammer_audio("Hello sir, I am calling from your bank.")
    if audio:
        print("✅ Scammer voice works!")
    else:
        print("❌ Scammer voice failed")

    # Test agent
    audio = tts.get_agent_audio("Oh beta, let me check. My son usually helps me with this.", "Elderly Teacher")
    if audio:
        print("✅ Agent voice works!")
    else:
        print("❌ Agent voice failed")

    print("\nDone! Audio cached in /audio_cache/")