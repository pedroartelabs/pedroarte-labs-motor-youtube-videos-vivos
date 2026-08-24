"""Gate 3B — unidades puras/técnicas: NarrationRequest/Result, QA de áudio via
ffprobe sobre um WAV sintético (sem depender de SAPI5/edge-tts, que exigem
SO/rede reais), e validade de um `voice_candidates.json` real já produzido
pelo bake-off. Naturalidade/qualidade de voz NÃO é testada aqui — é sempre
Human Gate (regra 32 do briefing do Gate 3B)."""

from __future__ import annotations

import json
import math
import struct
import wave
from pathlib import Path

import pytest

from pedroarte_youtube_engine.lite.audio_qa import probe_audio
from pedroarte_youtube_engine.lite.narration.ports import NarrationRequest, NarrationResult


def _write_synthetic_wav(path: Path, *, seconds: float = 1.0, sample_rate: int = 22050) -> None:
    """Um tom senoidal curto — áudio real e inspecionável, sem TTS nenhum."""
    n_samples = int(seconds * sample_rate)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        frames = bytearray()
        for i in range(n_samples):
            value = int(8000 * math.sin(2 * math.pi * 440 * i / sample_rate))
            frames += struct.pack("<h", value)
        handle.writeframes(bytes(frames))


class TestNarrationContract:
    def test_narration_request_accepts_optional_voice(self, tmp_path: Path) -> None:
        request = NarrationRequest(
            text="ola mundo", output_path=tmp_path / "x.wav", voice="pt-BR-FranciscaNeural"
        )
        assert request.voice == "pt-BR-FranciscaNeural"
        assert request.language == "pt-BR"

    def test_narration_result_defaults(self, tmp_path: Path) -> None:
        result = NarrationResult(
            output_path=tmp_path / "x.wav", duration_seconds=1.5, method="local:sapi5"
        )
        assert result.generation_time_seconds == 0.0
        assert result.timing_data_available is False


class TestAudioQa:
    def test_probe_audio_on_synthetic_wav(self, tmp_path: Path) -> None:
        wav_path = tmp_path / "tone.wav"
        _write_synthetic_wav(wav_path, seconds=1.0)
        metrics = probe_audio(wav_path)
        assert metrics.duration_seconds == pytest.approx(1.0, abs=0.05)
        assert metrics.sample_rate == 22050
        assert metrics.channels == 1
        assert metrics.file_size_bytes > 0

    def test_probe_audio_raises_on_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(Exception):
            probe_audio(tmp_path / "does_not_exist.wav")


def _latest_gate3b_candidates_path() -> Path | None:
    matches = sorted(Path("runs").glob("*-gate3b-voice/working/voice_candidates.json"))
    return matches[-1] if matches else None


class TestVoiceCandidatesArtifact:
    """Valida a forma do `voice_candidates.json` da execução real mais
    recente do bake-off (não regenera áudio — só audita o artefato existente)."""

    def test_candidate_mapping_has_three_letters(self) -> None:
        path = _latest_gate3b_candidates_path()
        if path is None:
            pytest.skip("Nenhuma execução real do Gate 3B disponível neste ambiente.")
        mapping = json.loads(path.read_text(encoding="utf-8"))
        assert set(mapping.keys()) == {"A", "B", "C"}

    def test_all_candidates_used_the_same_text(self) -> None:
        path = _latest_gate3b_candidates_path()
        if path is None:
            pytest.skip("Nenhuma execução real do Gate 3B disponível neste ambiente.")
        mapping = json.loads(path.read_text(encoding="utf-8"))
        hashes = {entry["text_sha256"] for entry in mapping.values()}
        assert len(hashes) == 1, "Todos os candidatos devem narrar exatamente o mesmo texto."

    def test_candidate_output_paths_do_not_leak_provider_in_filename(self) -> None:
        path = _latest_gate3b_candidates_path()
        if path is None:
            pytest.skip("Nenhuma execução real do Gate 3B disponível neste ambiente.")
        mapping = json.loads(path.read_text(encoding="utf-8"))
        for letter, entry in mapping.items():
            filename = Path(entry["output_path"]).name
            assert filename.startswith(f"voice_{letter}.")
            assert "sapi" not in filename.lower()
            assert "edge" not in filename.lower()
            assert "francisca" not in filename.lower()
            assert "antonio" not in filename.lower()
