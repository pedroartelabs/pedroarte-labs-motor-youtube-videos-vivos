"""Utilidades de texto, com atenção ao português brasileiro.

Nada aqui depende de bibliotecas externas de NLP: o motor precisa rodar offline,
sem download de modelos, e de forma determinística nos testes golden.
"""

from __future__ import annotations

import re
import unicodedata

# Nomes reservados no Windows: um arquivo chamado `CON.md` é inacessível.
_WINDOWS_RESERVED = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)}
)

_SLUG_STRIP = re.compile(r"[^a-z0-9]+")
_WHITESPACE = re.compile(r"[ \t ]+")
_BLANK_LINES = re.compile(r"\n{3,}")
_WORD = re.compile(r"[\w'’-]+", re.UNICODE)

# Velocidade média de narração em português brasileiro, em palavras por minuto.
# 150 wpm é o ponto de conforto para narração documental; diálogo dramático fica
# entre 130 e 170. O motor usa este valor para checar se um texto cabe na
# duração do segmento.
DEFAULT_SPEECH_RATE_WPM = 150.0


def strip_accents(value: str) -> str:
    """Remove diacríticos preservando as letras base."""
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def slugify(value: str, *, max_length: int = 80) -> str:
    """Converte um título em um slug ASCII estável.

    >>> slugify("A Morte Ainda Não Nasceu")
    'a-morte-ainda-nao-nasceu'
    """
    ascii_value = strip_accents(value).lower()
    slug = _SLUG_STRIP.sub("-", ascii_value).strip("-")
    if len(slug) > max_length:
        slug = slug[:max_length].rstrip("-")
    return slug or "sem-titulo"


def safe_slug(value: str, *, max_length: int = 80, fallback: str = "arquivo") -> str:
    """Slug seguro para uso como nome de arquivo ou diretório.

    Além do `slugify`, protege contra nomes reservados do Windows e contra
    nomes que resolveriam para navegação de diretório.
    """
    slug = slugify(value, max_length=max_length)
    if slug.upper() in _WINDOWS_RESERVED:
        slug = f"{slug}-item"
    if slug in {".", "..", ""}:
        slug = fallback
    return slug


def normalize_whitespace(text: str) -> str:
    """Normaliza quebras de linha e espaços preservando a estrutura de parágrafos."""
    unified = text.replace("\r\n", "\n").replace("\r", "\n")
    unified = unified.replace(" ", " ")
    unified = _WHITESPACE.sub(" ", unified)
    unified = "\n".join(line.strip() for line in unified.split("\n"))
    return _BLANK_LINES.sub("\n\n", unified).strip()


def count_words(text: str) -> int:
    """Conta palavras de forma estável, incluindo hifenizadas e com apóstrofo."""
    return len(_WORD.findall(text))


def speakable_duration_seconds(text: str, *, words_per_minute: float = DEFAULT_SPEECH_RATE_WPM) -> float:
    """Estima quantos segundos o texto leva para ser falado.

    É a base da regra "fala longa demais" do `AUDIOVISUAL_QUALITY_GUARDIAN_AGENT`.
    """
    if words_per_minute <= 0:
        raise ValueError("A velocidade de fala deve ser positiva.")
    return count_words(text) / words_per_minute * 60.0


def max_words_for_duration(
    seconds: float, *, words_per_minute: float = DEFAULT_SPEECH_RATE_WPM
) -> int:
    """Quantidade máxima de palavras que cabem confortavelmente na duração."""
    if seconds <= 0:
        return 0
    return int(seconds / 60.0 * words_per_minute)


def truncate_words(text: str, max_words: int) -> str:
    """Trunca no limite de palavras, sem cortar palavras pela metade."""
    if max_words <= 0:
        return ""
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]).rstrip(",;:—- ") + "…"


def sentence_split(text: str) -> list[str]:
    """Divide em sentenças com heurística adequada ao português.

    Trata abreviações comuns (`Sr.`, `Dra.`, `etc.`) e reticências, que quebram
    divisores ingênuos por ponto final.
    """
    protected = text
    for abbreviation in ("Sr.", "Sra.", "Srta.", "Dr.", "Dra.", "Prof.", "etc.", "p.ex."):
        protected = protected.replace(abbreviation, abbreviation.replace(".", "\x00"))
    protected = protected.replace("...", "\x01").replace("…", "\x01")
    pieces = re.split(r"(?<=[.!?])\s+", protected)
    restored = [
        piece.replace("\x00", ".").replace("\x01", "…").strip()
        for piece in pieces
        if piece.strip()
    ]
    return restored


def first_sentence(text: str, *, fallback: str = "") -> str:
    """Primeira sentença do texto, útil para resumos curtos."""
    sentences = sentence_split(text)
    return sentences[0] if sentences else fallback


def excerpt(text: str, *, max_chars: int = 220) -> str:
    """Trecho curto e limpo, usado nas referências de proveniência."""
    flat = normalize_whitespace(text).replace("\n", " ")
    if len(flat) <= max_chars:
        return flat
    return flat[: max_chars - 1].rsplit(" ", 1)[0] + "…"
