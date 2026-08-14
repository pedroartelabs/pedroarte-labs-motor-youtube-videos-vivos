"""Registro de capacidades de provedor, lido de YAML.

As capacidades são voláteis — mudam a cada release de um modelo. Mantê-las em
configuração é o que impede o domínio de envelhecer junto com uma API
(regra da seção 9.23).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from pedroarte_youtube_engine.domain.provider import (
    ModelName,
    ProviderCapability,
    ProviderModality,
    ProviderName,
)
from pedroarte_youtube_engine.shared.errors import CapabilityError, ConfigurationError

#: Capacidade neutra usada quando nenhum provedor concreto foi configurado.
#: Ela representa um alvo genérico de prompt, não um produto real.
GENERIC_VIDEO_CAPABILITY = ProviderCapability(
    provider=ProviderName.generic(),
    model=ModelName(value="generic-video-target"),
    modality=ProviderModality.VIDEO,
    min_duration_seconds=1.0,
    max_duration_seconds=10.0,
    duration_granularity_seconds=1.0,
    supported_aspect_ratios=("16:9", "9:16", "1:1"),
    supported_resolutions=("720p", "1080p", "1440p", "2160p"),
    native_audio=True,
    dialogue_support=True,
    first_frame_reference=True,
    last_frame_reference=True,
    image_reference=True,
    video_extension=False,
    max_prompt_characters=20000,
    max_negative_prompt_characters=2000,
    notes=(
        "Alvo genérico: aceita a duração narrativa padrão de 10s sem recompilação.",
        "Não representa nenhum produto comercial específico.",
    ),
)

GENERIC_IMAGE_CAPABILITY = ProviderCapability(
    provider=ProviderName.generic(),
    model=ModelName(value="generic-image-target"),
    modality=ProviderModality.IMAGE,
    min_duration_seconds=0.001,
    max_duration_seconds=0.001,
    duration_granularity_seconds=0.001,
    supported_aspect_ratios=("16:9", "9:16", "1:1"),
    supported_resolutions=("720p", "1080p", "1440p", "2160p"),
    native_audio=False,
    dialogue_support=False,
    first_frame_reference=False,
    last_frame_reference=False,
    image_reference=True,
    video_extension=False,
    max_prompt_characters=8000,
)

GENERIC_VOICE_CAPABILITY = ProviderCapability(
    provider=ProviderName.generic(),
    model=ModelName(value="generic-voice-target"),
    modality=ProviderModality.VOICE,
    min_duration_seconds=0.5,
    max_duration_seconds=600.0,
    supported_aspect_ratios=("16:9", "9:16", "1:1"),
    supported_resolutions=("720p", "1080p"),
    native_audio=True,
    dialogue_support=True,
    max_prompt_characters=6000,
)

GENERIC_MUSIC_CAPABILITY = ProviderCapability(
    provider=ProviderName.generic(),
    model=ModelName(value="generic-music-target"),
    modality=ProviderModality.MUSIC,
    min_duration_seconds=5.0,
    max_duration_seconds=600.0,
    supported_aspect_ratios=("16:9", "9:16", "1:1"),
    supported_resolutions=("720p", "1080p"),
    native_audio=True,
    max_prompt_characters=4000,
)

_BUILTIN: tuple[ProviderCapability, ...] = (
    GENERIC_VIDEO_CAPABILITY,
    GENERIC_IMAGE_CAPABILITY,
    GENERIC_VOICE_CAPABILITY,
    GENERIC_MUSIC_CAPABILITY,
)


class YamlCapabilityRegistry:
    """Implementação do `CapabilityRegistryPort` com fallback embutido."""

    def __init__(self, capabilities: tuple[ProviderCapability, ...] = ()) -> None:
        self._capabilities: list[ProviderCapability] = [*_BUILTIN, *capabilities]

    @classmethod
    def from_directory(cls, directory: Path) -> "YamlCapabilityRegistry":
        """Carrega todos os `*.yaml` de um diretório de capacidades."""
        loaded: list[ProviderCapability] = []
        if directory.exists():
            for path in sorted(directory.glob("*.yaml")):
                loaded.extend(cls._read_file(path))
        return cls(tuple(loaded))

    @staticmethod
    def _read_file(path: Path) -> list[ProviderCapability]:
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise ConfigurationError(
                f"Capacidades em YAML inválido: {exc}", path=str(path)
            ) from exc
        if not payload:
            return []

        entries: list[dict[str, Any]]
        if isinstance(payload, dict) and "provider_capabilities" in payload:
            raw = payload["provider_capabilities"]
            entries = raw if isinstance(raw, list) else [raw]
        elif isinstance(payload, list):
            entries = payload
        elif isinstance(payload, dict):
            entries = [payload]
        else:
            raise ConfigurationError(
                "Formato de capacidades não reconhecido.", path=str(path)
            )

        result: list[ProviderCapability] = []
        for entry in entries:
            result.append(_parse_capability(entry, path))
        return result

    # -- consulta ----------------------------------------------------------

    def get(
        self, *, provider: str, modality: ProviderModality, model: str | None = None
    ) -> ProviderCapability | None:
        for capability in reversed(self._capabilities):
            if capability.provider.value != provider:
                continue
            if capability.modality is not modality:
                continue
            if model and capability.model.value != model:
                continue
            return capability
        return None

    def require(
        self, *, provider: str, modality: ProviderModality, model: str | None = None
    ) -> ProviderCapability:
        capability = self.get(provider=provider, modality=modality, model=model)
        if capability is None:
            raise CapabilityError(
                f"Nenhuma capacidade registrada para {provider}/{modality.value}"
                + (f"/{model}" if model else "")
                + ". Declare-a em config/provider_capabilities/.",
                provider=provider,
                modality=modality.value,
                model=model,
                available=[
                    f"{item.provider}/{item.modality.value}/{item.model}"
                    for item in self._capabilities
                ],
            )
        return capability

    def list_all(self) -> tuple[ProviderCapability, ...]:
        return tuple(self._capabilities)


def _parse_capability(entry: dict[str, Any], path: Path) -> ProviderCapability:
    """Converte uma entrada YAML no value object de capacidade."""
    try:
        return ProviderCapability(
            provider=ProviderName(value=str(entry["provider"])),
            model=ModelName(value=str(entry["model"])),
            modality=ProviderModality(str(entry.get("modality", "video"))),
            min_duration_seconds=float(entry.get("min_duration_seconds", 1.0)),
            max_duration_seconds=float(entry.get("max_duration_seconds", 10.0)),
            duration_granularity_seconds=float(
                entry.get("duration_granularity_seconds", 1.0)
            ),
            supported_aspect_ratios=tuple(
                str(item) for item in entry.get("supported_aspect_ratios", ("16:9",))
            ),
            supported_resolutions=tuple(
                str(item) for item in entry.get("supported_resolutions", ("1080p",))
            ),
            native_audio=bool(entry.get("native_audio", False)),
            dialogue_support=bool(entry.get("dialogue_support", False)),
            first_frame_reference=bool(entry.get("first_frame_reference", False)),
            last_frame_reference=bool(entry.get("last_frame_reference", False)),
            image_reference=bool(entry.get("image_reference", False)),
            video_extension=bool(entry.get("video_extension", False)),
            max_prompt_characters=int(entry.get("max_prompt_characters", 8000)),
            max_negative_prompt_characters=int(
                entry.get("max_negative_prompt_characters", 1500)
            ),
            notes=tuple(str(item) for item in entry.get("notes", ())),
        )
    except KeyError as exc:
        raise ConfigurationError(
            f"Capacidade sem o campo obrigatório {exc}.", path=str(path)
        ) from exc
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(
            f"Capacidade inválida: {exc}", path=str(path)
        ) from exc
