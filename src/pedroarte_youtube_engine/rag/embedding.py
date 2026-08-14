"""Embeddings locais e determinísticos.

Um modelo de embedding real exigiria download, GPU opcional e — pior para este
projeto — tornaria os testes golden não reproduzíveis entre máquinas.

A implementação aqui usa *hashing trick* sobre unigramas e bigramas, com peso
sublinear de frequência e normalização L2. Não compete com um modelo neural em
semântica profunda, mas captura sobreposição lexical e de vizinhança com
qualidade suficiente para o papel que o vetor tem no motor: complementar o BM25
na recuperação híbrida. Um adaptador neural pode substituí-lo pela mesma porta.
"""

from __future__ import annotations

import hashlib
import math

from pedroarte_youtube_engine.rag.lexical import tokenize


class HashingEmbeddingProvider:
    """Vetorização por hashing, sem modelo e sem rede."""

    def __init__(self, *, dimensions: int = 256) -> None:
        if not 32 <= dimensions <= 4096:
            raise ValueError("As dimensões devem estar entre 32 e 4096.")
        self._dimensions = dimensions

    @property
    def name(self) -> str:
        return f"hashing_local_v1_d{self._dimensions}"

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed(self, text: str) -> tuple[float, ...]:
        tokens = tokenize(text)
        if not tokens:
            return tuple(0.0 for _ in range(self._dimensions))

        vector = [0.0] * self._dimensions
        features = self._features(tokens)

        for feature, count in features.items():
            index, sign = self._bucket(feature)
            # Peso sublinear: a décima ocorrência importa menos que a segunda.
            vector[index] += sign * (1.0 + math.log(count))

        return self._normalize(vector)

    def embed_batch(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        return tuple(self.embed(text) for text in texts)

    # -- internos ----------------------------------------------------------

    @staticmethod
    def _features(tokens: list[str]) -> dict[str, int]:
        """Unigramas e bigramas: o bigrama carrega a ordem que o unigrama perde."""
        features: dict[str, int] = {}
        for token in tokens:
            features[token] = features.get(token, 0) + 1
        for first, second in zip(tokens, tokens[1:], strict=False):
            bigram = f"{first}_{second}"
            features[bigram] = features.get(bigram, 0) + 1
        return features

    def _bucket(self, feature: str) -> tuple[int, float]:
        """Índice e sinal do balde.

        O sinal derivado de um segundo bit do hash reduz o viés de colisão:
        colisões tendem a se cancelar em vez de se somar.
        """
        digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
        value = int.from_bytes(digest, "big")
        index = value % self._dimensions
        sign = 1.0 if (value >> 63) & 1 else -1.0
        return index, sign

    @staticmethod
    def _normalize(vector: list[float]) -> tuple[float, ...]:
        norm = math.sqrt(sum(component * component for component in vector))
        if norm == 0.0:
            return tuple(vector)
        return tuple(component / norm for component in vector)


def cosine_similarity(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    """Similaridade do cosseno entre vetores já normalizados."""
    if len(left) != len(right):
        raise ValueError("Vetores de dimensões diferentes não são comparáveis.")
    return sum(a * b for a, b in zip(left, right, strict=True))
