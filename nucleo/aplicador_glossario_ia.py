# -*- coding: utf-8 -*-
"""
================================================================================
 Aplicador de Glossário à Tradução por IA - Wartales CAT Studio
================================================================================
 Garante que a IA (qualquer provedor/modelo) respeite o glossário oficial:
  1. Seleciona os termos do glossário que aparecem no texto em inglês.
  2. Injeta esses termos como regra obrigatória no prompt de sistema.
  3. Verifica a resposta (termo padrão presente e sinônimos proibidos ausentes).
================================================================================
"""

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from nucleo.gerenciador_pool_ia import PROMPT_SISTEMA_WARTALES_PADRAO


def _normalizar_comparacao(texto: str) -> str:
    """Minúsculas e sem acentos, para comparações tolerantes."""
    decomposto = unicodedata.normalize("NFD", texto or "")
    return "".join(c for c in decomposto if unicodedata.category(c) != "Mn").lower()


@dataclass
class ResultadoVerificacaoGlossario:
    """Resultado da conferência de uma tradução contra os termos aplicáveis."""
    conforme: bool = True
    violacoes: List[str] = field(default_factory=list)


class AplicadorGlossarioIA:
    """Injeta e audita o glossário nas traduções geradas por IA."""

    def __init__(self, fonte_termos: Callable[[], List[Dict[str, Any]]]):
        # A fonte é consultada a cada tradução, refletindo edições recentes do glossário.
        self._fonte_termos = fonte_termos

    @classmethod
    def de_lista(cls, termos: List[Dict[str, Any]]) -> "AplicadorGlossarioIA":
        """Cria um aplicador com um retrato fixo do glossário (útil em lotes grandes)."""
        copia = list(termos)
        return cls(lambda: copia)

    # ------------------------------------------------------------------
    # Seleção dos termos relevantes
    # ------------------------------------------------------------------

    def selecionar_termos(self, texto_en: str) -> List[Dict[str, Any]]:
        """Retorna os termos presentes no texto, ignorando os cobertos por termos maiores."""
        texto = texto_en or ""
        texto_min = texto.lower()
        candidatos: List[Tuple[Dict[str, Any], List[Tuple[int, int]]]] = []

        for termo in self._fonte_termos() or []:
            termo_en = (termo.get("termo_en") or "").strip()
            if not termo_en or not (termo.get("termo_pt_padrao") or "").strip():
                continue
            if termo_en not in texto:
                continue
            padrao = rf"(?<!\w){re.escape(termo_en)}(?:es|s)?(?!\w)"
            trechos = [m.span() for m in re.finditer(padrao, texto)]
            if trechos:
                candidatos.append((termo, trechos))

        candidatos.sort(key=lambda item: len(item[0]["termo_en"]), reverse=True)
        mantidos: List[Dict[str, Any]] = []
        spans_ocupados: List[Tuple[int, int]] = []
        for termo, trechos in candidatos:
            livres = [
                t for t in trechos
                if not any(ini <= t[0] and t[1] <= fim for ini, fim in spans_ocupados)
            ]
            if livres:
                mantidos.append(termo)
                spans_ocupados.extend(livres)

        return sorted(mantidos, key=lambda t: t["termo_en"].lower())

    # ------------------------------------------------------------------
    # Montagem de prompts
    # ------------------------------------------------------------------

    @staticmethod
    def _listar_sinonimos(termo: Dict[str, Any]) -> List[str]:
        bruto = termo.get("sinonimos_proibidos") or ""
        return [s.strip() for s in bruto.split(",") if s.strip()]

    def montar_instrucoes(self, termos: List[Dict[str, Any]]) -> str:
        """Prompt de sistema padrão acrescido do bloco de glossário obrigatório."""
        if not termos:
            return PROMPT_SISTEMA_WARTALES_PADRAO

        linhas = []
        for termo in termos:
            linha = f'- "{termo["termo_en"]}" => "{termo["termo_pt_padrao"]}"'
            sinonimos = self._listar_sinonimos(termo)
            if sinonimos:
                linha += f' (PROIBIDO usar: {", ".join(sinonimos)})'
            nota = (termo.get("notas") or "").strip()
            if nota:
                linha += f" [Nota: {nota}]"
            linhas.append(linha)

        bloco = (
            "\nGLOSSÁRIO OFICIAL DO JOGO (OBRIGATÓRIO):\n"
            "Este glossário foi definido manualmente a partir do jogo original e tem PRIORIDADE "
            "ABSOLUTA sobre as regras de terminologia acima e sobre qualquer outra tradução que "
            "você conheça. Sempre que um termo abaixo aparecer no texto (inclusive no plural), "
            "use EXATAMENTE a tradução indicada, ajustando apenas número e gênero para "
            "concordar com a frase. Jamais use os sinônimos proibidos.\n"
            + "\n".join(linhas)
            + "\n"
        )
        return PROMPT_SISTEMA_WARTALES_PADRAO + bloco

    def montar_instrucoes_correcao(
        self,
        termos: List[Dict[str, Any]],
        violacoes: List[str],
        traducao_rejeitada: str
    ) -> str:
        """Prompt de refação listando exatamente o que a tentativa anterior violou."""
        itens = "\n".join(f"- {v}" for v in violacoes)
        return (
            self.montar_instrucoes(termos)
            + "\nCORREÇÃO NECESSÁRIA:\n"
            "Sua tradução anterior foi REJEITADA por violar o glossário oficial.\n"
            f"Tradução rejeitada: {traducao_rejeitada}\n"
            f"Problemas encontrados:\n{itens}\n"
            "Refaça a tradução corrigindo todos os problemas, sem alterar tags nem formatação.\n"
        )

    # ------------------------------------------------------------------
    # Verificação da resposta
    # ------------------------------------------------------------------

    def verificar(self, traducao: str, termos: List[Dict[str, Any]]) -> ResultadoVerificacaoGlossario:
        """Confere se a tradução usa os termos padrão e evita os sinônimos proibidos."""
        resultado = ResultadoVerificacaoGlossario()
        if not termos:
            return resultado

        trad_norm = _normalizar_comparacao(traducao)
        trad_sem_padroes = trad_norm
        for termo in termos:
            padrao_norm = _normalizar_comparacao(termo["termo_pt_padrao"])
            if padrao_norm:
                trad_sem_padroes = trad_sem_padroes.replace(padrao_norm, " ")

        for termo in termos:
            padrao_norm = _normalizar_comparacao(termo["termo_pt_padrao"])
            if padrao_norm not in trad_norm:
                resultado.violacoes.append(
                    f'O termo "{termo["termo_en"]}" deveria ser traduzido como "{termo["termo_pt_padrao"]}".'
                )
            for sinonimo in self._listar_sinonimos(termo):
                sin_norm = _normalizar_comparacao(sinonimo)
                if sin_norm and re.search(rf"(?<!\w){re.escape(sin_norm)}(?!\w)", trad_sem_padroes):
                    resultado.violacoes.append(
                        f'Uso proibido de "{sinonimo}"; para "{termo["termo_en"]}" use "{termo["termo_pt_padrao"]}".'
                    )

        resultado.conforme = not resultado.violacoes
        return resultado
