"""Voice Embedding - SpeechBrain ECAPA-TDNN for speaker verification"""
import logging
import torch
import numpy as np
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

MODEL_SOURCE = "speechbrain/spkrec-ecapa-voxceleb"

# Anchor the model cache to the backend directory so it no longer depends on
# the process working directory (uvicorn may be started from the repo root
# or from backend/, which previously resolved to different locations).
_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_MODEL_DIR = _BACKEND_DIR / "pretrained_models" / "spkrec-ecapa-voxceleb"


def is_valid_hparams_file(path: Path) -> bool:
    """Check that a cached hyperparams.yaml is a real hyperparams mapping.

    A corrupt cache entry (e.g. a file containing a local filesystem path
    instead of YAML) parses to a plain string. SpeechBrain's ``fetch`` reuses
    any file already present in ``savedir`` as-is, so such a file makes model
    loading crash with ``AttributeError: 'str' object has no attribute
    'keys'`` deep inside hyperpyyaml. Detect that here so the bad file can
    be discarded and re-downloaded from the HuggingFace Hub.

    Returns True when the file is missing (nothing cached yet -> download)
    or when it parses as a mapping containing the expected ``modules`` key.
    """
    if not path.exists():
        return True
    try:
        try:
            import yaml  # pyyaml, present via the speechbrain/hyperpyyaml stack
        except ImportError:
            yaml = None
        if yaml is not None:
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            # SpeechBrain requires "modules" and "pretrainer" keys; a poisoned
            # file parses to a plain string and fails the isinstance check.
            return isinstance(data, dict) and ("modules" in data or "pretrainer" in data)
        # Fallback heuristic without pyyaml: the real file is kilobytes of
        # YAML defining those mappings; poisoned files are short single-line
        # scalars that never mention them.
        content = path.read_bytes()
        return b"modules:" in content or b"pretrainer:" in content
    except Exception:
        return False


