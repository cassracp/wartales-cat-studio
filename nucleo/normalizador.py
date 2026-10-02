"""
Módulo de normalização de textos, sanitização estrutural para CastleDB
e geração de chaves de concordância.
"""

import hashlib
import re
from typing import List, Tuple


def normalizar_espacos(texto: str) -> str:
    """Normaliza múltiplos espaços em branco, quebras de linha e tabulações."""
    if not texto:
        return ""
    return re.sub(r"\s+", " ", texto).strip()


def sanitizar_para_castledb(texto: str) -> str:
    """
    Higieniza o texto para conformidade estrita com a engine Heaps.io e CastleDB.
    Remove quebras de linha (<br/>) no início da frase, prevenindo crashes de
    'assert' em cdb.Lang / Trails.hx.
    """
    if not texto:
        return ""
    # Remove tags <br>, <br/> ou <br /> no início do texto
    texto_limpo = re.sub(r"^(?:\s*<br\s*/?>)+\s*", "", texto)
    return texto_limpo


def extrair_tokens_protegidos(texto: str) -> List[str]:
    """
    Extrai tokens que não podem ser corrompidos ou perdidos na tradução:
    - Variáveis de interpolação: ::nome::, ::valor::, $val, etc.
    - Tags de formatação de cores e estilo: <b>, </b>, <good>, <bad>, <skill>, <gold>
    - Ícones e placeholders entre colchetes: [DMG], [KOROAS], [INFL], etc.
    """
    if not texto:
        return []
    
    padroes = [
        r"::[a-zA-Z0-9_\-]+::",          # Ex: ::name::, ::target::
        r"\[[A-Za-z0-9_\-]+\]",           # Ex: [DMG], [CRIT]
        r"<\/?(?:b|i|u|good|bad|skill|gold|neutral|warning|color)[^>]*>", # Tags XML/HTML
        r"\{[0-9]+\}",                    # Ex: {0}, {1}
        r"\$[a-zA-Z0-9_]+"               # Ex: $valor
    ]
    
    expressao = re.compile("|".join(padroes), re.IGNORECASE)
    return expressao.findall(texto)


def gerar_hash_conteudo(texto: str) -> str:
    """Gera hash SHA-256 do texto normalizado para agrupamento exato de repetições."""
    texto_base = normalizar_espacos(texto).lower()
    return hashlib.sha256(texto_base.encode("utf-8")).hexdigest()
