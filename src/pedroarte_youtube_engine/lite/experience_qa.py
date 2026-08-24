"""Gate 3D.1 SLICE F — Experience QA.

Media QA (`lite/qa.py`) pergunta "o arquivo é tecnicamente válido?".
Experience QA pergunta "a timeline produzida satisfaz estruturalmente o
contrato de experiência de publicação?" — nenhum dos dois pergunta "é
bonito?"/"é envolvente?": isso é sempre Human Full Watch.

Duas camadas de QA de movimento, como exigido (§22 do briefing de
implementação): `MOTION_CONFIGURATION_QA` (parâmetros, antes de renderizar)
e `MOTION_RENDER_REGRESSION_QA` (pixel real, depois de renderizar) — QA de
parâmetro sozinha NÃO teria pego o bug do Gate 3D.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from pedroarte_youtube_engine.lite.audio_qa import probe_audio
from pedroarte_youtube_engine.lite.captions import APPROX_MAX_DISPLAY_CHARS, Cue, CaptionStyle
from pedroarte_youtube_engine.lite.retention import (
    RetentionSegment,
    TOLERATED_MAX_STATIC_WINDOW_SECONDS,
    GATE_3D1_EXPERIMENTAL_MIN_ZOOM_RATE_PER_SECOND,
    segments_share_continuous_trajectory,
)
from pedroarte_youtube_engine.lite.visual_beats import VisualBeat


@dataclass(slots=True)
class ExperienceQaCheck:
    name: str
    passed: bool
    detail: str = ""


@dataclass(slots=True)
class ExperienceQaReport:
    checks: list[ExperienceQaCheck] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)

    def as_dict(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "checks": [{"name": c.name, "passed": c.passed, "detail": c.detail} for c in self.checks],
        }


def check_timeline_visual_coverage(beats: list[VisualBeat], *, total_duration_seconds: float) -> ExperienceQaCheck:
    from pedroarte_youtube_engine.lite.visual_plan_gate3d import validate_plan_coverage

    report = validate_plan_coverage(tuple(beats), total_duration_seconds=total_duration_seconds)
    return ExperienceQaCheck("timeline_visual_coverage", report["status"] == "PASS", str(report["gaps"]))


def check_total_unique_images(image_count: int, *, target: int) -> ExperienceQaCheck:
    return ExperienceQaCheck(
        "total_unique_images", image_count >= target, f"{image_count} >= {target}?"
    )


def check_max_seconds_without_visual_event(
    retention_plans: dict[str, tuple[RetentionSegment, ...]],
    *,
    threshold_seconds: float = TOLERATED_MAX_STATIC_WINDOW_SECONDS,
) -> ExperienceQaCheck:
    worst = 0.0
    worst_beat = ""
    for beat_id, segments in retention_plans.items():
        for segment in segments:
            if segment.contemplative:
                continue
            if segment.duration_seconds > worst:
                worst = segment.duration_seconds
                worst_beat = beat_id
    return ExperienceQaCheck(
        "max_seconds_without_visual_event",
        worst <= threshold_seconds,
        f"pior janela={worst:.1f}s em {worst_beat} (limiar={threshold_seconds}s)",
    )


def check_motion_configuration(
    retention_plans: dict[str, tuple[RetentionSegment, ...]],
    *,
    min_rate: float = GATE_3D1_EXPERIMENTAL_MIN_ZOOM_RATE_PER_SECOND,
) -> ExperienceQaCheck:
    """Camada 1 — parâmetro. Sozinha, insuficiente (não teria pego o bug do
    Gate 3D — ver `check_motion_render_regression`)."""
    total = 0
    below_floor = []
    for beat_id, segments in retention_plans.items():
        for segment in segments:
            total += 1
            rate = abs(segment.zoom_delta) / segment.duration_seconds if segment.duration_seconds else 0.0
            has_pan = segment.pan_dx_fraction != 0 or segment.pan_dy_fraction != 0
            # tolerância de ponto flutuante: o piso é construído a partir do
            # mesmo `rate_per_second` (ver compute_zoom_delta) — sem folga,
            # ruído de arredondamento derrubaria segmentos exatamente no limiar.
            if rate < min_rate * 0.999 and not has_pan:
                below_floor.append(f"{beat_id}:{segment.kind.value}")
    coverage = (total - len(below_floor)) / total if total else 0.0
    return ExperienceQaCheck(
        "motion_configuration_coverage",
        coverage >= 0.95,
        f"{coverage:.1%} dos segmentos acima do piso de movimento configurado; abaixo: {below_floor[:5]}",
    )


def check_motion_render_regression(sample_yavg_measurements: dict[str, float], *, min_yavg: float = 1.0) -> ExperienceQaCheck:
    """Camada 2 — pixel real, sobre uma amostra de segmentos já renderizados
    (não recalcula os 30 beats inteiros aqui — isso é o papel do teste de
    regressão permanente, `tests/lite/test_motion_regression.py`, e do
    Motion Proof). Aqui só se agrega o resultado já medido."""
    failing = {k: v for k, v in sample_yavg_measurements.items() if v < min_yavg}
    return ExperienceQaCheck(
        "motion_render_regression_sample",
        not failing,
        f"amostras abaixo do piso ({min_yavg}): {failing}" if failing else "todas as amostras com movimento real",
    )


def check_caption_rechunk_valid(cues: tuple[Cue, ...], *, max_chars: int = APPROX_MAX_DISPLAY_CHARS) -> ExperienceQaCheck:
    too_long = [c.index for c in cues if len(c.text) > max_chars]
    non_monotonic = [c.index for c in cues if c.end_seconds <= c.start_seconds]
    ok = not too_long and not non_monotonic
    return ExperienceQaCheck(
        "caption_rechunk_valid",
        ok,
        f"too_long={too_long[:5]} non_monotonic={non_monotonic[:5]}",
    )


def check_caption_style_config_valid(style: CaptionStyle) -> ExperienceQaCheck:
    ok = (
        0.02 <= style.font_size_fraction_of_height <= 0.08
        and 0.03 <= style.bottom_margin_fraction <= 0.15
        and style.outline_width > 0
    )
    return ExperienceQaCheck("caption_style_config_valid", ok, str(style))


def check_burned_caption_render_step(*, pre_burn_path: Path, post_burn_path: Path) -> ExperienceQaCheck:
    """Verificação de processo (Gate 3D.1 §21 — detecção de pixel/OCR está
    fora de escopo). O passo é considerado completo se o comando terminou
    com sucesso (arquivo existe) e o tamanho mudou de forma consistente com
    reencode + queima (não é uma cópia idêntica do arquivo anterior)."""
    if not post_burn_path.exists():
        return ExperienceQaCheck("burned_caption_render_step_completed", False, "arquivo não existe")
    changed = post_burn_path.stat().st_size != (pre_burn_path.stat().st_size if pre_burn_path.exists() else -1)
    return ExperienceQaCheck("burned_caption_render_step_completed", changed, f"size={post_burn_path.stat().st_size}")


def check_cumulative_zoom_progression(retention_plans: dict[str, tuple[RetentionSegment, ...]]) -> ExperienceQaCheck:
    """Gate 3D.2 §26 — substitui/complementa `check_motion_configuration`
    (que só verifica taxa por segmento) respondendo diretamente às duas
    perguntas do mandato: o zoom ACUMULA ao longo do Visual Beat inteiro, e
    os Retention Segments NÃO resetam a trajetória da câmera entre si? Um
    beat de um único segmento é trivialmente contínuo (nada para resetar)."""
    resetting_beats = [
        beat_id for beat_id, segments in retention_plans.items() if not segments_share_continuous_trajectory(segments)
    ]
    coverage = (len(retention_plans) - len(resetting_beats)) / len(retention_plans) if retention_plans else 0.0
    return ExperienceQaCheck(
        "cumulative_zoom_progression",
        not resetting_beats,
        f"{coverage:.1%} dos beats com trajetória de zoom contínua (sem reset); com reset: {resetting_beats[:5]}",
    )


def check_music_stem_relative_level(
    *,
    narration_stem_mean_db: float,
    music_stem_mean_db_after_gain: float,
    min_relative_db: float = -20.0,
    max_relative_db: float = -3.0,
) -> ExperienceQaCheck:
    """Gate 3D.2 §25 — substitui o critério anterior (diferença de nível
    médio da MIXAGEM FINAL vs. narração pura), que o feedback humano provou
    insuficiente: a narração domina o nível médio total, então uma pequena
    diferença ali não prova audibilidade real da música. Aqui a comparação é
    STEM a STEM (música já com ganho aplicado, medida isoladamente, vs. a
    narração isolada) — a quantidade que realmente importa, por (§14/§15 do
    mandato do Gate 3D.2)."""
    relative_db = music_stem_mean_db_after_gain - narration_stem_mean_db
    ok = min_relative_db <= relative_db <= max_relative_db
    return ExperienceQaCheck(
        "music_stem_relative_level",
        ok,
        f"stem de música {relative_db:+.2f}dB relativo ao stem de narração (faixa alvo [{min_relative_db}, {max_relative_db}]dB)",
    )


def check_background_music_mix_step(*, narration_only_mean_db: float, mixed_mean_db: float) -> ExperienceQaCheck:
    """SUPERSEDIDO no render final pelo Gate 3D.2 por
    `check_music_stem_relative_level` (o feedback humano do Gate 3D.1 provou
    que este critério — nível médio da MIXAGEM vs. narração pura — não
    prova audibilidade real: a narração domina o nível médio total). Mantido
    aqui por compatibilidade com testes/chamadores existentes.

    Verificação por nível de energia — se a música está presente e não
    silenciada, o nível médio da mixagem deve diferir mensuravelmente do
    nível da narração pura (mesmo com narração dominante)."""
    diff = abs(mixed_mean_db - narration_only_mean_db)
    return ExperienceQaCheck(
        "background_music_mix_step_completed",
        diff >= 0.1,
        f"diferença de nível médio narração-só vs. mixado: {diff:.2f}dB",
    )


def check_final_audio_no_clipping(audio_path: Path) -> ExperienceQaCheck:
    metrics = probe_audio(audio_path)
    ok = (metrics.max_volume_db or 0.0) <= 0.0
    return ExperienceQaCheck("final_audio_no_clipping", ok, f"max_volume={metrics.max_volume_db}dB")
