"""Hierarquia de erros do motor.

Todos os erros carregam um `code` estável, adequado para logs estruturados, para
respostas da API e para erros do MCP. Mensagens são em português; códigos são em
inglês, porque integram contratos de máquina.
"""

from __future__ import annotations

from typing import Any


class EngineError(Exception):
    """Raiz de toda falha originada no motor."""

    code: str = "engine_error"

    def __init__(self, message: str, **details: Any) -> None:
        super().__init__(message)
        self.message = message
        self.details: dict[str, Any] = details

    def to_dict(self) -> dict[str, Any]:
        """Serializa o erro em uma estrutura pronta para transporte."""
        return {"code": self.code, "message": self.message, "details": self.details}

    def __repr__(self) -> str:  # pragma: no cover - conveniência de depuração
        return f"{type(self).__name__}(code={self.code!r}, message={self.message!r})"


class ConfigurationError(EngineError):
    """Configuração ausente, inválida ou contraditória."""

    code = "configuration_error"


class InputDiscoveryError(EngineError):
    """A pasta de entrada não pôde ser interpretada."""

    code = "input_discovery_error"


class IngestionError(EngineError):
    """Um documento não pôde ser lido ou normalizado."""

    code = "ingestion_error"


class DomainRuleViolation(EngineError):
    """Uma invariante de domínio foi violada."""

    code = "domain_rule_violation"


class StateTransitionError(EngineError):
    """Transição de estado não permitida pela máquina de estados."""

    code = "state_transition_error"


class RepairLimitExceeded(EngineError):
    """O repair loop atingiu o número máximo de iterações."""

    code = "repair_limit_exceeded"


class CapabilityError(EngineError):
    """O pacote exigido é incompatível com as capacidades do provedor."""

    code = "capability_error"


class ProviderError(EngineError):
    """Falha ao conversar com um provedor externo."""

    code = "provider_error"


class ProviderUnavailable(ProviderError):
    """O provedor está temporariamente indisponível (circuito aberto, timeout)."""

    code = "provider_unavailable"


class PathSecurityError(EngineError):
    """Um caminho violou a política de segurança de sistema de arquivos."""

    code = "path_security_error"


class QualityGateFailed(EngineError):
    """Um portão de qualidade rejeitou o artefato."""

    code = "quality_gate_failed"
