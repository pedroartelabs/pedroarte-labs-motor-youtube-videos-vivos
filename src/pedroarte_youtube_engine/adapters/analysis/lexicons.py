"""Léxicos do português brasileiro usados pela análise heurística.

Estas listas são o "conhecimento de idioma" do motor. Elas são explícitas e
versionadas de propósito: um analisador baseado em LLM pode substituí-las, mas
o caminho padrão precisa funcionar offline e de forma auditável.
"""

from __future__ import annotations

#: Verbos que atribuem uma fala a um personagem — o sinal mais confiável de nome próprio.
ATTRIBUTION_VERBS: frozenset[str] = frozenset(
    {
        "disse",
        "falou",
        "perguntou",
        "respondeu",
        "murmurou",
        "sussurrou",
        "gritou",
        "berrou",
        "exclamou",
        "replicou",
        "retrucou",
        "indagou",
        "observou",
        "comentou",
        "afirmou",
        "acrescentou",
        "continuou",
        "concluiu",
        "insistiu",
        "avisou",
        "explicou",
        "repetiu",
        "admitiu",
        "confessou",
        "ordenou",
        "pediu",
        "resmungou",
        "balbuciou",
        "arriscou",
        "provocou",
        "devolveu",
        "emendou",
        "completou",
    }
)

#: Verbos que, precedidos de um nome próprio, indicam que ele é o sujeito da ação.
#: É o sinal que separa um personagem ("Elias abriu") de um topônimo ("de Portovelho").
NARRATIVE_VERBS: frozenset[str] = frozenset(
    {
        "era", "estava", "tinha", "foi", "ficou", "parecia", "sentiu", "olhou",
        "viu", "ouviu", "pegou", "segurou", "levantou", "abriu", "fechou",
        "entrou", "saiu", "voltou", "andou", "correu", "parou", "sorriu",
        "chorou", "respirou", "puxou", "empurrou", "colocou", "tirou", "deixou",
        "guardou", "escreveu", "leu", "esperou", "sabia", "queria", "podia",
        "devia", "precisava", "lembrou", "pensou", "entendeu", "percebeu",
        "descobriu", "trabalhava", "morava", "vivia", "usava", "vestia",
        "acendeu", "apagou", "girou", "baixou", "apertou", "limpou", "cruzou",
        "encarou", "hesitou", "assentiu", "balançou", "estendeu", "recuou",
    }
    | ATTRIBUTION_VERBS
)

#: Substantivos que denotam lugar. Usados para detectar ambientes recorrentes.
LOCATION_NOUNS: frozenset[str] = frozenset(
    {
        "oficina",
        "casa",
        "quarto",
        "sala",
        "cozinha",
        "corredor",
        "porão",
        "sótão",
        "escada",
        "varanda",
        "jardim",
        "quintal",
        "rua",
        "avenida",
        "praça",
        "beco",
        "esquina",
        "ponte",
        "cais",
        "porto",
        "estação",
        "plataforma",
        "trem",
        "barco",
        "igreja",
        "capela",
        "cemitério",
        "hospital",
        "delegacia",
        "cartório",
        "biblioteca",
        "arquivo",
        "escritório",
        "loja",
        "mercado",
        "bar",
        "café",
        "hotel",
        "pensão",
        "fábrica",
        "galpão",
        "armazém",
        "torre",
        "farol",
        "campo",
        "floresta",
        "mata",
        "rio",
        "lago",
        "praia",
        "montanha",
        "estrada",
        "vila",
        "cidade",
        "bairro",
        "morro",
        "túnel",
        "muro",
        "pátio",
        "salão",
        "ateliê",
        "relojoaria",
    }
)

#: Substantivos com potencial de objeto de cena.
PROP_NOUNS: frozenset[str] = frozenset(
    {
        "relógio",
        "chave",
        "carta",
        "envelope",
        "caderno",
        "livro",
        "diário",
        "fotografia",
        "retrato",
        "espelho",
        "faca",
        "arma",
        "revólver",
        "corda",
        "vela",
        "lanterna",
        "lampião",
        "lâmpada",
        "moeda",
        "anel",
        "colar",
        "medalha",
        "caixa",
        "baú",
        "mala",
        "bolsa",
        "casaco",
        "chapéu",
        "luva",
        "óculos",
        "bengala",
        "guarda-chuva",
        "garrafa",
        "copo",
        "xícara",
        "prato",
        "mesa",
        "cadeira",
        "porta",
        "janela",
        "quadro",
        "mapa",
        "bilhete",
        "documento",
        "papel",
        "pena",
        "tinta",
        "corrente",
        "engrenagem",
        "pêndulo",
        "vidro",
        "ferramenta",
        "lupa",
        "cofre",
        "telegrama",
    }
)

#: Palavras que elevam a tensão percebida de um trecho.
TENSION_WORDS: frozenset[str] = frozenset(
    {
        "medo",
        "pânico",
        "terror",
        "sangue",
        "grito",
        "gritou",
        "correu",
        "fugiu",
        "arma",
        "morte",
        "morreu",
        "matou",
        "escuro",
        "escuridão",
        "tremor",
        "tremia",
        "ameaça",
        "perigo",
        "ferida",
        "golpe",
        "silêncio",
        "sombra",
        "sussurro",
        "estilhaço",
        "quebrou",
        "arrombou",
        "perseguiu",
        "urgência",
        "desespero",
        "aflição",
        "sobressalto",
        "gelou",
        "prendeu",
        "acusou",
        "mentiu",
        "traiu",
        "segredo",
        "confissão",
    }
)

