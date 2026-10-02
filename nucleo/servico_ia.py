# -*- coding: utf-8 -*-
"""
================================================================================
 Módulo de Serviço de IA (Gemini) - Wartales CAT Studio
================================================================================
 Integração direta com a API do Google Gemini Flash Lite para tradução
 contextualizada, respeitando terminologias oficiais e tags CastleDB.
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

logger = logging.getLogger("cat_wartales.ia")

CHAVE_PADRAO_GEMINI = os.environ.get("CHAVE_API_GEMINI", "")
MODELO_PADRAO = "gemini-flash-lite-latest"

PROMPT_SISTEMA_WARTALES = """Você é um tradutor sênior especializado na localização oficial de Wartales para Português do Brasil (pt-BR).
Traduza o texto em inglês mantendo fidelidade absoluta ao estilo do jogo original da Shiro Games.

REGRAS:
1. Mantenha TODAS as tags XML, HTML e marcações intactas:
   - Ex: [DMG], [Fervor], [Bleeding], [Movement], [Willpower], ::value::, $val$, {val}
   - Ex: <skill>Lone Wolf</skill>, <b>...</b>, <br />, <br/>, &lt;b&gt;...&lt;/b&gt;
   - NUNCA adicione nem remova tags de quebra de linha ou formatação.
2. Padrões de terminologia:
   - "Armour:" -> "Armadura:"
   - "Helmet:" -> "Capacete:"
   - "Default Scaling, Levels 1 -> 15:" -> "Escalonamento Padrão, Níveis 1 -> 15:"
   - "Strength:" -> "Força:", "Dexterity:" -> "Destreza:", "Constitution:" -> "Constituição:"
   - "Additional abilities, Level -> Skill:" -> "Habilidades adicionais, Nível -> Habilidade:"
   - "Capture: 1 rope" -> "Captura: 1 corda"
   - "Light" -> "Leve", "Medium" -> "Média" (ou Médio), "Heavy" -> "Pesada" (ou Pesado), "None" -> "Nenhuma"
3. Responda ESTRITAMENTE em formato JSON com o schema:
   {"pt": "texto traduzido"}
"""


class ServicoIA:
    """Gerencia chamadas diretas à API generativa para tradução assistida."""

    def __init__(self, chave_api: str = CHAVE_PADRAO_GEMINI, modelo: str = MODELO_PADRAO):
        self.chave_api = chave_api
        self.modelo = modelo

    def traduzir_texto(self, texto_en: str) -> Dict[str, Any]:
        """
        Envia um texto individual em inglês para ser traduzido pela IA.
        Retorna dicionário contendo {"sucesso": bool, "traducao": str, "erro": str}.
        """
        if not texto_en or not texto_en.strip():
            return {"sucesso": True, "traducao": "", "erro": ""}

        prompt_usuario = f"Texto a traduzir:\n{texto_en.strip()}"
        prompt_completo = f"{PROMPT_SISTEMA_WARTALES}\n\n{prompt_usuario}"

        payload = json.dumps({
            "contents": [{"parts": [{"text": prompt_completo}]}],
            "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"}
        }).encode("utf-8")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.modelo}:generateContent?key={self.chave_api}"
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
