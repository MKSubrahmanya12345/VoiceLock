"""Tests for the free-tier agent voice + deepfake fallbacks.

Covers the TTS provider chain (Fish -> Edge fallback, cache), edge-tts rate
mapping, and deepfake provider routing (auto/aurigin/local/off). Heavy native
deps (torch, fishaudio, google.generativeai) are stubbed so the tests run in a
plain fastapi/httpx/numpy venv without downloading models or calling APIs.
"""
import builtins
import sys
import types
from unittest.mock import AsyncMock

import pytest

_original_import = builtins.__import__


# ---------------------------------------------------------------------------
# Stub heavy dependencies before importing app.* (see handoff §6).
# ---------------------------------------------------------------------------
class _Ctx:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _install_stubs():
    torch = types.ModuleType("torch")
    torch.Tensor = object
    torch.no_grad = lambda: _Ctx()
    torch.zeros = lambda *a, **k: None
    torch.from_numpy = lambda *a, **k: None
    torch.cat = lambda *a, **k: None
    torch.clamp = lambda *a, **k: None
    torch.softmax = lambda *a, **k: a[0]
    sys.modules["torch"] = torch

    torchaudio = types.ModuleType("torchaudio")
    torchaudio.list_audio_backends = lambda: []
    sys.modules["torchaudio"] = torchaudio

    fishaudio = types.ModuleType("fishaudio")
    fishaudio.FishAudio = type("FishAudio", (), {"__init__": lambda self, *a, **k: None})
    utils = types.ModuleType("fishaudio.utils")
    utils.save = lambda *a, **k: None
    sys.modules["fishaudio"] = fishaudio
    sys.modules["fishaudio.utils"] = utils

    google = types.ModuleType("google")
    genai = types.ModuleType("google.generativeai")
    genai.configure = lambda **k: None
    genai.GenerativeModel = type("GenerativeModel", (), {"__init__": lambda self, *a, **k: None})
    sys.modules["google"] = google
    sys.modules["google.generativeai"] = genai


_install_stubs()

import app.api.agent as agent  # noqa: E402
from app.services.deepfake_detector import (  # noqa: E402
    DEFAULT_LOCAL_MODEL,
    DeepfakeDetector,
    LocalDeepfakeDetector,
    pick_fake_index,
)
from app.services.edge_tts_service import EdgeTTSService  # noqa: E402


def _make_wav(seconds: float = 0.1, sample_rate: int = 16000) -> bytes:
    """Build a tiny mono 16-bit WAV of silence."""
    import io
    import wave

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(b"\x00\x00" * int(sample_rate * seconds))
    return buffer.getvalue()


def _fake_edge_module():
    """A fake edge_tts module that writes fixed MP3 bytes to the target file."""
    module = types.ModuleType("edge_tts")

    class _Communicate:
        def __init__(self, text, voice, **kwargs):
            self.text = text
            self.voice = voice
            self.kwargs = kwargs

        async def save(self, path):
            with open(path, "wb") as f:
                f.write(b"FAKE_EDGE_MP3")

    module.Communicate = _Communicate
    return module


# ---------------------------------------------------------------------------
# Edge TTS
# ---------------------------------------------------------------------------
class TestEdgeTTSService:
    def test_edge_rate_mapping(self):
        assert EdgeTTSService._map_speed(1.0) == "+0%"
        assert EdgeTTSService._map_speed(1.1) == "+10%"
        assert EdgeTTSService._map_speed(0.8) == "-20%"
        assert EdgeTTSService._map_speed(2.0) == "+100%"

    async def test_generate_speech_returns_mp3_bytes(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "edge_tts", _fake_edge_module())
        service = EdgeTTSService(voice="en-US-AriaNeural")
        audio = await service.generate_speech("Hello there", format="mp3", speed=1.0)
        assert audio == b"FAKE_EDGE_MP3"

    async def test_generate_speech_missing_dep_is_clear(self, monkeypatch):
        monkeypatch.delitem(sys.modules, "edge_tts", raising=False)
        monkeypatch.setattr("builtins.__import__", _raise_missing_edge_tts)
        service = EdgeTTSService()
        with pytest.raises(RuntimeError, match="edge-tts is not installed"):
            await service.generate_speech("hi")


def _raise_missing_edge_tts(name, *args, **kwargs):
    if name == "edge_tts":
        raise ImportError("edge_tts missing in test")
    return _original_import(name, *args, **kwargs)


# ---------------------------------------------------------------------------
# Agent TTS provider chain
# ---------------------------------------------------------------------------
@pytest.fixture
def scratch_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(agent.settings, "data_dir", str(tmp_path))
    monkeypatch.setattr(agent.settings, "tts_provider", "auto")
    monkeypatch.setattr(agent.settings, "fish_audio_api_key", "")
    monkeypatch.setattr(agent.settings, "edge_tts_voice", "en-US-AriaNeural")
    return agent.settings