#: Palavras que sinalizam revelação de informação.
REVELATION_WORDS: frozenset[str] = frozenset(
    {
        "descobriu",
        "revelou",
        "percebeu",
        "entendeu",
        "compreendeu",
        "soube",
        "confessou",
        "admitiu",
        "reconheceu",
        "encontrou",
        "achou",
        "leu",
        "mostrou",
        "provou",
        "confirmou",
        "identificou",
        "lembrou",
        "recordou",
    }
)

#: Palavras que sinalizam um mistério aberto.
MYSTERY_WORDS: frozenset[str] = frozenset(
    {
        "mistério",
        "enigma",
        "segredo",
        "desaparecimento",
        "desapareceu",
        "sumiu",
        "inexplicável",
        "estranho",
        "por que",
        "quem",
        "ninguém sabia",
        "nunca soube",
    }
)

#: Mapeia campos semânticos a tons emocionais do domínio.
TONE_LEXICON: dict[str, tuple[str, ...]] = {
    "tenso": ("medo", "perigo", "ameaça", "correu", "fugiu", "arma", "urgência", "sobressalto"),
    "amedrontado": ("pânico", "terror", "tremia", "gelou", "arrepio", "horror"),
    "melancolico": ("saudade", "perda", "vazio", "cinza", "chuva", "silêncio", "solidão"),
    "enlutado": ("morte", "morreu", "luto", "enterro", "túmulo", "velório", "caixão"),
    "irado": ("raiva", "fúria", "gritou", "berrou", "socou", "ódio", "explodiu"),
    "terno": ("carinho", "abraço", "sorriu", "mão", "afago", "ternura", "beijo"),
    "desconfiado": ("mentiu", "mentira", "suspeita", "desconfiou", "encarou", "escondeu"),
    "esperancoso": ("esperança", "amanhecer", "luz", "recomeço", "promessa", "respirou"),
    "determinado": ("decidiu", "resolveu", "firme", "avançou", "encarou", "jurou"),
    "maravilhado": ("deslumbrou", "espanto", "brilho", "imenso", "assombro", "prodígio"),
    "sombrio": ("sombra", "escuridão", "presságio", "corvo", "névoa", "frio"),
    "aliviado": ("alívio", "enfim", "soltou", "respirou fundo", "acabou"),
    "amargo": ("amargura", "rancor", "arrependimento", "tarde demais", "culpa"),
    "sereno": ("calma", "quieto", "sereno", "manso", "tranquilo", "paz"),
}

#: Palavras capitalizadas que não são nomes de personagem.
NON_NAME_CAPITALS: frozenset[str] = frozenset(
    {
        "janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
        "agosto", "setembro", "outubro", "novembro", "dezembro",
        "segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo",
        "deus", "senhor", "senhora", "senhorita", "doutor", "doutora",
        "capítulo", "parte", "livro", "ato", "prólogo", "epílogo",
        "sim", "não", "talvez", "claro", "então", "mas", "porém", "quando",
        "depois", "antes", "agora", "ainda", "havia", "era", "foi", "ele",
        "ela", "eles", "elas", "você", "vocês", "nós", "eu", "isso", "aquilo",
        "esse", "essa", "este", "esta", "aquele", "aquela", "um", "uma",
        "os", "as", "no", "na", "do", "da", "de", "em", "por", "para", "com",
        "que", "se", "sua", "seu", "meu", "minha", "nada", "tudo", "todo",
        "toda", "algo", "alguém", "ninguém", "nunca", "sempre", "só", "já",
    }
)

#: Preposições e artigos que ligam partes de um nome composto ("Maria da Glória").
NAME_CONNECTORS: frozenset[str] = frozenset({"de", "da", "do", "das", "dos", "e", "del", "van"})

#: Palavras que indicam regra de mundo quando aparecem em frase declarativa.
WORLD_RULE_MARKERS: tuple[str, ...] = (
    "nunca se",
    "jamais se",
    "não se pode",
    "é proibido",
    "era proibido",
    "toda vez que",
    "sempre que",
    "por lei",
    "a regra era",
    "a tradição",
    "o costume",
    "desde sempre",
    "só funciona",
    "só podia",
)

#: Palavras que confirmam que uma sentença enuncia mesmo uma regra do universo,
#: e não apenas um hábito de personagem. Sem elas, marcadores frouxos como
#: "sempre que" produzem falsos positivos.
RULE_CONFIRMERS: tuple[str, ...] = (
    "regra",
    "lei",
    "costume",
    "tradição",
    "proibido",
    "proibida",
    "nunca se",
    "jamais se",
    "não se pode",
    "ninguém pode",
    "só funciona",
    "só podia",
    "desde sempre",
)

#: Marcadores de proibição explícita no universo da obra.
PROHIBITION_MARKERS: tuple[str, ...] = (
    "é proibido",
    "era proibido",
    "não se pode",
    "não podia",
    "jamais",
    "sob nenhuma circunstância",
    "nunca deve",
)
