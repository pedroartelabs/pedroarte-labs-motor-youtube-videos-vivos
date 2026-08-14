"""Continuidade entre segmentos (seção 16).

O `Continuity Ledger` compara o estado que um segmento *entrega* com o estado
que o próximo *herda*. Nada aqui depende da memória do modelo: se o segmento 12
terminou com a personagem segurando um envelope, o segmento 13 começa com o
envelope na mão, ou o gate reprova.
"""

from __future__ import annotations

from pedroarte_youtube_engine.domain.aggregates import AudiovisualBible, CanonBible
from pedroarte_youtube_engine.domain.segment import ContinuitySnapshot, PromptSegment
from pedroarte_youtube_engine.domain.services._issues import make_issue
from pedroarte_youtube_engine.domain.validation import (
    IssueCategory,
    ValidationIssue,
    ValidationReport,
)
from pedroarte_youtube_engine.domain.value_objects import Severity

VISUAL_AGENT = "VISUAL_CONTINUITY_AGENT"
VOICE_AGENT = "VOICE_CASTING_AGENT"
CHARACTER_AGENT = "CHARACTER_BIBLE_AGENT"

#: Transições que autorizam uma mudança brusca de local, luz ou hora.
_HARD_TRANSITIONS = frozenset(
    {
        "fade_para_preto",
        "fade_out",
        "fade_in",
        "dissolucao",
        "corte_de_correspondencia",
        "chicote",
        "ponte_sonora",
    }
)