class VoiceEmbedding:
    """Speaker embedding and verification using SpeechBrain ECAPA-TDNN"""
    
    def __init__(
        self,
        model_name: str = MODEL_SOURCE,
        embeddings_dir: str = "../data/embeddings",
        model_dir: Optional[str] = None,
    ):
        self.model_name = model_name
        self.embeddings_dir = Path(embeddings_dir)
        self.embeddings_dir.mkdir(parents=True, exist_ok=True)
        # Absolute model cache dir (see DEFAULT_MODEL_DIR); may be overridden
        # for tests via model_dir.
        self.model_dir = Path(model_dir) if model_dir else DEFAULT_MODEL_DIR
        self.model = None  # Lazy loaded
    
    def _load_model(self):
        """Lazy load the SpeechBrain model with torchaudio compatibility patch"""
        if self.model is not None:
            return
        # Patch torchaudio compatibility issue before importing speechbrain
        import torchaudio
        if not hasattr(torchaudio, 'list_audio_backends'):
            # Monkey patch for newer torchaudio versions
            torchaudio.list_audio_backends = lambda: ["sox", "soundfile"]

        self.model_dir.mkdir(parents=True, exist_ok=True)

        # Drop a poisoned hyperparams.yaml (see is_valid_hparams_file) so
        # SpeechBrain downloads a fresh copy instead of crashing on it.
        hparams_file = self.model_dir / "hyperparams.yaml"
        if hparams_file.exists() and not is_valid_hparams_file(hparams_file):
            logger.warning(
                "Removing invalid cached model file %s; it will be "
                "re-downloaded from the HuggingFace Hub.",
                hparams_file,
            )
            hparams_file.unlink()

        from speechbrain.inference.speaker import EncoderClassifier

        logger.info("Loading SpeechBrain model: %s...", self.model_name)
        try:
            kwargs = {
                "source": self.model_name,
                "savedir": str(self.model_dir),
            }
            # SpeechBrain's Pretrained.from_hparams accepts a local_strategy
            # since ~1.0.0. Use LocalStrategy.COPY so the cached model files
            # are plain copies rather than symlinks. Windows blocks creating
            # symlinks without admin / Developer Mode (WinError 1314), which
            # previously broke first launch on the user's machine.
            try:
                import inspect

                from speechbrain.utils.fetching import LocalStrategy

                if "local_strategy" in inspect.signature(EncoderClassifier.from_hparams).parameters:
                    kwargs["local_strategy"] = LocalStrategy.COPY
            except Exception:
                # Very old SpeechBrain or missing symbol: keep the default
                # behaviour rather than crash the whole model fetch.
                logger.debug("LocalStrategy.COPY not available for EncoderClassifier.from_hparams")

            self.model = EncoderClassifier.from_hparams(**kwargs)
        except Exception as e:
            raise RuntimeError(
                f"Could not load voice model '{self.model_name}'. "
                "Check network access to huggingface.co, then delete "
                f"'{self.model_dir}' and retry. Original error: {e}"
            ) from e
        logger.info("Model loaded successfully")
    
    def compute_embedding(self, audio_tensor: torch.Tensor) -> np.ndarray:
        """
        Compute speaker embedding from audio tensor.
        
        Args:
            audio_tensor: 1D tensor of audio samples (mono, 16kHz)
        
        Returns:
            192-dimensional embedding as numpy array
        """
        self._load_model()
        
        # SpeechBrain expects (batch, time)
        if audio_tensor.dim() == 1:
            audio_tensor = audio_tensor.unsqueeze(0)  # Add batch dimension
        
        # Compute embedding
        with torch.no_grad():
            embedding = self.model.encode_batch(audio_tensor)
            # embedding shape: (batch, 1, embedding_dim)
            embedding = embedding.squeeze().cpu().numpy()
        
        return embedding
    
    def cosine_similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """
        Compute cosine similarity between two embeddings.
        
        Returns:
            Similarity score in range [0, 1] where 1 = identical, 0 = opposite
        """
        # Compute cosine similarity
        dot_product = np.dot(embedding1, embedding2)
        norm1 = np.linalg.norm(embedding1)
        norm2 = np.linalg.norm(embedding2)
        
        similarity = dot_product / (norm1 * norm2)
        
        # Normalize from [-1, 1] to [0, 1]
        similarity = (similarity + 1.0) / 2.0
        
        return float(similarity)
    
    def load_enrolled_embedding(self, user_id: str) -> Optional[np.ndarray]:
        """
        Load pre-computed enrollment embedding from disk.
        
        Args:
            user_id: User identifier (e.g., "demo_user")
        
        Returns:
            Embedding array or None if not found
        """
        embedding_path = self.embeddings_dir / f"{user_id}_embedding.npy"
        
        if not embedding_path.exists():
            print(f"✗ No enrollment found for user: {user_id}")
            return None
        
        embedding = np.load(embedding_path)
        print(f"✓ Loaded enrollment for {user_id}: shape {embedding.shape}")
        return embedding
    
    def verify_speaker(self, audio_tensor: torch.Tensor, user_id: str) -> float:
        """
        Verify if audio matches enrolled speaker.
        
        Args:
            audio_tensor: Audio to verify
            user_id: User to verify against
        
        Returns:
            Similarity score [0, 1] where higher = more similar
        """
        # Load enrolled embedding
        enrolled_embedding = self.load_enrolled_embedding(user_id)
        if enrolled_embedding is None:
            return 0.0  # No enrollment = no match
        
        # Compute embedding for current audio
        current_embedding = self.compute_embedding(audio_tensor)
        
        # Calculate similarity
        similarity = self.cosine_similarity(enrolled_embedding, current_embedding)
        
        return similarity


# Global instance - singleton pattern
_voice_embedding: Optional[VoiceEmbedding] = None


def get_voice_embedding() -> VoiceEmbedding:
    """Get or create global voice embedding instance"""
    global _voice_embedding
    if _voice_embedding is None:
        _voice_embedding = VoiceEmbedding()
    return _voice_embedding
