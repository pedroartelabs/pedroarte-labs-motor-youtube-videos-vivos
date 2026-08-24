"""Gate 3D.1 SLICE D — trilha de fundo e mixagem.

Nenhum Music Agent/Composer/Swarm — uma única função determinística que
sintetiza uma cama ambiente original (3 tons graves levemente dessintonizados
+ tremolo lento + filtro passa-baixa) via geradores nativos do FFmpeg
(`sine`, `tremolo`, `lowpass`). É um asset **original, gerado por código**,
sem nenhuma fonte de terceiros — categoria explicitamente aceita em
GATE_3D_POSTMORTEM_AND_3D1_PLAN.md §16 ("original/generated asset with
publication rights"), o que evita o bloqueio de licenciamento de música de
terceiros sem abrir mão do requisito de música de fundo.

Mixagem: narração é sempre dominante (SDD_SPDD.md/Gate 3D.1 §17) — nível de
música fixo e baixo, sem ducking (adiado, conforme autorizado).
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from pedroarte_youtube_engine.lite.audio_qa import probe_audio
from pedroarte_youtube_engine.lite.ffmpeg_assembler import _run_ffmpeg, resolve_ffmpeg_binary
from pedroarte_youtube_engine.shared.errors import EngineError

# Calibrado empiricamente (Gate 3D.1 §17: "não congelar -26/-30dB como
# constante universal — calibrar empiricamente"): a cama gerada por
# `generate_ambient_bed` já nasce quieta por construção (mean_volume medido
# ≈ -48dB, ver GATE_3D1_IMPLEMENTATION_REPORT.md §10). Um valor POSITIVO
# aqui não é um erro de sinal — é o ajuste necessário a partir dessa base já
# baixa para chegar a um nível final de mixagem claramente subordinado à
# narração real (≈-21dB), mas não inaudível. Medido: -28dB (negativo) sobre
# a cama já quieta produzia diferença de nível médio ≈0.00dB na mixagem
# final — música efetivamente ausente, não apenas discreta.
DEFAULT_MUSIC_GAIN_DB = 12.0
DEFAULT_FADE_SECONDS = 3.0

# Gate 3D.2 — redesenho pós-feedback humano ("confundindo a voz do
# narrador com a música"). Medição real sobre a narração aprovada
# (GATE_3D2_CALIBRATION_REPORT.md, investigação de espectro): energia
# concentrada em 80-3000Hz (fundamental 80-300Hz ≈ -26.1dB médio, formantes
# 300-3000Hz ≈ -23.1dB médio — a banda dominante), quase silenciosa abaixo
# de 80Hz (-40.7dB) e acima de 3000Hz (-36.3dB). O desenho anterior (3 tons
# em 110/164.5/220Hz) caía EXATAMENTE dentro da faixa fundamental da voz —
# por isso a música, mesmo em nível audível, se misturava perceptualmente
# com a narração em vez de ser reconhecida como uma camada separada.
#
# Novo desenho: ocupa as duas faixas onde a narração está praticamente
# ausente — um sub-grave sentido mais do que ouvido (abaixo de 80Hz) e um
# shimmer agudo (acima de 3000Hz) — deixando o "bolso vocal" (80-3000Hz)
# livre. É a técnica padrão de produção para pads que precisam coexistir
# com diálogo/narração sem entrar em conflito espectral.
_SUB_FREQUENCY_HZ = 55.0  # A1 — abaixo do piso de energia vocal medido
_SHIMMER_FREQUENCIES_HZ = (3520.0, 4698.63)  # A7 / D8 — acima do teto de energia vocal medido


@dataclass(frozen=True, slots=True)
class MixResult:
    output_path: Path
    music_gain_db: float
    render_time_seconds: float


def generate_ambient_bed(*, duration_seconds: float, output_path: Path, sample_rate: int = 44100) -> Path:
    """Sintetiza uma cama ambiente original de `duration_seconds` — sem
    melodia, sem voz, apropriada para "mistério/realismo mágico contido"
    (Gate 3D.1 §19). 100% gerada, sem risco de licenciamento de terceiros.

    Espectralmente afastada da voz por construção (ver constantes acima):
    sub-grave (`_SUB_FREQUENCY_HZ`, filtrado apenas por sua própria
    frequência baixa) + shimmer agudo (`_SHIMMER_FREQUENCIES_HZ`, reforçado
    com `highpass=f=3000` para garantir que nenhuma energia caia na faixa
    vocal mesmo com a modulação de `chorus`/`tremolo`). `chorus` dá textura
    "viva"/de pad sem introduzir melodia ou voz."""
    ffmpeg = resolve_ffmpeg_binary("ffmpeg")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    duration = f"{duration_seconds:.3f}"

    inputs = ["-f", "lavfi", "-i", f"sine=frequency={_SUB_FREQUENCY_HZ}:duration={duration}:sample_rate={sample_rate}"]
    for freq in _SHIMMER_FREQUENCIES_HZ:
        inputs += ["-f", "lavfi", "-i", f"sine=frequency={freq}:duration={duration}:sample_rate={sample_rate}"]

    filter_complex = (
        "[0:a]volume=0.34[sub];"
        "[1:a]volume=0.09,highpass=f=3000[sh0];"
        "[2:a]volume=0.065,highpass=f=3000[sh1];"
        "[sub][sh0][sh1]amix=inputs=3:duration=longest[mixed];"
        "[mixed]tremolo=f=0.15:d=0.2,"
        "chorus=0.6:0.9:55|60|65:0.4|0.4|0.4:0.25|0.3|0.35:2|2.5|3[out]"
    )

    command = (
        ffmpeg, "-y", *inputs,
        "-filter_complex", filter_complex,
        "-map", "[out]",
        "-ac", "2", "-ar", str(sample_rate),
        str(output_path),
    )
    _run_ffmpeg(command, timeout=180)
    if not output_path.exists():
        raise EngineError("Cama ambiente não foi gerada.", output_path=str(output_path))
    return output_path


def render_music_stem(
    *,
    music_path: Path,
    output_path: Path,
    music_gain_db: float,
    narration_duration_seconds: float,
    fade_seconds: float = DEFAULT_FADE_SECONDS,
) -> Path:
    """Gate 3D.2 §15 — renderiza o stem de música APÓS o ganho aplicado,
    isolado (sem narração), para medir seu nível real de forma independente
    do nível médio da mixagem final (que a narração dominante mascara — essa
    é exatamente a lição do achado humano do Gate 3D.1: uma mixagem com
    diferença de 0.30dB no nível médio NÃO prova que a música é audível)."""
    ffmpeg = resolve_ffmpeg_binary("ffmpeg")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fade_out_start = max(0.0, narration_duration_seconds - fade_seconds)
    filter_complex = (
        f"[0:a]volume={music_gain_db}dB,"
        f"afade=t=in:st=0:d={fade_seconds},"
        f"afade=t=out:st={fade_out_start:.3f}:d={fade_seconds}:curve=tri,"
        f"atrim=0:{narration_duration_seconds:.3f}[out]"
    )
    command = (
        ffmpeg, "-y",
        "-i", str(music_path),
        "-filter_complex", filter_complex,
        "-map", "[out]",
        "-c:a", "libmp3lame", "-q:a", "2",
        str(output_path),
    )
    _run_ffmpeg(command, timeout=120)
    if not output_path.exists():
        raise EngineError("Stem de música não foi gerado.", output_path=str(output_path))
    return output_path


def compute_gain_for_relative_offset(
    *,
    narration_mean_db: float,
    raw_music_mean_db: float,
    target_relative_offset_db: float,
) -> float:
    """Gate 3D.2 §17 — NUNCA escolher um ganho absoluto às cegas (ex.: -26,
    -22, -18 fixos). Em vez disso, deriva o ganho necessário a partir do
    nível REAL medido da cama bruta para que o stem de música, após o ganho,
    fique a `target_relative_offset_db` (negativo = mais silencioso) do
    nível médio real da narração. `target_relative_offset_db=-12` significa
    "música 12dB mais silenciosa que a narração", não um valor absoluto."""
    target_music_mean_db = narration_mean_db + target_relative_offset_db
    return target_music_mean_db - raw_music_mean_db


def mix_narration_with_music(
    *,
    narration_path: Path,
    music_path: Path,
    output_path: Path,
    music_gain_db: float = DEFAULT_MUSIC_GAIN_DB,
    fade_seconds: float = DEFAULT_FADE_SECONDS,
) -> MixResult:
    """Narração inalterada (autoridade); música em nível fixo baixo, com
    fade-in/out limpo. Sem ducking (Gate 3D.1 §17/§22 — adiado)."""
    ffmpeg = resolve_ffmpeg_binary("ffmpeg")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    narration_duration = probe_audio(narration_path).duration_seconds
    fade_out_start = max(0.0, narration_duration - fade_seconds)

    filter_complex = (
        f"[1:a]volume={music_gain_db}dB,"
        f"afade=t=in:st=0:d={fade_seconds},"
        f"afade=t=out:st={fade_out_start:.3f}:d={fade_seconds}:curve=tri[music];"
        # normalize=0: sem isso, `amix` divide o nível geral pelo número de
        # entradas por padrão — o que deixaria a narração mais baixa do que
        # sozinha, mesmo já dominante em ganho. Com normalize=0, a mixagem é
        # a soma direta dos dois sinais já ajustados (narração no ganho
        # original + música já atenuada por `music_gain_db`).
        f"[0:a][music]amix=inputs=2:duration=first:normalize=0[out]"
    )
    command = (
        ffmpeg, "-y",
        "-i", str(narration_path), "-i", str(music_path),
        "-filter_complex", filter_complex,
        "-map", "[out]",
        "-c:a", "libmp3lame", "-q:a", "2",
        str(output_path),
    )
    start = time.monotonic()
    _run_ffmpeg(command, timeout=180)
    elapsed = time.monotonic() - start
    if not output_path.exists():
        raise EngineError("Mixagem não produziu arquivo.", output_path=str(output_path))
    return MixResult(output_path=output_path, music_gain_db=music_gain_db, render_time_seconds=elapsed)
