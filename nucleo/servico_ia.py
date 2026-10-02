# -*- coding: utf-8 -*-
"""
================================================================================
 Módulo de Serviço de IA (Gemini) - Wartales CAT Studio
================================================================================
 Integração direta ou via GerenciadorPoolIA com a API do Google Gemini Flash Lite
 para tradução contextualizada, respeitando terminologias oficiais e tags CastleDB.
 Nomenclatura 100% em Português do Brasil (pt-BR).
================================================================================
"""

import os
import json
import time
import urllib.request
import urllib.error
import logging
from typing import Optional, Dict, Any

from nucleo.gerenciador_pool_ia import (
    GerenciadorPoolIA,
    obter_instancia_pool_ia,
    PROMPT_SISTEMA_WARTALES_PADRAO
)

logger = logging.getLogger("cat_wartales.ia")

CHAVE_PADRAO_GEMINI = os.environ.get("CHAVE_API_GEMINI", "")
MODELO_PADRAO = "gemini-flash-lite-latest"
PROMPT_SISTEMA_WARTALES = PROMPT_SISTEMA_WARTALES_PADRAO


class ServicoIA:
    """Gerencia chamadas diretas ou roteadas via Pool de IA para tradução assistida."""

    def __init__(
        self,
        chave_api: Optional[str] = None,
        modelo: str = MODELO_PADRAO,
        gerenciador_pool: Optional[GerenciadorPoolIA] = None
    ):
        self.chave_api = chave_api
        self.modelo = modelo
        self.gerenciador_pool = gerenciador_pool

    def traduzir_texto(self, texto_en: str) -> Dict[str, Any]:
        """
        Envia um texto individual em inglês para ser traduzido pela IA.
        Se um GerenciadorPoolIA estiver configurado ou disponível com chaves ativas,
        utiliza o pool para balanceamento (Round-Robin / Fallback) e Circuit Breaker.
        Retorna dicionário contendo {"sucesso": bool, "traducao": str, "erro": str}.
        """
        if not texto_en or not texto_en.strip():
            return {"sucesso": True, "traducao": "", "erro": ""}

        # 1. Utilizar pool explicitamente injetado
        if self.gerenciador_pool is not None:
            return self.gerenciador_pool.executar_traducao(
                texto_en=texto_en,
                modelo_override=self.modelo
            )

        # 2. Se nenhuma chave direta foi especificada, consultar o pool global compartilhado
        if not self.chave_api:
            try:
                pool_global = obter_instancia_pool_ia()
                if pool_global and pool_global.possui_chaves_cadastradas():
                    return pool_global.executar_traducao(
                        texto_en=texto_en,
                        modelo_override=self.modelo
                    )
            except Exception as erro_pool:
                logger.warning(f"Falha ao consultar pool global de IA: {erro_pool}")

        # 3. Execução direta com chave individual (retrocompatibilidade)
        chave_utilizar = (self.chave_api or "").strip() or CHAVE_PADRAO_GEMINI
        if not chave_utilizar:
            return {
                "sucesso": False,
                "traducao": "",
                "erro": "Nenhuma chave de API configurada para o serviço de IA."
            }

        prompt_usuario = f"Texto a traduzir:\n{texto_en.strip()}"
        prompt_completo = f"{PROMPT_SISTEMA_WARTALES}\n\n{prompt_usuario}"

        payload = json.dumps({
            "contents": [{"parts": [{"text": prompt_completo}]}],
            "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"}
        }).encode("utf-8")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.modelo}:generateContent?key={chave_utilizar}"
        requisicao = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})

        tentativas = 0
        while tentativas < 3:
            tentativas += 1
            try:
                t0 = time.time()
                with urllib.request.urlopen(requisicao, timeout=30) as resposta:
                    dados = json.loads(resposta.read().decode("utf-8"))
                tempo_decorrido = round(time.time() - t0, 2)

                texto_resposta = dados["candidates"][0]["content"]["parts"][0]["text"]
                resposta_json = json.loads(texto_resposta)
                traducao = resposta_json.get("pt", "").strip()

                logger.info(f"Tradução IA concluída com sucesso em {tempo_decorrido}s.")
                return {
                    "sucesso": True,
                    "traducao": traducao,
                    "tempo_segundos": tempo_decorrido,
                    "erro": ""
                }
            except urllib.error.HTTPError as http_err:
                detalhe = http_err.read().decode("utf-8", errors="replace")
                logger.warning(f"Tentativa {tentativas} falhou com HTTP {http_err.code}: {detalhe}")
                if tentativas >= 3:
                    return {"sucesso": False, "traducao": "", "erro": f"HTTP {http_err.code}: {detalhe}"}
                time.sleep(2)
            except Exception as e:
                logger.warning(f"Tentativa {tentativas} falhou: {e}")
                if tentativas >= 3:
                    return {"sucesso": False, "traducao": "", "erro": str(e)}
                time.sleep(1)

        return {"sucesso": False, "traducao": "", "erro": "Limite de tentativas excedido"}
