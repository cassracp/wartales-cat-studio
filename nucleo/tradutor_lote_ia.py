# -*- coding: utf-8 -*-
"""
================================================================================
 Módulo de Tradução em Lote por IA com Deep TM - Wartales CAT Studio
================================================================================
 Executa a tradução de novos mods de Wartales de forma hiper-otimizada:
 1. Isolamento de Deltas: identifica exatamente o que é inédito no mod.
 2. Reutilização de 100% do Vanilla oficial e da Memória Global (0 tokens gastos).
 3. Tradução em lotes paralelos pelo Gemini Flash Lite apenas das novidades.
 4. Geração dos arquivos finais texts_pt-BR.xml e export_pt-BR.xml sanitizados
    para o motor CastleDB da Shiro Games.
================================================================================
"""

import os
import re
import math
import time
import json
import logging
import threading
from collections import deque
import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Optional, Callable

from nucleo.normalizador import normalizar_espacos, sanitizar_para_castledb, gerar_hash_conteudo
from nucleo.memoria_global import MemoriaTraducaoGlobal
from nucleo.servico_ia import ServicoIA, CHAVE_PADRAO_GEMINI
from nucleo.aplicador_glossario_ia import AplicadorGlossarioIA
from nucleo.gerenciador_pool_ia import GerenciadorPoolIA
from nucleo.sincronizador import SincronizadorXml

logger = logging.getLogger("cat_wartales.tradutor_lote")

LIMITE_LOG_LOTE = 300
TENTATIVAS_POR_FRASE = 3
ESPERAS_COOLDOWN_MAXIMAS = 6
PREVIA_TEXTO_LOG = 60