class VisualContinuityService:
    """Compara estados visuais entre segmentos consecutivos."""

    def validate_chain(self, segments: tuple[PromptSegment, ...]) -> ValidationReport:
        issues: list[ValidationIssue] = []
        for previous, current in zip(segments, segments[1:], strict=False):
            issues.extend(self._compare(previous, current))
        checked = max(0, len(segments) - 1)
        failing = {issue.segment_id for issue in issues if issue.segment_id}
        return ValidationReport(
            gate="visual_continuity",
            issues=tuple(issues),
            checked_count=checked,
            passed_count=max(0, checked - len(failing)),
        )

    def _compare(
        self, previous: PromptSegment, current: PromptSegment
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        out_state = previous.continuity_out
        in_state = current.continuity_in
        transition = current.video.transition_in.value
        soft = transition not in _HARD_TRANSITIONS

        # Local
        if out_state.location_id != in_state.location_id and soft:
            issues.append(
                self._issue(
                    current,
                    IssueCategory.UNTRANSITIONED_LOCATION_CHANGE,
                    Severity.ERROR,
                    (
                        "Mudança de ambiente sem transição declarada "
                        f"({out_state.location_id} → {in_state.location_id})."
                    ),
                    field_path="continuity_in.location_id",
                    suggested_fix=(
                        "Use fade, dissolução, corte de correspondência ou ponte sonora, "
                        "ou insira um segmento de deslocamento."
                    ),
                )
            )

        # Hora do dia e clima
        if out_state.time_of_day != in_state.time_of_day and soft:
            issues.append(
                self._issue(
                    current,
                    IssueCategory.INCOMPATIBLE_LIGHT,
                    Severity.ERROR,
                    (
                        f"Horário muda de '{out_state.time_of_day}' para "
                        f"'{in_state.time_of_day}' sem transição."
                    ),
                    field_path="continuity_in.time_of_day",
                    suggested_fix="Declare uma elipse temporal ou preserve o horário.",
                )
            )
        if out_state.weather != in_state.weather and soft:
            issues.append(
                self._issue(
                    current,
                    IssueCategory.CONTINUITY_BREAK,
                    Severity.WARNING,
                    f"Clima muda de '{out_state.weather}' para '{in_state.weather}' sem transição.",
                    field_path="continuity_in.weather",
                )
            )

        # Figurino, ferimentos e mãos ocupadas
        issues.extend(
            self._compare_mapping(
                current,
                out_state.wardrobe,
                in_state.wardrobe,
                category=IssueCategory.UNEXPLAINED_PHYSICAL_CHANGE,
                label="figurino",
                field_path="continuity_in.wardrobe",
            )
        )
        issues.extend(
            self._compare_mapping(
                current,
                out_state.injuries,
                in_state.injuries,
                category=IssueCategory.UNEXPLAINED_PHYSICAL_CHANGE,
                label="ferimentos",
                field_path="continuity_in.injuries",
            )
        )
        issues.extend(
            self._compare_mapping(
                current,
                out_state.hands_occupied,
                in_state.hands_occupied,
                category=IssueCategory.VANISHING_PROP,
                label="mãos ocupadas",
                field_path="continuity_in.hands_occupied",
                severity=Severity.WARNING,
            )
        )

        # Objetos que somem sem justificativa
        vanished = set(out_state.props_on_scene) - set(in_state.props_on_scene)
        if vanished and soft:
            issues.append(
                self._issue(
                    current,
                    IssueCategory.VANISHING_PROP,
                    Severity.WARNING,
                    f"Objetos deixam a cena sem explicação: {sorted(vanished)}.",
                    field_path="continuity_in.props_on_scene",
                    suggested_fix="Mostre a retirada do objeto ou mantenha-o em quadro.",
                )
            )

        # Encadeamento de identificadores
        if current.continuity_reference.previous_segment_id != previous.segment_id:
            issues.append(
                self._issue(
                    current,
                    IssueCategory.CONTINUITY_BREAK,
                    Severity.ERROR,
                    "O segmento não referencia corretamente o segmento anterior.",
                    field_path="continuity_reference.previous_segment_id",
                    observed=str(current.continuity_reference.previous_segment_id),
                    expected=str(previous.segment_id),
                )
            )

        return issues

    def _compare_mapping(
        self,
        current: PromptSegment,
        out_state: dict[str, str],
        in_state: dict[str, str],
        *,
        category: IssueCategory,
        label: str,
        field_path: str,
        severity: Severity = Severity.ERROR,
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        for subject, previous_value in out_state.items():
            incoming = in_state.get(subject)
            if incoming is not None and incoming != previous_value:
                issues.append(
                    self._issue(
                        current,
                        category,
                        severity,
                        (
                            f"Mudança de {label} em {subject} sem justificativa: "
                            f"'{previous_value}' → '{incoming}'."
                        ),
                        field_path=field_path,
                        observed=incoming,
                        expected=previous_value,
                        suggested_fix=(
                            "Mostre a mudança em cena, ou mantenha o estado herdado."
                        ),
                    )
                )
        return issues

    def _issue(
        self,
        segment: PromptSegment,
        category: IssueCategory,
        severity: Severity,
        message: str,
        *,
        field_path: str,
        suggested_fix: str = "",
        observed: str = "",
        expected: str = "",
    ) -> ValidationIssue:
        return make_issue(
            category=category,
            severity=severity,
            message=message,
            responsible_agent=VISUAL_AGENT,
            variant=segment.production_variant,
            episode_id=segment.episode_id,
            segment_id=segment.segment_id,
            field_path=field_path,
            suggested_fix=suggested_fix,
            observed=observed,
            expected=expected,
        )


class CharacterContinuityService:
    """Garante que todo personagem em cena existe no cânone e mantém sua âncora."""

    def validate(
        self, segments: tuple[PromptSegment, ...], canon: CanonBible
    ) -> ValidationReport:
        issues: list[ValidationIssue] = []
        anchors: dict[str, str] = {}
        for segment in segments:
            for presence in segment.video.characters:
                key = presence.character_id.value
                if canon.character(presence.character_id) is None:
                    issues.append(
                        make_issue(
                            category=IssueCategory.CANON_CONTRADICTION,
                            severity=Severity.ERROR,
                            message=(
                                f"Personagem '{presence.display_name}' não existe no cânone."
                            ),
                            responsible_agent=CHARACTER_AGENT,
                            variant=segment.production_variant,
                            episode_id=segment.episode_id,
                            segment_id=segment.segment_id,
                            field_path="video.characters[].character_id",
                            suggested_fix="Use apenas personagens extraídos da obra.",
                        )
                    )
                    continue
                known = anchors.get(key)
                if known is None:
                    anchors[key] = presence.appearance_anchor
                elif known != presence.appearance_anchor:
                    issues.append(
                        make_issue(
                            category=IssueCategory.UNEXPLAINED_PHYSICAL_CHANGE,
                            severity=Severity.ERROR,
                            message=(
                                f"A âncora visual de '{presence.display_name}' mudou entre "
                                "segmentos."
                            ),
                            responsible_agent=CHARACTER_AGENT,
                            variant=segment.production_variant,
                            episode_id=segment.episode_id,
                            segment_id=segment.segment_id,
                            field_path="video.characters[].appearance_anchor",
                            observed=presence.appearance_anchor[:120],
                            expected=known[:120],
                            suggested_fix=(
                                "Reinjete sempre a mesma ficha da Bíblia de Personagens."
                            ),
                        )
                    )
        checked = sum(len(segment.video.characters) for segment in segments)
        return ValidationReport(
            gate="character_continuity",
            issues=tuple(issues),
            checked_count=checked,
            passed_count=max(0, checked - len(issues)),
        )


class VoiceContinuityService:
    """Garante que cada personagem mantém a mesma voz em todos os segmentos."""

    def validate(
        self, segments: tuple[PromptSegment, ...], bible: AudiovisualBible
    ) -> ValidationReport:
        issues: list[ValidationIssue] = []
        known_voices = {voice.voice_id for voice in bible.voices}
        assignments: dict[str, str] = {}
        checked = 0

        for segment in segments:
            for entry in segment.audio.voice_plan:
                checked += 1
                if entry.voice_id not in known_voices:
                    issues.append(
                        make_issue(
                            category=IssueCategory.MISSING_VOICE,
                            severity=Severity.ERROR,
                            message=(
                                f"voice_id '{entry.voice_id}' não existe na Bíblia de Vozes."
                            ),
                            responsible_agent=VOICE_AGENT,
                            variant=segment.production_variant,
                            episode_id=segment.episode_id,
                            segment_id=segment.segment_id,
                            field_path="audio.voice_plan[].voice_id",
                            suggested_fix="Use apenas vozes registradas na voice_bible.",
                        )
                    )
                if entry.character_id is not None:
                    key = entry.character_id.value
                    previous = assignments.get(key)
                    if previous is None:
                        assignments[key] = entry.voice_id
                    elif previous != entry.voice_id:
                        issues.append(
                            make_issue(
                                category=IssueCategory.CONTINUITY_BREAK,
                                severity=Severity.ERROR,
                                message=(
                                    f"O personagem {key} trocou de voz: "
                                    f"'{previous}' → '{entry.voice_id}'."
                                ),
                                responsible_agent=VOICE_AGENT,
                                variant=segment.production_variant,
                                episode_id=segment.episode_id,
                                segment_id=segment.segment_id,
                                field_path="audio.voice_plan[].voice_id",
                                observed=entry.voice_id,
                                expected=previous,
                                suggested_fix="Mantenha uma identidade vocal por personagem.",
                            )
                        )
        return ValidationReport(
            gate="voice_continuity",
            issues=tuple(issues),
            checked_count=checked,
            passed_count=max(0, checked - len(issues)),
        )


def carry_forward(previous_out: ContinuitySnapshot) -> ContinuitySnapshot:
    """Estado inicial do próximo segmento: o estado final do anterior, tal e qual."""
    return previous_out.model_copy(deep=True)
