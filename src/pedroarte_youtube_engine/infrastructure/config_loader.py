"""Carregamento e mesclagem de configuração.

Precedência, do mais fraco ao mais forte:

    padrões do domínio → config/default.yaml → config/<ambiente>.yaml
    → input/project.yaml → sobrescritas da CLI

Credenciais **nunca** vêm daqui: só de variáveis de ambiente. Um `project.yaml`
que traga uma chave de API é rejeitado com erro explícito.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from pedroarte_youtube_engine.domain.configuration import ProjectConfiguration
from pedroarte_youtube_engine.observability.redaction import is_sensitive_key
from pedroarte_youtube_engine.shared.errors import ConfigurationError

#: Nome do arquivo de configuração aceito dentro de `input/`.
PROJECT_CONFIG_NAMES: tuple[str, ...] = ("project.yaml", "project.yml")


@dataclass(frozen=True, slots=True)
class LoadedConfiguration:
    """Configuração final e o rastro de onde cada camada veio."""

    configuration: ProjectConfiguration
    sources: tuple[str, ...]
    raw: dict[str, Any]


class ConfigurationLoader:
    """Constrói a `ProjectConfiguration` a partir das camadas disponíveis."""

    def __init__(self, *, config_directory: Path | None = None) -> None:
        self._config_directory = config_directory

    def load(
        self,
        *,
        environment: str = "development",
        project_config_path: Path | None = None,
        overrides: dict[str, Any] | None = None,
        explicit_config_path: Path | None = None,
    ) -> LoadedConfiguration:
        merged: dict[str, Any] = {}
        sources: list[str] = ["padrões do domínio"]

        if self._config_directory is not None:
            for name in ("default.yaml", f"{environment}.yaml"):
                candidate = self._config_directory / name
                if candidate.exists():
                    merged = _deep_merge(merged, self._read_yaml(candidate))
                    sources.append(str(candidate))

        if explicit_config_path is not None:
            if not explicit_config_path.exists():
                raise ConfigurationError(
                    "Arquivo de configuração informado não existe.",
                    path=str(explicit_config_path),
                )
            merged = _deep_merge(merged, self._read_yaml(explicit_config_path))
            sources.append(str(explicit_config_path))

        if project_config_path is not None and project_config_path.exists():
            merged = _deep_merge(merged, self._read_yaml(project_config_path))
            sources.append(str(project_config_path))

        if overrides:
            merged = _deep_merge(merged, overrides)
            sources.append("argumentos da linha de comando")

        _reject_secrets(merged)

        try:
            configuration = ProjectConfiguration.model_validate(merged)
        except Exception as exc:  # pydantic ValidationError e derivados
            raise ConfigurationError(
                f"Configuração inválida: {exc}", sources=sources
            ) from exc

        return LoadedConfiguration(
            configuration=configuration, sources=tuple(sources), raw=merged
        )

    @staticmethod
    def find_project_config(input_directory: Path) -> Path | None:
        """Procura `project.yaml` na pasta de entrada."""
        for name in PROJECT_CONFIG_NAMES:
            candidate = input_directory / name
            if candidate.exists():
                return candidate
        return None

    @staticmethod
    def _read_yaml(path: Path) -> dict[str, Any]:
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise ConfigurationError(f"YAML inválido: {exc}", path=str(path)) from exc
        except OSError as exc:
            raise ConfigurationError(
                f"Não foi possível ler a configuração: {exc}", path=str(path)
            ) from exc
        if payload is None:
            return {}
        if not isinstance(payload, dict):
            raise ConfigurationError(
                "A configuração deve ser um mapeamento no nível raiz.", path=str(path)
            )
        return payload


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Mescla recursivamente; listas são substituídas, não concatenadas.

    Concatenar listas impediria o operador de *remover* um item herdado de uma
    camada anterior — por exemplo, encurtar a lista de trailers.
    """
    result = copy.deepcopy(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _reject_secrets(payload: dict[str, Any], *, path: str = "") -> None:
    """Impede que credenciais entrem por arquivo de configuração."""
    for key, value in payload.items():
        current = f"{path}.{key}" if path else key
        if isinstance(value, dict):
            _reject_secrets(value, path=current)
        elif is_sensitive_key(key) and value not in (None, "", False):
            raise ConfigurationError(
                f"O campo '{current}' parece conter um segredo. "
                "Credenciais são lidas apenas de variáveis de ambiente — veja SECURITY.md.",
                field=current,
            )
