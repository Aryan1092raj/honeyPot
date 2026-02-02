import os
from groq import Groq
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

class STTHandler:
    """
    Speech-to-Text using Groq Whisper.
    Converts audio recordings to text.
    """
    
    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY not found")
        self.client = Groq(api_key=api_key)
        self.model = "whisper-large-v3"
    
    def transcribe(self, audio_bytes: bytes, filename: str = "recording.wav") -> str:
        """
        Transcribe audio bytes to text.
        
        Args:
            audio_bytes: Raw audio data
            filename: Temp filename for the audio
            
        Returns:
            Transcribed text string
        """
        try:
            # Save temporarily
            temp_path = Path(__file__).resolve().parent / filename
            with open(temp_path, "wb") as f:
                f.write(audio_bytes)
            
            # Transcribe
            with open(temp_path, "rb") as audio_file:
                transcription = self.client.audio.transcriptions.create(
                    file=(filename, audio_file.read()),
                    model=self.model,
                    language="en",
                    response_format="text"
                )
            
            # Clean up
            temp_path.unlink()
            
            return transcription.strip()
            
        except Exception as e:
            print(f"STT Error: {e}")
            return None


# Test
if __name__ == "__main__":
    print("STT Handler ready. Use in app.py with audio recorder.")
