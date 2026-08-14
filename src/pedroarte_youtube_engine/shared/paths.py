"""Política de acesso a sistema de arquivos.

Toda leitura e escrita do motor passa por aqui. O objetivo é impedir path
traversal, escrita fora das raízes autorizadas, leitura de extensões
inesperadas e exaustão de memória por arquivos gigantes.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

from pedroarte_youtube_engine.shared.errors import PathSecurityError

DEFAULT_INPUT_EXTENSIONS: frozenset[str] = frozenset(
    {".md", ".txt", ".docx", ".pdf", ".epub", ".json", ".yaml", ".yml"}
)

DEFAULT_MAX_FILE_BYTES = 32 * 1024 * 1024
DEFAULT_MAX_TOTAL_BYTES = 256 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class PathPolicy:
    """Allowlist de raízes, extensões e limites de tamanho."""

    allowed_roots: tuple[Path, ...]
    allowed_extensions: frozenset[str] = DEFAULT_INPUT_EXTENSIONS
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES
    max_total_bytes: int = DEFAULT_MAX_TOTAL_BYTES
    follow_symlinks: bool = False

    @classmethod
    def for_roots(cls, *roots: Path | str, **kwargs: object) -> "PathPolicy":
        resolved = tuple(Path(root).resolve() for root in roots)
        if not resolved:
            raise PathSecurityError("A política exige ao menos uma raiz permitida.")
        return cls(allowed_roots=resolved, **kwargs)  # type: ignore[arg-type]

    def resolve_within(self, candidate: Path | str) -> Path:
        """Resolve `candidate` e garante que ele está sob uma raiz permitida.

        Levanta `PathSecurityError` quando o caminho escapa — inclusive quando o
        escape acontece através de `..` ou de um link simbólico.
        """
        path = Path(candidate)
        resolved = path.resolve() if self.follow_symlinks else _resolve_no_symlink_escape(path)
        for root in self.allowed_roots:
            if resolved == root or root in resolved.parents:
                return resolved
        raise PathSecurityError(
            "Caminho fora das raízes autorizadas.",
            candidate=str(candidate),
            resolved=str(resolved),
            allowed_roots=[str(root) for root in self.allowed_roots],
        )

    def is_allowed_extension(self, path: Path) -> bool:
        return path.suffix.lower() in self.allowed_extensions

    def check_file_size(self, path: Path) -> int:
        """Valida o tamanho de um arquivo e devolve os bytes."""
        size = path.stat().st_size
        if size > self.max_file_bytes:
            raise PathSecurityError(
                "Arquivo excede o tamanho máximo permitido.",
                path=str(path),
                size_bytes=size,
                max_file_bytes=self.max_file_bytes,
            )
        return size


def _resolve_no_symlink_escape(path: Path) -> Path:
    """Resolve o caminho e rejeita links simbólicos no trajeto.

    `Path.resolve()` sozinho seguiria o link — o que permitiria a um link dentro
    de `input/` apontar para fora da raiz autorizada.
    """
    resolved = path.resolve()
    probe = path if path.is_absolute() else Path.cwd() / path
    current = Path(probe.anchor)
    for part in probe.parts[1:]:
        current = current / part
        if current.is_symlink():
            raise PathSecurityError(
                "Links simbólicos não são seguidos na política padrão.",
                path=str(path),
                symlink=str(current),
            )
        if not current.exists():
            break
    return resolved


@dataclass(slots=True)
class DiscoveryBudget:
    """Acumula bytes lidos para não estourar o limite total da execução."""

    max_total_bytes: int = DEFAULT_MAX_TOTAL_BYTES
    consumed_bytes: int = field(default=0)

    def consume(self, size: int, *, path: Path) -> None:
        self.consumed_bytes += size
        if self.consumed_bytes > self.max_total_bytes:
            raise PathSecurityError(
                "A execução excedeu o volume total de entrada permitido.",
                path=str(path),
                consumed_bytes=self.consumed_bytes,
                max_total_bytes=self.max_total_bytes,
            )


def iter_input_files(
    root: Path,
    policy: PathPolicy,
    *,
    ignore_names: Iterable[str] = (),
) -> Iterator[Path]:
    """Percorre a pasta de entrada devolvendo apenas arquivos autorizados.

    A ordem é determinística (alfabética, com diretórios visitados em ordem),
    condição necessária para que duas execuções sobre a mesma entrada produzam
    o mesmo resultado.
    """
    ignored = {name.lower() for name in ignore_names}
    root = policy.resolve_within(root)
    if not root.exists():
        raise PathSecurityError("Pasta de entrada inexistente.", path=str(root))
    for path in sorted(root.rglob("*"), key=lambda item: str(item).lower()):
        if not path.is_file():
            continue
        if path.name.lower() in ignored or path.name.startswith("."):
            continue
        if not policy.is_allowed_extension(path):
            continue
        yield policy.resolve_within(path)


def ensure_directory(path: Path, policy: PathPolicy) -> Path:
    """Cria um diretório dentro das raízes autorizadas."""
    resolved = policy.resolve_within(path)
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def write_text_atomic(path: Path, content: str, policy: PathPolicy) -> Path:
    """Escreve um arquivo de texto de forma atômica dentro da allowlist.

    A escrita vai primeiro para um arquivo temporário no mesmo diretório e só
    então é renomeada, evitando artefatos truncados quando a execução é
    interrompida.
    """
    resolved = policy.resolve_within(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    temporary = resolved.with_name(resolved.name + ".tmp")
    temporary.write_text(content, encoding="utf-8", newline="\n")
    temporary.replace(resolved)
    return resolved
