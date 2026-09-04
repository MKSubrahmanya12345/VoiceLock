"""Deepfake Detector - Aurigin.AI API with a free local HuggingFace fallback.

The detector has four providers:

``off``
    Return ``0.0`` without doing anything (disable detection).
``aurigin``
    Call the Aurigin.AI API. On any failure return ``0.0`` (never silently
    switch providers when the user explicitly asked for Aurigin).
``local``
    Run ``Bisher/wav2vec2_ASV_deepfake_audio_detection`` (or any compatible
    ``AutoModelForAudioClassification``) locally with CPU inference.
``auto`` (default)
    Use Aurigin when an API key is configured; otherwise use the local model.
    In ``auto`` mode an Aurigin failure (including the user's current 404 on
    ``/api-ext/predict``) falls back to the local model with a loud log.

The Aurigin parsing logic is preserved verbatim in ``_detect_aurigin``.
"""
import asyncio
import io
import logging
import wave
from typing import Dict, Optional

import httpx

from ..config import get_settings

logger = logging.getLogger(__name__)

DEFAULT_LOCAL_MODEL = "Bisher/wav2vec2_ASV_deepfake_audio_detection"

# Substrings that identify a fake/synthetic class label. Keep the list
# reasonably specific so real/human labels do not accidentally match.
_FAKE_HINTS = ("fake", "spoof", "synthetic", "ai", "machine", "attack", "tampered")
_REAL_HINTS = ("real", "bonafide", "genuine", "human", "authentic", "original", "true")


def pick_fake_index(id2label: Dict[int, str]) -> int:
    """Return the label index that represents the fake/synthetic class.

    Selection order:
    1. First label whose text matches a fake hint.
    2. Binary fallback: when there are exactly two classes and one is clearly
       the real/bonafide class, the other one is the fake class.
    3. Last resort: index ``1`` with a warning. Never assume ``0`` because
       some checkpoints label the fake class ``1``.

    ``id2label`` may be a dict of ``{index: label}`` from a transformers
    config; int conversion is done defensively.
    """
    if not id2label:
        logger.warning("Deepfake model has no id2label; defaulting fake index to 1.")
        return 1

    normalized = {int(k): str(v).strip().lower() for k, v in id2label.items()}

    for idx, label in normalized.items():
        if any(hint in label for hint in _FAKE_HINTS):
            return idx

    real_indices = [idx for idx, label in normalized.items() if any(hint in label for hint in _REAL_HINTS)]
    if len(normalized) == 2 and real_indices:
        other = [idx for idx in normalized if idx not in real_indices]
        if other:
            return other[0]

    logger.warning(
        "Could not identify fake class from labels %s; defaulting fake index to 1.",
        id2label,
    )
    return 1


class LocalDeepfakeDetector:
    """Local transformer-based audio classification for deepfake detection.

    ``transformers`` is imported lazily so a missing optional dependency is a
    clear runtime error instead of an import-time crash. WAV parsing uses the
    standard library (``wave``) deliberately - no librosa, whose native
    Windows dependencies are heavy.
    """

    def __init__(self, model_id: str = DEFAULT_LOCAL_MODEL):
        self.model_id = model_id
        self._feature_extractor = None
        self._model = None
        self._id2label: Optional[Dict[int, str]] = None
        self._fake_index: Optional[int] = None
        self._labels_printed = False

    def _load(self) -> None:
        """Lazily load the model; safe to call from a worker thread."""
        if self._model is not None:
            return

        try:
            from transformers import AutoFeatureExtractor, AutoModelForAudioClassification
        except ImportError as exc:
            raise RuntimeError(
                "transformers is not installed. Install it with: "
                'pip install "transformers>=4.38.2,<4.39"'
            ) from exc

        logger.info("Loading local deepfake model: %s", self.model_id)
        self._feature_extractor = AutoFeatureExtractor.from_pretrained(
            self.model_id, trust_remote_code=False
        )
        self._model = AutoModelForAudioClassification.from_pretrained(
            self.model_id, trust_remote_code=False
        )
        self._model.eval()

        config_labels = getattr(getattr(self._model, "config", None), "id2label", None)
        self._id2label = dict(config_labels) if config_labels else {}
        self._fake_index = pick_fake_index(self._id2label)

        if not self._labels_printed:
            print(
                f"  🤖 Local deepfake model loaded "
                f"(labels={self._id2label}, fake_index={self._fake_index})"
            )
            self._labels_printed = True

    def _extract_tail(self, wav_bytes: bytes, tail_seconds: int) -> bytes:
        """Parse WAV PCM and keep only the last ``tail_seconds``.

        Returns raw little-endian int16 mono PCM bytes.
        """
        buffer = io.BytesIO(wav_bytes)
        with wave.open(buffer, "rb") as wav_file:
            channels = wav_file.getnchannels()
            sample_width = wav_file.getsampwidth()
            sample_rate = wav_file.getframerate()
            frames = wav_file.readframes(wav_file.getnframes())

        if channels != 1 or sample_width != 2:
            raise ValueError(
                f"Expected mono 16-bit WAV for local detection, got "
                f"channels={channels}, sample_width={sample_width}"
            )

        tail_bytes = int(sample_rate * tail_seconds) * 2  # 2 bytes per sample
        if len(frames) > tail_bytes:
            frames = frames[-tail_bytes:]
        return frames

    def _score_wav_sync(self, wav_bytes: bytes, tail_seconds: int = 15) -> float:
        """Blocking CPU inference for a WAV byte string."""
        self._load()
        try:
            import numpy as np
            import torch
        except ImportError as exc:
            raise RuntimeError("numpy/torch are required for local deepfake detection") from exc

        pcm = self._extract_tail(wav_bytes, tail_seconds)
        if not pcm:
            return 0.0

        raw = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0

        sampling_rate = getattr(self._feature_extractor, "sampling_rate", 16000)
        inputs = self._feature_extractor(
            raw,
            sampling_rate=sampling_rate,
            return_tensors="pt",
        )

        with torch.no_grad():
            logits = self._model(**inputs).logits
            probabilities = torch.softmax(logits, dim=-1)[0].cpu().numpy()

        score = float(probabilities[self._fake_index]) if len(probabilities) > self._fake_index else 0.0
        logger.info(
            "Local deepfake score: %.3f (fake_index=%d, labels=%s)",
            score,
            self._fake_index,
            self._id2label,
        )
        return score

    async def score_wav(self, wav_bytes: bytes, tail_seconds: int = 15) -> float:
        """Score a WAV; runs CPU inference in a thread so the WS loop stays live."""
        return await asyncio.to_thread(self._score_wav_sync, wav_bytes, tail_seconds)