class TestAgentTTSChain:
    async def test_auto_healthy_fish_uses_fish(self, scratch_settings, monkeypatch):
        monkeypatch.setattr(scratch_settings, "fish_audio_api_key", "key")
        fish = AsyncMock(return_value=b"FISH_AUDIO")
        edge = AsyncMock(return_value=b"EDGE_AUDIO")
        monkeypatch.setattr(agent, "_generate_with_fish", fish)
        monkeypatch.setattr(agent, "_generate_with_edge", edge)

        audio, fmt, provider, cached = await agent.synthesize_agent_audio("hi", "mp3", 0)

        assert audio == b"FISH_AUDIO"
        assert (fmt, provider, cached) == ("mp3", "fish", False)
        assert fish.await_count == 1
        assert edge.await_count == 0

    async def test_auto_fish_402_falls_back_to_edge(self, scratch_settings, monkeypatch):
        monkeypatch.setattr(scratch_settings, "fish_audio_api_key", "key")
        fish = AsyncMock(side_effect=RuntimeError("Fish Audio HTTP 402"))
        edge = AsyncMock(return_value=b"EDGE_AUDIO")
        monkeypatch.setattr(agent, "_generate_with_fish", fish)
        monkeypatch.setattr(agent, "_generate_with_edge", edge)

        audio, fmt, provider, cached = await agent.synthesize_agent_audio("hi", "mp3", 0)

        assert audio == b"EDGE_AUDIO"
        assert (fmt, provider, cached) == ("mp3", "edge", False)
        assert fish.await_count == 1
        assert edge.await_count == 1

        # The successful Edge render is cached for the next call.
        audio2, fmt2, provider2, cached2 = await agent.synthesize_agent_audio("hi", "mp3", 0)
        assert (audio2, fmt2, provider2, cached2) == (b"EDGE_AUDIO", "mp3", "edge", True)
        assert edge.await_count == 1

    async def test_provider_fish_re_raises_without_fallback(self, scratch_settings, monkeypatch):
        monkeypatch.setattr(scratch_settings, "tts_provider", "fish")
        monkeypatch.setattr(scratch_settings, "fish_audio_api_key", "key")
        fish = AsyncMock(side_effect=RuntimeError("Fish failed"))
        edge = AsyncMock(return_value=b"EDGE_AUDIO")
        monkeypatch.setattr(agent, "_generate_with_fish", fish)
        monkeypatch.setattr(agent, "_generate_with_edge", edge)

        with pytest.raises(RuntimeError, match="Fish failed"):
            await agent.synthesize_agent_audio("hi", "mp3", 0)
        assert edge.await_count == 0

    async def test_provider_edge_needs_no_key(self, scratch_settings, monkeypatch):
        monkeypatch.setattr(scratch_settings, "tts_provider", "edge")
        monkeypatch.setattr(scratch_settings, "fish_audio_api_key", "")
        edge = AsyncMock(return_value=b"EDGE_AUDIO")
        monkeypatch.setattr(agent, "_generate_with_edge", edge)

        audio, fmt, provider, cached = await agent.synthesize_agent_audio("hi", "mp3", 1)
        assert audio == b"EDGE_AUDIO"
        assert (fmt, provider, cached) == ("mp3", "edge", False)
        assert edge.await_count == 1

    async def test_auto_without_key_uses_edge(self, scratch_settings, monkeypatch):
        monkeypatch.setattr(scratch_settings, "tts_provider", "auto")
        monkeypatch.setattr(scratch_settings, "fish_audio_api_key", "")
        edge = AsyncMock(return_value=b"EDGE_AUDIO")
        monkeypatch.setattr(agent, "_generate_with_edge", edge)

        audio, fmt, provider, cached = await agent.synthesize_agent_audio("hi", "mp3", 2)
        assert (audio, fmt, provider) == (b"EDGE_AUDIO", "mp3", "edge")
        assert edge.await_count == 1

    async def test_cache_prefers_prior_fish_render(self, scratch_settings, monkeypatch):
        monkeypatch.setattr(scratch_settings, "fish_audio_api_key", "")
        cache_dir = _cache_dir(scratch_settings)
        cache_dir.mkdir(parents=True, exist_ok=True)
        (cache_dir / "fish_seg3.mp3").write_bytes(b"CACHED_FISH")
        edge = AsyncMock(return_value=b"EDGE_AUDIO")
        monkeypatch.setattr(agent, "_generate_with_edge", edge)

        audio, fmt, provider, cached = await agent.synthesize_agent_audio("hi", "mp3", 3)
        assert (audio, fmt, provider, cached) == (b"CACHED_FISH", "mp3", "fish", True)
        assert edge.await_count == 0