class MotorTraducaoLoteIA:
    """Orquestra o pipeline de isolamento de deltas e tradução em lote."""

    def __init__(
        self,
        memoria_global: Optional[MemoriaTraducaoGlobal] = None,
        gerenciador_pool: Optional[GerenciadorPoolIA] = None,
        aplicador_glossario: Optional[AplicadorGlossarioIA] = None
    ):
        self.aplicador_glossario = aplicador_glossario
        self.memoria_global = memoria_global or MemoriaTraducaoGlobal()
        self.gerenciador_pool = gerenciador_pool
        self._lock = threading.Lock()
        self._log: deque = deque(maxlen=LIMITE_LOG_LOTE)
        self._proximo_id_log = 1
        self.estado_execucao: Dict[str, Any] = self._criar_estado_inicial()

    def _congelar_glossario(self) -> Optional[AplicadorGlossarioIA]:
        """Retrato do glossário no início do lote, evitando uma consulta ao banco por frase."""
        if self.aplicador_glossario is None:
            return None
        try:
            return AplicadorGlossarioIA.de_lista(self.aplicador_glossario._fonte_termos())
        except Exception as erro:
            logger.error(f"Falha ao carregar glossário para o lote: {erro}")
            return None

    @staticmethod
    def _criar_estado_inicial() -> Dict[str, Any]:
        return {
            "ativo": False,
            "concluido": False,
            "erro": None,
            "porcentagem": 0.0,
            "segmentos_processados": 0,
            "total_segmentos": 0,
            "reaproveitados": 0,
            "frases_ia_traduzidas": 0,
            "falhas_ia": 0,
            "fora_do_glossario": 0,
            "total_para_ia": 0,
            "aguardando_segundos": 0,
            "provedores": {},
            "mensagem": "Pronto para iniciar.",
            "data_inicio": None,
            "tempo_decorrido_segundos": 0,
        }

    def _registrar_log_sem_lock(self, nivel: str, mensagem: str) -> None:
        self._log.append({
            "id": self._proximo_id_log,
            "hora": time.strftime("%H:%M:%S"),
            "nivel": nivel,
            "mensagem": mensagem,
        })
        self._proximo_id_log += 1

    def _registrar_log(self, nivel: str, mensagem: str) -> None:
        with self._lock:
            self._registrar_log_sem_lock(nivel, mensagem)

    def obter_status(self) -> Dict[str, Any]:
        """Retorna uma cópia do estado atual da tradução em lote, incluindo o log de eventos."""
        with self._lock:
            res = dict(self.estado_execucao)
            res["provedores"] = dict(res["provedores"])
            if res["ativo"] and res["data_inicio"]:
                res["tempo_decorrido_segundos"] = round(time.time() - res["data_inicio"], 1)
                feitas = res["frases_ia_traduzidas"] + res["falhas_ia"]
                restantes = res["total_para_ia"] - feitas
                if feitas > 0 and restantes > 0:
                    res["estimativa_restante_segundos"] = int(res["tempo_decorrido_segundos"] / feitas * restantes)
            res["log"] = list(self._log)
            return res

    @staticmethod
    def _previa(texto: str) -> str:
        limpo = " ".join((texto or "").split())
        return limpo if len(limpo) <= PREVIA_TEXTO_LOG else limpo[:PREVIA_TEXTO_LOG] + "…"

    def _traduzir_com_retentativas(self, servico_ia: ServicoIA, chave: str, texto_en: str) -> Optional[str]:
        """
        Traduz uma frase tolerando falhas: aguarda cooldown (429) do pool e retenta.
        Retorna a tradução ou None se esgotar as tentativas (nunca devolve o texto em inglês).
        """
        previa = self._previa(texto_en)
        esperas = 0
        tentativa = 0
        while tentativa < TENTATIVAS_POR_FRASE:
            tentativa += 1
            resultado = servico_ia.traduzir_texto(texto_en)

            if resultado.get("sucesso") and (resultado.get("traducao") or "").strip():
                provedor = resultado.get("rotulo_chave") or resultado.get("provedor") or "chave direta"
                with self._lock:
                    provs = self.estado_execucao["provedores"]
                    provs[provedor] = provs.get(provedor, 0) + 1
                glossario = resultado.get("glossario")
                if glossario and not glossario.get("conforme", True):
                    with self._lock:
                        self.estado_execucao["fora_do_glossario"] += 1
                    self._registrar_log("aviso", f"[{chave}] fora do glossário ({'; '.join(glossario.get('violacoes', []))}): {previa}")
                else:
                    tempo = resultado.get("tempo_segundos")
                    sufixo = f" ({tempo}s)" if tempo else ""
                    self._registrar_log("ok", f"[{chave}] traduzido via {provedor}{sufixo}: {previa}")
                return resultado["traducao"]

            erro = resultado.get("erro") or "resposta vazia da IA"
            if resultado.get("em_cooldown") and esperas < ESPERAS_COOLDOWN_MAXIMAS:
                esperas += 1
                tentativa -= 1
                segundos = int(resultado.get("segundos_espera") or 5) + 1
                self._registrar_log("aviso", f"Todas as chaves em cooldown (429). Aguardando {segundos}s ({esperas}/{ESPERAS_COOLDOWN_MAXIMAS})...")
                self._aguardar(segundos)
                continue

            self._registrar_log("erro", f"[{chave}] tentativa {tentativa}/{TENTATIVAS_POR_FRASE} falhou: {self._previa(erro)[:160]}")

        return None

    def _aguardar(self, segundos: int) -> None:
        """Espera atualizando o contador exibido na interface."""
        for restante in range(segundos, 0, -1):
            with self._lock:
                self.estado_execucao["aguardando_segundos"] = restante
            time.sleep(1)
        with self._lock:
            self.estado_execucao["aguardando_segundos"] = 0

    def _traduzir_pendencias(
        self,
        pendencias: List[Dict[str, str]],
        destino: Dict[str, str],
        servico_ia: ServicoIA,
        novos_pares_tm: List[Dict[str, str]],
        total_itens: int,
        total_pendencias: int,
    ) -> None:
        """Traduz as pendências de um arquivo. Falhas mantêm o inglês no arquivo, mas não poluem a memória."""
        for item in pendencias:
            traducao = self._traduzir_com_retentativas(servico_ia, item["chave"], item["en"])
            if traducao is None:
                destino[item["chave"]] = item["en"]
                with self._lock:
                    self.estado_execucao["falhas_ia"] += 1
                self._registrar_log("erro", f"[{item['chave']}] FALHOU: mantido em inglês e fora da Memória de Tradução.")
            else:
                pt_sanitizado = sanitizar_para_castledb(traducao)
                destino[item["chave"]] = pt_sanitizado
                novos_pares_tm.append({"en": item["en"], "pt": pt_sanitizado})
                with self._lock:
                    self.estado_execucao["frases_ia_traduzidas"] += 1

            with self._lock:
                self.estado_execucao["segmentos_processados"] += 1
                proc = self.estado_execucao["segmentos_processados"]
                self.estado_execucao["porcentagem"] = round(proc / total_itens * 100, 1) if total_itens else 100.0
                feitas = self.estado_execucao["frases_ia_traduzidas"] + self.estado_execucao["falhas_ia"]
                self.estado_execucao["mensagem"] = f"Traduzindo com IA: {feitas}/{total_pendencias}..."
    def analisar_deltas(
        self,
        diretorio_vanilla: str,
        diretorio_mod_en: str
    ) -> Dict[str, Any]:
        """
        Analisa os XMLs do mod comparando-os com o Vanilla oficial e com a Memória Global.
        Retorna estimativas exatas de economia de tokens e frases restantes para a IA.
        """
        mod_texts_path = os.path.join(diretorio_mod_en, "texts_en.xml")
        mod_export_path = os.path.join(diretorio_mod_en, "export_en.xml")

        v_texts_en_path = os.path.join(diretorio_vanilla, "texts_en.xml")
        v_texts_pt_path = os.path.join(diretorio_vanilla, "texts_pt-BR.xml")
        v_export_en_path = os.path.join(diretorio_vanilla, "export_en.xml")
        v_export_pt_path = os.path.join(diretorio_vanilla, "export_pt-BR.xml")

        dict_m_texts = SincronizadorXml.extrair_dicionario_texts(mod_texts_path)
        dict_m_export = SincronizadorXml.extrair_mapa_elementos_export(mod_export_path)

        dict_v_texts_en = SincronizadorXml.extrair_dicionario_texts(v_texts_en_path)
        dict_v_texts_pt = SincronizadorXml.extrair_dicionario_texts(v_texts_pt_path)

        dict_v_export_en = SincronizadorXml.extrair_mapa_elementos_export(v_export_en_path)
        dict_v_export_pt = SincronizadorXml.extrair_mapa_elementos_export(v_export_pt_path)

        # Mapa em memória da TM Global para busca instantânea (<10ms)
        tm_dict = self.memoria_global.carregar_dicionario_completo()

        total_segmentos = len(dict_m_texts) + len(dict_m_export)
        if total_segmentos == 0:
            return {
                "total_segmentos": 0,
                "reaproveitamento_oficial": 0,
                "reaproveitamento_tm_global": 0,
                "necessita_ia": 0,
                "porcentagem_reaproveitamento": 0.0,
                "estimativa_chamadas_ia": 0,
                "estimativa_tempo_segundos": 0,
                "aviso": "Nenhum arquivo XML encontrado no diretório do Mod em inglês."
            }

        reaproveitamento_oficial = 0
        reaproveitamento_tm_global = 0
        necessita_ia = 0

        # Analisar texts
        for chave, texto_en in dict_m_texts.items():
            en_limpo = normalizar_espacos(texto_en)
            if not en_limpo:
                continue

            v_en = normalizar_espacos(dict_v_texts_en.get(chave, ""))
            v_pt = dict_v_texts_pt.get(chave, "")

            if v_pt and v_en == en_limpo:
                reaproveitamento_oficial += 1
            else:
                hash_c = gerar_hash_conteudo(en_limpo)
                if hash_c in tm_dict:
                    reaproveitamento_tm_global += 1
                else:
                    necessita_ia += 1

        # Analisar export
        for chave, texto_en in dict_m_export.items():
            en_limpo = normalizar_espacos(texto_en)
            if not en_limpo:
                continue

            v_en = normalizar_espacos(dict_v_export_en.get(chave, ""))
            v_pt = dict_v_export_pt.get(chave, "")

            if v_pt and v_en == en_limpo:
                reaproveitamento_oficial += 1
            else:
                hash_c = gerar_hash_conteudo(en_limpo)
                if hash_c in tm_dict:
                    reaproveitamento_tm_global += 1
                else:
                    necessita_ia += 1

        total_reaproveitado = reaproveitamento_oficial + reaproveitamento_tm_global
        pct_reaproveitamento = round((total_reaproveitado / total_segmentos * 100), 1) if total_segmentos > 0 else 0.0

        tamanho_lote = 15
        qtd_chamadas = math.ceil(necessita_ia / tamanho_lote)
        tempo_estimado = round(qtd_chamadas * 1.5, 0)

        return {
            "total_segmentos": total_segmentos,
            "total_texts": len(dict_m_texts),
            "total_export": len(dict_m_export),
            "reaproveitamento_oficial": reaproveitamento_oficial,
            "reaproveitamento_tm_global": reaproveitamento_tm_global,
            "necessita_ia": necessita_ia,
            "porcentagem_reaproveitamento": pct_reaproveitamento,
            "estimativa_chamadas_ia": qtd_chamadas,
            "estimativa_tempo_segundos": int(tempo_estimado)
        }

    def iniciar_traducao_assincrona(
        self,
        diretorio_vanilla: str,
        diretorio_mod_en: str,
        diretorio_saida_ia: str,
        chave_api_gemini: Optional[str] = None,
        nome_mod: str = ""
    ) -> bool:
        """Inicia a tradução em lote em uma thread dedicada em segundo plano."""
        with self._lock:
            if self.estado_execucao["ativo"]:
                return False  # Já está em execução

            self.estado_execucao = self._criar_estado_inicial()
            self.estado_execucao.update({
                "ativo": True,
                "mensagem": "Iniciando análise e pipeline de tradução...",
                "data_inicio": time.time(),
            })
            self._log.clear()
            self._proximo_id_log = 1
            self._registrar_log_sem_lock("info", "Lote iniciado.")

        thread = threading.Thread(
            target=self._executar_pipeline_completo,
            args=(diretorio_vanilla, diretorio_mod_en, diretorio_saida_ia, chave_api_gemini, nome_mod),
            daemon=True
        )
        thread.start()
        return True

    def _executar_pipeline_completo(
        self,
        diretorio_vanilla: str,
        diretorio_mod_en: str,
        diretorio_saida_ia: str,
        chave_api: Optional[str],
        nome_mod: str
    ) -> None:
        try:
            chave_utilizar = (chave_api or "").strip()
            if self.gerenciador_pool is not None and self.gerenciador_pool.possui_chaves_cadastradas():
                servico_ia = ServicoIA(gerenciador_pool=self.gerenciador_pool)
            elif chave_utilizar:
                servico_ia = ServicoIA(chave_api=chave_utilizar)
            else:
                servico_ia = ServicoIA(gerenciador_pool=self.gerenciador_pool)
            servico_ia.aplicador_glossario = self._congelar_glossario()
            os.makedirs(diretorio_saida_ia, exist_ok=True)

            mod_texts_path = os.path.join(diretorio_mod_en, "texts_en.xml")
            mod_export_path = os.path.join(diretorio_mod_en, "export_en.xml")

            v_texts_en_path = os.path.join(diretorio_vanilla, "texts_en.xml")
            v_texts_pt_path = os.path.join(diretorio_vanilla, "texts_pt-BR.xml")
            v_export_en_path = os.path.join(diretorio_vanilla, "export_en.xml")
            v_export_pt_path = os.path.join(diretorio_vanilla, "export_pt-BR.xml")

            dict_m_texts = SincronizadorXml.extrair_dicionario_texts(mod_texts_path)
            dict_m_export = SincronizadorXml.extrair_mapa_elementos_export(mod_export_path)

            dict_v_texts_en = SincronizadorXml.extrair_dicionario_texts(v_texts_en_path)
            dict_v_texts_pt = SincronizadorXml.extrair_dicionario_texts(v_texts_pt_path)

            dict_v_export_en = SincronizadorXml.extrair_mapa_elementos_export(v_export_en_path)
            dict_v_export_pt = SincronizadorXml.extrair_mapa_elementos_export(v_export_pt_path)

            tm_dict = self.memoria_global.carregar_dicionario_completo()

            total_itens = len(dict_m_texts) + len(dict_m_export)
            with self._lock:
                self.estado_execucao["total_segmentos"] = total_itens
                self.estado_execucao["mensagem"] = f"Mapeando {total_itens:,} segmentos do mod..."

            resultado_texts_pt: Dict[str, str] = {}
            resultado_export_pt: Dict[str, str] = {}

            pendencias_ia_texts: List[Dict[str, str]] = []
            pendencias_ia_export: List[Dict[str, str]] = []

            # 1. Processamento rápido de texts_en.xml
            for chave, texto_en in dict_m_texts.items():
                en_limpo = normalizar_espacos(texto_en)
                v_en = normalizar_espacos(dict_v_texts_en.get(chave, ""))
                v_pt = dict_v_texts_pt.get(chave, "")

                if v_pt and v_en == en_limpo:
                    resultado_texts_pt[chave] = v_pt
                else:
                    hash_c = gerar_hash_conteudo(en_limpo)
                    if hash_c in tm_dict:
                        resultado_texts_pt[chave] = tm_dict[hash_c]
                    else:
                        pendencias_ia_texts.append({"chave": chave, "en": texto_en})

            # 2. Processamento rápido de export_en.xml
            for chave, texto_en in dict_m_export.items():
                en_limpo = normalizar_espacos(texto_en)
                v_en = normalizar_espacos(dict_v_export_en.get(chave, ""))
                v_pt = dict_v_export_pt.get(chave, "")

                if v_pt and v_en == en_limpo:
                    resultado_export_pt[chave] = v_pt
                else:
                    hash_c = gerar_hash_conteudo(en_limpo)
                    if hash_c in tm_dict:
                        resultado_export_pt[chave] = tm_dict[hash_c]
                    else:
                        pendencias_ia_export.append({"chave": chave, "en": texto_en})

            total_pendencias = len(pendencias_ia_texts) + len(pendencias_ia_export)
            with self._lock:
                self.estado_execucao["total_para_ia"] = total_pendencias
                self.estado_execucao["reaproveitados"] = total_itens - total_pendencias
                self._registrar_log_sem_lock("info", f"Isolamento: {total_itens - total_pendencias:,} reaproveitados (0 tokens), {total_pendencias:,} irão para a IA.")
                self.estado_execucao["segmentos_processados"] = total_itens - total_pendencias
                if total_itens > 0:
                    self.estado_execucao["porcentagem"] = round((total_itens - total_pendencias) / total_itens * 100, 1)

            logger.info(f"Isolamento concluído: {total_itens - total_pendencias} reaproveitados (0 tokens), {total_pendencias} para a IA.")

            # 3 e 4. Traduzir pendências de texts e export via IA
            novos_pares_tm: List[Dict[str, str]] = []
            self._traduzir_pendencias(pendencias_ia_texts, resultado_texts_pt, servico_ia, novos_pares_tm, total_itens, total_pendencias)
            self._traduzir_pendencias(pendencias_ia_export, resultado_export_pt, servico_ia, novos_pares_tm, total_itens, total_pendencias)
            # Salvar novos pares na Memória Global
            if novos_pares_tm:
                self.memoria_global.salvar_lote(novos_pares_tm, origem_mod=nome_mod, autor="ia_gemini")

            # 5. Escrever arquivos XML resultantes
            saida_texts = os.path.join(diretorio_saida_ia, "texts_pt-BR.xml")
            saida_export = os.path.join(diretorio_saida_ia, "export_pt-BR.xml")

            self._gravar_arquivo_texts(mod_texts_path, saida_texts, resultado_texts_pt)
            self._gravar_arquivo_export(mod_export_path, saida_export, resultado_export_pt)

            with self._lock:
                self.estado_execucao["ativo"] = False
                self.estado_execucao["concluido"] = True
                self.estado_execucao["porcentagem"] = 100.0
                falhas = self.estado_execucao["falhas_ia"]
                self.estado_execucao["mensagem"] = "Tradução concluída! Arquivos texts_pt-BR.xml e export_pt-BR.xml gerados." + (f" {falhas} frase(s) falharam e permaneceram em inglês." if falhas else "")
                self._registrar_log_sem_lock("ok" if not falhas else "aviso", self.estado_execucao["mensagem"])

        except Exception as erro:
            logger.exception("Falha na tradução em lote por IA:")
            with self._lock:
                self.estado_execucao["ativo"] = False
                self.estado_execucao["concluido"] = False
                self.estado_execucao["erro"] = str(erro)
                self.estado_execucao["mensagem"] = f"Erro: {str(erro)}"
                self._registrar_log_sem_lock("erro", f"Pipeline interrompido: {erro}")

    @staticmethod
    def _gravar_arquivo_texts(caminho_template_en: str, caminho_saida_pt: str, mapa_traducoes: Dict[str, str]) -> None:
        if not os.path.exists(caminho_template_en):
            return

        with open(caminho_template_en, "r", encoding="utf-8") as f_in:
            conteudo_en = f_in.read()

        padrao_token = re.compile(r'(<g\b[^>]*>)|(</g>)|(<t\b([^>]*)>(.*?)</t>)', re.DOTALL)
        partes = []
        ultimo_fim = 0
        pilha_grupos = []

        for coincidencia in padrao_token.finditer(conteudo_en):
            abertura_g, fechamento_g, tag_t, atributos_t, texto_t = coincidencia.groups()
            if abertura_g:
                match_id = re.search(r'\bid="([^"]+)"', abertura_g)
                pilha_grupos.append(match_id.group(1) if match_id else "sem_grupo")
            elif fechamento_g:
                if pilha_grupos:
                    pilha_grupos.pop()
            elif tag_t is not None:
                match_id = re.search(r'\b(?:id|_id)="([^"]+)"', atributos_t)
                id_t = match_id.group(1) if match_id else "sem_id"
                chave = ".".join(pilha_grupos + [id_t])

                ini_texto = coincidencia.start(5)
                fim_texto = coincidencia.end(5)

                partes.append(conteudo_en[ultimo_fim:ini_texto])
                trad = mapa_traducoes.get(chave, texto_t)
                partes.append(sanitizar_para_castledb(trad))
                ultimo_fim = fim_texto

        partes.append(conteudo_en[ultimo_fim:])
        conteudo_pt = "".join(partes)
        conteudo_pt = re.sub(r'lang="[^"]+"', 'lang="pt-BR"', conteudo_pt, count=1)

        with open(caminho_saida_pt, "w", encoding="utf-8") as f_out:
            f_out.write(conteudo_pt)

    @staticmethod
    def _gravar_arquivo_export(caminho_template_en: str, caminho_saida_pt: str, mapa_traducoes: Dict[str, str]) -> None:
        if not os.path.exists(caminho_template_en):
            return

        os.makedirs(os.path.dirname(os.path.abspath(caminho_saida_pt)), exist_ok=True)
        try:
            arvore = ET.parse(caminho_template_en)
            raiz = arvore.getroot()
            raiz.attrib["lang"] = "pt-BR"

            for folha in raiz.findall("sheet"):
                nome_folha = folha.attrib.get("name", "")
                contagem_tags_linha: Dict[str, int] = {}
                for linha in folha:
                    tag_linha = linha.tag
                    contagem_tags_linha[tag_linha] = contagem_tags_linha.get(tag_linha, 0) + 1
                    chave_linha = f"{tag_linha}#{contagem_tags_linha[tag_linha] - 1}" if contagem_tags_linha[tag_linha] > 1 else tag_linha

                    def aplicar_traducao_filhos(elem: ET.Element, caminho_atual: str) -> None:
                        contagem_filhos: Dict[str, int] = {}
                        for filho in elem:
                            tag_f = filho.tag
                            contagem_filhos[tag_f] = contagem_filhos.get(tag_f, 0) + 1
                            idx_f = contagem_filhos[tag_f] - 1
                            chave_f = f"{tag_f}[{idx_f}]" if contagem_filhos[tag_f] > 1 else tag_f
                            sub_c = f"{caminho_atual}/{chave_f}" if caminho_atual else chave_f

                            tem_filhos_estruturais = any(neto.tag not in ("br", "b", "good", "bad", "skill", "gold") for neto in filho)
                            if not tem_filhos_estruturais and (filho.text or len(filho) > 0):
                                loc = f"{nome_folha}/{chave_linha}/{sub_c}"
                                if loc in mapa_traducoes:
                                    texto_traduzido = mapa_traducoes[loc]
                                    texto_limpo = sanitizar_para_castledb(texto_traduzido)
                                    filho.clear()
                                    xml_preparado = re.sub(r'<br(?:\s*)>', '<br/>', texto_limpo, flags=re.IGNORECASE)
                                    xml_preparado = re.sub(r'&(?!(?:amp|lt|gt|quot|apos);)', '&amp;', xml_preparado)
                                    try:
                                        fragmento = ET.fromstring(f"<tmp>{xml_preparado}</tmp>")
                                        filho.text = fragmento.text
                                        for sub_elem in fragmento:
                                            filho.append(sub_elem)
                                    except Exception:
                                        filho.text = texto_limpo
                            else:
                                aplicar_traducao_filhos(filho, sub_c)

                    aplicar_traducao_filhos(linha, "")

            arvore.write(caminho_saida_pt, encoding="utf-8", xml_declaration=True)
        except Exception as erro_xml:
            logger.warning(f"Falha ao gravar export_pt-BR.xml via ElementTree: {erro_xml}. Usando fallback de linhas.")
            with open(caminho_template_en, "r", encoding="utf-8") as f_in:
                linhas = f_in.readlines()

            saida_linhas = []
            for linha in linhas:
                if 'lang="en"' in linha:
                    linha = linha.replace('lang="en"', 'lang="pt-BR"')
                saida_linhas.append(linha)

            with open(caminho_saida_pt, "w", encoding="utf-8") as f_out:
                f_out.writelines(saida_linhas)