class DeepfakeDetector:
    """Detect AI-generated/synthetic speech.

    Backward-compatible with the old ``DeepfakeDetector(api_url, api_key)``
    constructor: ``api_url``/``api_key`` may still be passed positionally or
    by keyword, while the new defaults pull from application settings.
    """

    def __init__(
        self,
        api_url: str = "",
        api_key: str = "",
        provider: Optional[str] = None,
        local_model: Optional[str] = None,
    ):
        settings = get_settings()
        self.api_url = (api_url or settings.aurigin_api_url).rstrip("/")
        self.api_key = api_key or settings.aurigin_api_key
        self.provider = (provider or settings.deepfake_provider or "auto").lower()
        self.local_model = local_model or settings.deepfake_model or DEFAULT_LOCAL_MODEL
        self.use_stub = not self.api_key  # kept for API compatibility
        self._local = LocalDeepfakeDetector(self.local_model)

    async def detect(self, audio_bytes: bytes) -> float:
        """Detect if audio is AI-generated.

        Returns a probability in ``[0, 1]`` that the audio is synthetic.
        """
        provider = self.provider

        if provider == "off":
            return 0.0

        if provider == "local":
            try:
                return await self._detect_local(audio_bytes)
            except Exception as exc:
                logger.error("Local deepfake detection failed: %s", exc)
                return 0.0

        if provider == "aurigin":
            try:
                return await self._detect_aurigin(audio_bytes)
            except Exception as exc:
                logger.error("Aurigin.AI deepfake detection failed: %s", exc)
                return 0.0

        # provider == "auto"
        if self.api_key:
            try:
                return await self._detect_aurigin(audio_bytes)
            except Exception as exc:
                logger.error(
                    "Aurigin.AI deepfake detection failed (%s); "
                    "falling back to the free local model.",
                    exc,
                )
                try:
                    return await self._detect_local(audio_bytes)
                except Exception as local_exc:
                    logger.error("Local deepfake fallback also failed: %s", local_exc)
                    return 0.0

        try:
            return await self._detect_local(audio_bytes)
        except Exception as exc:
            logger.error("Local deepfake detection failed: %s", exc)
            return 0.0

    async def _detect_local(self, audio_bytes: bytes) -> float:
        return await self._local.score_wav(audio_bytes)

    async def _detect_aurigin(self, audio_bytes: bytes) -> float:
        """Aurigin.AI API call. Raises on failure so ``auto`` can fall back."""
        if not self.api_key:
            raise RuntimeError("Aurigin.AI API key not configured")

        import time

        total_start = time.time()
        print("  🔍 Starting Aurigin.AI deepfake detection...")

        files = {"file": ("recording.wav", audio_bytes, "audio/wav")}

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.api_url}/predict",
                headers={"x-api-key": self.api_key},
                files=files,
            )
            print(f"    [DEBUG] Raw HTTP Status: {response.status_code}")
            print(f"    [DEBUG] Raw Response Text: {response.text}")
            response.raise_for_status()
            result = response.json()

        total_time = time.time() - total_start

        # Actual API format: {"predictions": ["real", "fake", ...], "global_probability": [...]}
        predictions = result.get("predictions", [])
        probabilities = result.get("global_probability", [])

        if not predictions or not probabilities:
            print(f"    ✗ Invalid API response: {result}")
            raise RuntimeError(f"Aurigin.AI returned an invalid response: {result}")

        fake_count = sum(1 for p in predictions if p == "fake")
        total_count = len(predictions)
        mean_fake_prob = sum(probabilities) / len(probabilities)

        print(
            f"  ✓ Aurigin.AI: {mean_fake_prob:.3f} ({mean_fake_prob * 100:.1f}% AI) - "
            f"{fake_count}/{total_count} fake segments in {total_time:.1f}s"
        )
        return mean_fake_prob

    def bytes_to_wav(self, pcm_bytes: bytes, sample_rate: int = 16000) -> bytes:
        """Convert PCM bytes to WAV format for API/local submission.

        Args:
            pcm_bytes: Raw PCM audio bytes (16-bit)
            sample_rate: Sample rate in Hz

        Returns:
            WAV format audio bytes
        """
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm_bytes)
        return buffer.getvalue()
