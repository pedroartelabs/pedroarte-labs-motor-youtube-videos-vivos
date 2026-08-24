"""Retention Beats (Gate 3D.1, SLICE B) — eventos audiovisuais perceptíveis
dentro de um Visual Beat. NÃO é um Effects Engine: só 4 tipos de evento
determinísticos (zoom in/out, pan, reframe), gerados por um algoritmo simples
baseado em duração, não uma biblioteca de efeitos configurável.

Causa raiz do bug do Gate 3D (docs/youtube-lite/GATE_3D_POSTMORTEM_AND_3D1_PLAN.md
§6): o zoom nunca era realmente progressivo porque o filtro `zoompan` era
alimentado com `-framerate {fps}` sobre `-loop 1` + `d=1` — combinação que
quebra o estado interno do filtro. A correção estrutural mora em
`ffmpeg_assembler.render_retention_segment`; este módulo só decide OS
parâmetros (duração, direção, delta de zoom), não a mecânica do FFmpeg.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

# Piso experimental do Gate 3D.1 (docs/.../GATE_3D_POSTMORTEM_AND_3D1_PLAN.md §23) —
# NÃO uma constante permanente do YouTube Lite. Derivado empiricamente do teste
# lado a lado do postmortem (receita corrigida ~25 YAVG de diferença perceptível
# vs. ~0.01 da receita quebrada).
GATE_3D1_EXPERIMENTAL_MIN_ZOOM_RATE_PER_SECOND = 0.004

# Teto de delta de zoom total por segmento — acima disso o movimento deixa de
# parecer "contido" (nota qualitativa do postmortem §25).
MAX_TOTAL_ZOOM_DELTA = 0.16

# Janela alvo de evento perceptível (Gate 3D.1 §9 do briefing de implementação).
TARGET_MAX_STATIC_WINDOW_SECONDS = 7.0
TOLERATED_MAX_STATIC_WINDOW_SECONDS = 10.0


class RetentionKind(StrEnum):
    ZOOM_IN = "zoom_in"
    ZOOM_OUT = "zoom_out"
    PAN = "pan"
    REFRAME = "reframe"


@dataclass(frozen=True, slots=True)
class RetentionSegment:
    kind: RetentionKind
    duration_seconds: float
    start_scale: float
    end_scale: float
    # Fração da MARGEM DE RECORTE disponível no zoom atual (não da largura do
    # frame) — 0.0 = centro, ±1.0 = extremo da margem segura. Garante que o
    # pan nunca sai dos limites da imagem, qualquer que seja o zoom aplicado.
    pan_dx_fraction: float = 0.0
    pan_dy_fraction: float = 0.0
    contemplative: bool = False  # INTENTIONAL_CONTEMPLATIVE_HOLD — isento do teto de janela estática

    @property
    def zoom_delta(self) -> float:
        return self.end_scale - self.start_scale


def compute_zoom_delta(
    duration_seconds: float,
    *,
    rate_per_second: float = GATE_3D1_EXPERIMENTAL_MIN_ZOOM_RATE_PER_SECOND,
    max_total_delta: float = MAX_TOTAL_ZOOM_DELTA,
) -> float:
    """Zoom que percorre a duração INTEIRA do segmento — nunca satura cedo
    (causa raiz secundária do Gate 3D, postmortem §7: max_zoom fixo saturava
    em ~8s independente da duração do beat)."""
    return min(rate_per_second * duration_seconds, max_total_delta)


def build_default_retention_plan(
    duration_seconds: float,
    *,
    target_chunk_seconds: float = TARGET_MAX_STATIC_WINDOW_SECONDS,
    contemplative_threshold_seconds: float = TOLERATED_MAX_STATIC_WINDOW_SECONDS,
) -> tuple[RetentionSegment, ...]:
    """Algoritmo determinístico: beats curtos (<=10s) recebem um único
    Retention Segment (zoom contínuo cobrindo tudo). Beats mais longos são
    divididos em ~7s, alternando ZOOM_IN/ZOOM_OUT/PAN — a alternância de
    direção É o evento perceptível na fronteira de cada chunk, sem exigir
    imagem nova (Gate 3D.1 §11: "Motion Proof Before New Images")."""
    if duration_seconds <= contemplative_threshold_seconds:
        delta = compute_zoom_delta(duration_seconds)
        return (
            RetentionSegment(
                kind=RetentionKind.ZOOM_IN,
                duration_seconds=duration_seconds,
                start_scale=1.0,
                end_scale=1.0 + delta,
                contemplative=duration_seconds > TARGET_MAX_STATIC_WINDOW_SECONDS,
            ),
        )

    chunk_count = max(2, round(duration_seconds / target_chunk_seconds))
    chunk_duration = duration_seconds / chunk_count
    kinds = [RetentionKind.ZOOM_IN, RetentionKind.PAN, RetentionKind.ZOOM_OUT, RetentionKind.REFRAME]

    segments: list[RetentionSegment] = []
    for i in range(chunk_count):
        kind = kinds[i % len(kinds)]
        delta = compute_zoom_delta(chunk_duration, max_total_delta=MAX_TOTAL_ZOOM_DELTA / 2)
        if kind is RetentionKind.ZOOM_IN:
            segments.append(
                RetentionSegment(kind=kind, duration_seconds=chunk_duration, start_scale=1.0, end_scale=1.0 + delta)
            )
        elif kind is RetentionKind.ZOOM_OUT:
            segments.append(
                RetentionSegment(
                    kind=kind, duration_seconds=chunk_duration, start_scale=1.0 + delta, end_scale=1.0
                )
            )
        elif kind is RetentionKind.PAN:
            # zoom leve para abrir margem de recorte para o pan; pan_dx_fraction
            # perto do extremo da margem (±0.85) para ficar claramente visível
            # sem risco de sair da imagem (a margem em si escala com o zoom).
            segments.append(
                RetentionSegment(
                    kind=kind,
                    duration_seconds=chunk_duration,
                    start_scale=1.05,
                    end_scale=1.05,
                    pan_dx_fraction=0.85 if i % 2 == 0 else -0.85,
                )
            )
        else:  # REFRAME — pequeno reenquadramento vertical com leve zoom
            segments.append(
                RetentionSegment(
                    kind=kind,
                    duration_seconds=chunk_duration,
                    start_scale=1.05,
                    end_scale=1.05,
                    pan_dy_fraction=0.7,
                )
            )
    return tuple(segments)


def max_static_window_seconds(segments: tuple[RetentionSegment, ...]) -> float:
    """Maior janela contígua sem transição de Retention Segment — segmentos
    marcados `contemplative` não contam para o teto (Gate 3D.1 §9)."""
    windows = [s.duration_seconds for s in segments if not s.contemplative]
    return max(windows) if windows else 0.0


# ============================================================================
# GATE 3D.2 — PROGRESSIVE DEPTH MOTION
#
# Achado de investigação (docs/youtube-lite/GATE_3D2_CALIBRATION_REPORT.md §3):
# `build_default_retention_plan` gera cada Retention Segment com seu próprio
# `start_scale` independente (1.0 para zoom_in/zoom_out, 1.05 constante para
# pan/reframe) — ou seja, a escala PULA entre segmentos em vez de continuar
# de onde o segmento anterior parou (ex.: beat_26: 1.0→1.029 (zoom_in), depois
# SALTO para 1.05 constante (pan), depois SALTO para baixo 1.029→1.0
# (zoom_out)). O delta de zoom também é calculado por CHUNK, não pelo beat
# inteiro, então o zoom nunca acumula além de ~3-4% mesmo em beats de 30+s.
# Isso explica por que YAVG≈11 (movimento real, quadro-a-quadro) coexistia
# com a percepção humana de "zoom insuficiente" — o pixel se move, mas a
# câmera nunca parece avançar cumulativamente na cena.
#
# `build_continuous_push_in_plan` corrige isso: UMA trajetória de escala
# contínua cobre o beat INTEIRO (1.0 → 1.0+total_zoom_ratio); os Retention
# Segments passam a ser apenas fatias de TEMPO dessa mesma trajetória (cada
# segmento começa exatamente onde o anterior terminou), com pan/reframe
# leves camadas OPCIONAIS sobre a trajetória de zoom em vez de substituí-la.
# ============================================================================

# Valores de referência para o bake-off de calibração (Gate 3D.2 §11) — NÃO
# são a resposta final; a resposta final é escolhida pelo humano entre as
# variantes A/B/C. "Moderate" ~dobra a percepção de profundidade acumulada
# em relação ao comportamento anterior (que nunca passava de ~3-4% líquido);
# "strong" ainda fica bem abaixo do teto qualitativo de "parece zoom digital
# agressivo" (~0.30-0.40 de delta total em poucos segundos).
GATE_3D2_CALIBRATION_TOTAL_ZOOM_RATIO_MODERATE = 0.12
GATE_3D2_CALIBRATION_TOTAL_ZOOM_RATIO_STRONG = 0.22


def compute_continuous_zoom_end_scale(
    duration_seconds: float,
    *,
    total_zoom_ratio: float,
) -> float:
    return 1.0 + total_zoom_ratio


def _smoothstep(t: float) -> float:
    """3t²-2t³ — acelera suavemente a partir do repouso, desacelera
    suavemente até o repouso. Derivada zero em t=0 e t=1."""
    return t * t * (3.0 - 2.0 * t)


def build_continuous_push_in_plan(
    duration_seconds: float,
    *,
    total_zoom_ratio: float,
    chunk_seconds: float = TARGET_MAX_STATIC_WINDOW_SECONDS,
    pan_dx_fraction_on_middle_chunks: float = 0.35,
    ease_in_out: bool = False,
) -> tuple[RetentionSegment, ...]:
    """Uma única trajetória de zoom contínua (`1.0 -> 1.0+total_zoom_ratio`)
    cobrindo o beat inteiro, fatiada em Retention Segments de ~`chunk_seconds`
    apenas para permitir pan/reframe leve camadado — NUNCA reseta a escala
    entre fatias (`segment[i+1].start_scale == segment[i].end_scale`,
    verificado por `segments_share_continuous_trajectory`).

    `ease_in_out=True` (Gate 3D.2, feedback humano "nível mais profissional
    de animação") aplica uma curva suave (`_smoothstep`) na trajetória
    GLOBAL do beat inteiro antes de fatiar em chunks — NÃO em cada chunk
    individualmente. Aplicar a curva por chunk reintroduziria uma velocidade
    zero a cada ~`chunk_seconds`, produzindo um movimento "pulsante"
    (desacelera/acelera a cada poucos segundos) em vez de um único
    movimento cinemático contínuo do início ao fim do beat — o oposto do
    efeito pedido. Cada chunk renderizado internamente permanece com
    progressão linear (`render_retention_clip`), mas seus limites de escala
    já refletem os pontos correspondentes na curva suave global, então a
    sequência concatenada dos chunks aproxima a curva suave inteira.

    Um leve pan lateral é camadado nos chunks intermediários (não no
    primeiro/último) para evitar um push-in perfeitamente centralizado o
    tempo todo — sem interromper a progressão do zoom."""
    end_scale = compute_continuous_zoom_end_scale(duration_seconds, total_zoom_ratio=total_zoom_ratio)
    chunk_count = max(1, round(duration_seconds / chunk_seconds))
    chunk_duration = duration_seconds / chunk_count

    segments: list[RetentionSegment] = []
    for i in range(chunk_count):
        t0 = i / chunk_count
        t1 = (i + 1) / chunk_count
        if ease_in_out:
            t0, t1 = _smoothstep(t0), _smoothstep(t1)
        seg_start_scale = 1.0 + (end_scale - 1.0) * t0
        seg_end_scale = 1.0 + (end_scale - 1.0) * t1
        is_middle_chunk = 0 < i < chunk_count - 1
        pan_dx = pan_dx_fraction_on_middle_chunks * (1 if i % 2 == 0 else -1) if is_middle_chunk else 0.0
        segments.append(
            RetentionSegment(
                kind=RetentionKind.ZOOM_IN,
                duration_seconds=chunk_duration,
                start_scale=seg_start_scale,
                end_scale=seg_end_scale,
                pan_dx_fraction=pan_dx,
            )
        )
    return tuple(segments)


def segments_share_continuous_trajectory(segments: tuple[RetentionSegment, ...], *, tolerance: float = 1e-6) -> bool:
    """Gate 3D.2 §10/§26 — detecta se a escala RESETA entre Retention
    Segments consecutivos (o achado de investigação deste gate) em vez de
    continuar de onde o segmento anterior parou. Um único segmento é sempre
    considerado contínuo (nada para resetar)."""
    if len(segments) <= 1:
        return True
    for previous, current in zip(segments, segments[1:]):
        if abs(current.start_scale - previous.end_scale) > tolerance:
            return False
    return True