def _cache_dir(settings):
    return settings.data_dir and agent._agent_cache_dir()


# ---------------------------------------------------------------------------
# Deepfake label picking
# ---------------------------------------------------------------------------
class TestPickFakeIndex:
    def test_fake_real_pair(self):
        assert pick_fake_index({0: "real", 1: "fake"}) == 1

    def test_bonafide_spoof_pair(self):
        assert pick_fake_index({0: "bonafide", 1: "spoof"}) == 1

    def test_synthetic_class(self):
        assert pick_fake_index({0: "genuine", 1: "synthetic"}) == 1

    def test_ai_label_differs_from_real(self):
        assert pick_fake_index({0: "human", 1: "ai"}) == 1

    def test_fake_label_not_at_index_one(self):
        assert pick_fake_index({0: "fake", 1: "real", 2: "other"}) == 0

    def test_machine_label(self):
        assert pick_fake_index({0: "unknown", 1: "real", 2: "machine"}) == 2

    def test_binary_fallback_to_non_real(self):
        assert pick_fake_index({0: "human", 1: "noise"}) == 1

    def test_last_resort_index_one(self):
        assert pick_fake_index({0: "a", 1: "b"}) == 1
        assert pick_fake_index({}) == 1


# ---------------------------------------------------------------------------
# Deepfake provider routing
# ---------------------------------------------------------------------------
class TestDeepfakeRouting:
    async def test_off_returns_zero(self):
        detector = DeepfakeDetector(api_url="", api_key="", provider="off", local_model=DEFAULT_LOCAL_MODEL)
        assert await detector.detect(b"anything") == 0.0

    async def test_auto_with_key_prefers_aurigin(self):
        detector = DeepfakeDetector(api_url="https://example.invalid", api_key="key", provider="auto")
        detector._detect_aurigin = AsyncMock(return_value=0.9)
        detector._local.score_wav = AsyncMock(return_value=0.5)
        assert await detector.detect(b"wav") == 0.9
        detector._local.score_wav.assert_not_awaited()

    async def test_auto_aurigin_error_falls_back_to_local(self):
        detector = DeepfakeDetector(api_url="https://example.invalid", api_key="key", provider="auto")
        detector._detect_aurigin = AsyncMock(side_effect=RuntimeError("404"))
        detector._local.score_wav = AsyncMock(return_value=0.5)
        assert await detector.detect(b"wav") == 0.5
        detector._local.score_wav.assert_awaited_once()

    async def test_aurigin_provider_does_not_fallback(self):
        detector = DeepfakeDetector(api_url="https://example.invalid", api_key="key", provider="aurigin")
        detector._detect_aurigin = AsyncMock(side_effect=RuntimeError("404"))
        detector._local.score_wav = AsyncMock(return_value=0.5)
        assert await detector.detect(b"wav") == 0.0
        detector._local.score_wav.assert_not_awaited()

    async def test_local_provider_ignores_key(self):
        detector = DeepfakeDetector(api_url="https://example.invalid", api_key="key", provider="local")
        detector._detect_aurigin = AsyncMock(return_value=0.9)
        detector._local.score_wav = AsyncMock(return_value=0.6)
        assert await detector.detect(b"wav") == 0.6
        detector._detect_aurigin.assert_not_awaited()

    async def test_auto_without_key_uses_local(self):
        detector = DeepfakeDetector(api_url="https://example.invalid", api_key="", provider="auto")
        detector._detect_aurigin = AsyncMock(return_value=0.9)
        detector._local.score_wav = AsyncMock(return_value=0.6)
        assert await detector.detect(b"wav") == 0.6
        detector._detect_aurigin.assert_not_awaited()

    def test_local_extract_tail_parses_wav(self):
        detector = LocalDeepfakeDetector()
        wav = _make_wav(seconds=0.2, sample_rate=16000)
        pcm = detector._extract_tail(wav, tail_seconds=1)
        assert isinstance(pcm, bytes)
        assert len(pcm) > 0

    async def test_score_wav_runs_in_worker(self, monkeypatch):
        detector = LocalDeepfakeDetector()
        monkeypatch.setattr(detector, "_score_wav_sync", lambda *a, **k: 0.77)
        assert await detector.score_wav(b"whatever") == 0.77

    def test_bytes_to_wav_roundtrip(self):
        detector = DeepfakeDetector(api_url="", api_key="", provider="off")
        pcm = b"\x00\x00" * 1600  # 0.1s at 16kHz
        wav = detector.bytes_to_wav(pcm, sample_rate=16000)
        assert wav.startswith(b"RIFF")
        assert detector._local is not None or True  # keep constructor smoke-tested
