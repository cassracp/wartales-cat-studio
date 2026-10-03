"""
Módulo de Garantia de Qualidade (QA) e Auditoria Linguística.
Executa checagens automáticas de integridade de tags, variáveis de interpolação,
conformidade CastleDB e violação de glossário/sinônimos proibidos.
"""

import re
from typing import Any, Dict, List, Optional
from nucleo.normalizador import extrair_tokens_protegidos


class ServicoGarantiaQualidade:
    """Validador e auditor de regras de qualidade e conformidade estrutural."""

    @staticmethod
    def validar_segmento(
        texto_origem_en: str,
        texto_traducao_pt: str,
        termos_glossario: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Executa todas as verificações de QA em um par de frases.
        Retorna dicionário com status de erro, lista de avisos e detalhes.
        """
        avisos: List[str] = []
        tem_inconsistencia = False

        if not texto_traducao_pt or not texto_traducao_pt.strip():
            return {
                "valido": True,
                "tem_inconsistencia": False,
                "avisos": [],
                "tags_faltantes": []
            }

        # 1. Checagem de quebra de linha inicial (risco de assert no CastleDB)
        if re.match(r"^\s*<br\s*/?>", texto_traducao_pt, re.IGNORECASE):
            avisos.append("Alerta CastleDB: o texto inicia com tag <br/>, o que pode causar 'assert' no motor Heaps.io.")
            tem_inconsistencia = True

        # 2. Checagem de integridade de tokens e variáveis protegidas
        tokens_origem = set(extrair_tokens_protegidos(texto_origem_en))
        tokens_traducao = set(extrair_tokens_protegidos(texto_traducao_pt))
        tokens_faltantes = tokens_origem - tokens_traducao

        if tokens_faltantes:
            avisos.append(f"Variáveis ou tags ausentes na tradução: {', '.join(sorted(tokens_faltantes))}")
            tem_inconsistencia = True

        # 3. Checagem de fechamento balanceado de tags HTML/XML básicas
        for tag in ["b", "i", "u", "good", "bad", "skill", "gold"]:
            aberturas = len(re.findall(rf"<{tag}\b[^>]*>", texto_traducao_pt, re.IGNORECASE))
            fechamentos = len(re.findall(rf"</{tag}>", texto_traducao_pt, re.IGNORECASE))
            if aberturas != fechamentos:
                avisos.append(f"Desbalanceamento de tag <{tag}>: {aberturas} aberturas vs {fechamentos} fechamentos.")
                tem_inconsistencia = True

        # 4. Checagem de Sinônimos Proibidos do Glossário
        if termos_glossario:
            texto_pt_lower = f" {texto_traducao_pt} "
            for termo in termos_glossario:
                sinonimos_str = termo.get("sinonimos_proibidos", "")
                if not sinonimos_str:
                    continue
                sinonimos = [s.strip() for s in sinonimos_str.split(",") if s.strip()]
                for sin in sinonimos:
                    # Busca de palavra inteira
                    padrao_palavra = rf"(?<!\w){re.escape(sin)}(?!\w)"
                    if re.search(padrao_palavra, texto_pt_lower):
                        termo_padrao = termo.get("termo_pt_padrao", "")
                        termo_en = termo.get("termo_en", "")
                        avisos.append(
                            f"Glossário: Detectado uso do sinônimo não padronizado '{sin}'. "
                            f"O termo oficial para '{termo_en}' é '{termo_padrao}'."
                        )
                        tem_inconsistencia = True

        return {
            "valido": not tem_inconsistencia,
            "tem_inconsistencia": tem_inconsistencia,
            "avisos": avisos,
            "tags_faltantes": list(tokens_faltantes)
        }
