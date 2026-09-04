"""Agent TTS API endpoints."""
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from ..services.tts_service import TTSService
from ..services.edge_tts_service import EdgeTTSService
from ..services.agent_script import get_agent_segment, get_timing_windows, AGENT_SCRIPT
from ..dependencies import get_user_id_from_token, verify_token
from ..config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["agent"])

settings = get_settings()
tts_service: Optional[TTSService] = None
edge_tts_service: Optional[EdgeTTSService] = None

_MEDIA_TYPES = {
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
    "opus": "audio/opus",
    "flac": "audio/flac",
}


def _agent_cache_dir() -> Path:
    """Resolve the on-disk agent TTS cache directory."""
    cache_dir = Path(settings.data_dir) / "agent_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def _write_cache(path: Path, data: bytes) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    except OSError as exc:
        logger.warning("Could not write agent TTS cache %s: %s", path, exc)


def get_tts_service() -> TTSService:
    """Get or create the Fish Audio TTS service (requires a key)."""
    global tts_service
    if tts_service is None:
        if not settings.fish_audio_api_key:
            raise HTTPException(
                status_code=500,
                detail="Fish Audio API key not configured",
            )
        tts_service = TTSService(
            api_key=settings.fish_audio_api_key,
            model=settings.fish_audio_model,
            reference_id=settings.fish_audio_reference_id if settings.fish_audio_reference_id else None,
        )
    return tts_service


def get_edge_tts_service() -> EdgeTTSService:
    """Get or create the free Edge TTS service (no key required)."""
    global edge_tts_service
    if edge_tts_service is None:
        edge_tts_service = EdgeTTSService(voice=settings.edge_tts_voice)
    return edge_tts_service


async def _generate_with_fish(text: str, format: str) -> bytes:
    tts = get_tts_service()
    print("[Agent TTS] Calling Fish Audio API...")
    return await tts.generate_speech(
        text=text,
        format=format,
        sample_rate=16000,
        speed=1.0,
    )


async def _generate_with_edge(text: str) -> bytes:
    edge = get_edge_tts_service()
    print("[Agent TTS] Calling free Edge TTS voice...")
    return await edge.generate_speech(
        text=text,
        format="mp3",
        sample_rate=16000,
        speed=1.0,
    )


async def synthesize_agent_audio(
    text: str,
    format: str = "mp3",
    segment_index: int = 0,
) -> tuple[bytes, str, str, bool]:
    """Generate agent audio through the configured TTS provider chain.

    Returns ``(audio_bytes, actual_format, used_provider, cached)``.

    Provider routing (``TTS_PROVIDER``):
    - ``fish``: Fish Audio; errors re-raise (no silent fallback).
    - ``edge``: free Edge TTS; needs no key.
    - ``auto`` (default): prefer a cached Fish render, then Fish when a key is
      set, then free Edge TTS. Any Fish failure in ``auto`` falls back to Edge
      with a loud log (this is what keeps the demo alive on Fish HTTP 402).

    A static script means each line is synthesized once and cached on disk at
    ``<data_dir>/agent_cache/{fish|edge}_seg{N}.{ext}``. Only successful
    renders are cached.
    """
    cache_dir = _agent_cache_dir()
    fish_cache = cache_dir / f"fish_seg{segment_index}.{format}"
    edge_cache = cache_dir / f"edge_seg{segment_index}.mp3"

    provider = (settings.tts_provider or "auto").lower()

    if provider == "fish":
        if fish_cache.exists():
            print(f"[Agent TTS] Serving cached fish audio for segment {segment_index}")
            return fish_cache.read_bytes(), format, "fish", True
        audio_bytes = await _generate_with_fish(text, format)
        _write_cache(fish_cache, audio_bytes)
        return audio_bytes, format, "fish", False

    if provider == "edge":
        if edge_cache.exists():
            print(f"[Agent TTS] Serving cached edge audio for segment {segment_index}")
            return edge_cache.read_bytes(), "mp3", "edge", True
        audio_bytes = await _generate_with_edge(text)
        _write_cache(edge_cache, audio_bytes)
        return audio_bytes, "mp3", "edge", False

    # auto
    # Cache prefers Fish renders (highest fidelity), regardless of current keys.
    # If only an Edge render exists, serve it directly: a previous Fish failure
    # means we should not hammer a broken/out-of-credit API on every retry.
    if fish_cache.exists():
        print(f"[Agent TTS] Serving cached fish audio for segment {segment_index}")
        return fish_cache.read_bytes(), format, "fish", True

    if edge_cache.exists():
        print(f"[Agent TTS] Serving cached edge audio for segment {segment_index}")
        return edge_cache.read_bytes(), "mp3", "edge", True

    if settings.fish_audio_api_key:
        try:
            audio_bytes = await _generate_with_fish(text, format)
            _write_cache(fish_cache, audio_bytes)
            return audio_bytes, format, "fish", False
        except Exception as exc:
            logger.error(
                "Fish Audio TTS failed (%s). Falling back to free Edge TTS voice...",
                exc,
            )
            print(f"[Agent TTS] Fish failed ({exc}); falling back to Edge")

    audio_bytes = await _generate_with_edge(text)
    _write_cache(edge_cache, audio_bytes)
    return audio_bytes, "mp3", "edge", False


def _audio_response(
    audio_bytes: bytes,
    actual_format: str,
    segment_index: int,
    used_provider: str,
    cached: bool = False,
) -> Response:
    """Build the audio Response with the correct media type and headers."""
    media_type = _MEDIA_TYPES.get(actual_format, "application/octet-stream")
    return Response(
        content=audio_bytes,
        media_type=media_type,
        headers={
            "Cache-Control": "public, max-age=3600",  # Cache for 1 hour
            "Content-Disposition": f'inline; filename="agent_{segment_index}.{actual_format}"',
            "X-TTS-Provider": used_provider,
            "X-TTS-Cached": "true" if cached else "false",
        },
    )


@router.get("/script")
async def get_script(user_id: str = Depends(verify_token)):
    """Get the full agent script with timing (requires authentication)."""
    return {
        "script": AGENT_SCRIPT,
        "windows": get_timing_windows(),
    }


@router.get("/audio/{segment_index}")
async def get_agent_audio(segment_index: int, format: str = "mp3", token: str | None = None):
    """
    Generate and return agent audio for a specific script segment.

    Requires a valid Supabase access token. Browsers can't attach headers to
    `<audio>` element requests, so the token arrives as a `?token=` query
    param (same pattern as the audio WebSocket).

    Args:
        segment_index: Index of the script segment (0-based)
        format: Audio format (mp3, wav, opus, flac)
        token: Supabase access token
    """
    get_user_id_from_token(token)  # 401 on missing/invalid token
    print(f"[Agent TTS] Request for segment {segment_index}")

    # Get the segment
    segment = get_agent_segment(segment_index)
    print(f"[Agent TTS] Segment text: {segment['text'][:50]}...")

    # Generate TTS
    try:
        audio_bytes, actual_format, used_provider, cached = await synthesize_agent_audio(
            text=segment["text"],
            format=format,
            segment_index=segment_index,
        )

        print(f"[Agent TTS] Generated {len(audio_bytes)} bytes via {used_provider}")

        return _audio_response(
            audio_bytes,
            actual_format,
            segment_index,
            used_provider,
            cached=cached,
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"[Agent TTS] Error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate TTS: {str(e)}",
        )
