"""Edge TTS Service - free, keyless fallback for the agent voice.

``edge-tts`` wraps the same online neural voices that Microsoft Edge uses
for Read Aloud. It needs no API key and no paid credit, which is why it is
the default fallback when Fish Audio is unavailable (no key, out of credit,
or an unreachable endpoint).

The class mirrors the async ``TTSService.generate_speech()`` shape so the
agent TTS chain can treat Fish Audio and Edge TTS interchangeably. Edge only
produces MP3, so callers should treat the returned format accordingly.
"""
import os
import tempfile
from typing import Optional


class EdgeTTSService:
    """Generate speech using Microsoft Edge TTS (edge-tts package)."""

    def __init__(self, voice: str = "en-US-AriaNeural"):
        self.voice = voice

    async def generate_speech(
        self,
        text: str,
        format: str = "mp3",
        sample_rate: int = 16000,
        speed: float = 1.0,
    ) -> bytes:
        """Generate MP3 speech bytes for ``text``.

        Args:
            text: Text to convert to speech.
            format: Accepted for API compatibility with ``TTSService``; Edge
                always returns MP3 so the value is ignored (``actual_format``
                is reported by the caller).
            sample_rate: Accepted for API compatibility; Edge TTS always
                returns its own 24 kHz MP3 stream.
            speed: Speech speed multiplier (Fish-style). ``1.0`` maps to
                edge-tts ``+0%``.

        Returns:
            MP3 audio bytes.
        """
        try:
            import edge_tts  # lazy import so a missing dep is a clear error
        except ImportError as exc:
            raise RuntimeError(
                "edge-tts is not installed. Install it with: "
                'pip install "edge-tts>=6.1.0"'
            ) from exc

        rate = self._map_speed(speed)

        # Communicate.save() writes to a path; use a temp file and read it back.
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            communicate = edge_tts.Communicate(text, self.voice, rate=rate)
            await communicate.save(tmp_path)
            with open(tmp_path, "rb") as audio_file:
                return audio_file.read()
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    @staticmethod
    def _map_speed(speed: float) -> str:
        """Map a Fish-style speed multiplier to an edge-tts ``rate`` string.

        ``speed=1.0`` -> ``+0%``, ``1.1`` -> ``+10%``, ``0.8`` -> ``-20%``.
        """
        percent = round((float(speed) - 1.0) * 100)
        return f"{percent:+d}%"
