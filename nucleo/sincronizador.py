"""
Módulo sincronizador de importação de arquivos XML de Wartales para o SQLite.
Capaz de ler os dados de referência Vanilla (jogo base), os dados do Mod Remastered
e a tradução vigente, populando a grade comparativa de 4 vias.
"""

import os
import re
import xml.etree.ElementTree as ET
from typing import Any, Callable, Dict, Optional
from nucleo.banco_dados import GerenciadorBancoDados
from nucleo.normalizador import normalizar_espacos, sanitizar_para_castledb
from nucleo.servico_qa import ServicoGarantiaQualidade


class SincronizadorXml:
    """Importador e sincronizador de arquivos de tradução XML."""

    def __init__(self, gerenciador_banco: GerenciadorBancoDados):
        self.banco = gerenciador_banco

    @staticmethod
    def extrair_dicionario_texts(caminho_arquivo: str) -> Dict[str, str]:
        """
        Lê um arquivo texts_*.xml mantendo chaves hierárquicas (grupos e ids de tags <t>).
        Retorna um dicionário {chave_composta: conteudo_interno}.
        """
        if not os.path.exists(caminho_arquivo):
            return {}

        with open(caminho_arquivo, "r", encoding="utf-8") as arquivo:
            conteudo = arquivo.read()

        resultado: Dict[str, str] = {}
        pilha_grupos = []
        padrao_token = re.compile(r'(<g\b[^>]*>)|(</g>)|(<t\b([^>]*)>(.*?)</t>)', re.DOTALL)

        for coincidencia in padrao_token.finditer(conteudo):
            abertura_g, fechamento_g, _, atributos_t, texto_t = coincidencia.groups()
            if abertura_g:
                match_id = re.search(r'\bid="([^"]+)"', abertura_g)
                pilha_grupos.append(match_id.group(1) if match_id else "sem_grupo")
            elif fechamento_g:
                if pilha_grupos:
                    pilha_grupos.pop()
            elif atributos_t is not None:
                match_id = re.search(r'\b(?:id|_id)="([^"]+)"', atributos_t)
                id_t = match_id.group(1) if match_id else "sem_id"
                chave_completa = ".".join(pilha_grupos + [id_t])
                resultado[chave_completa] = texto_t

        return resultado

    @staticmethod
    def extrair_mapa_elementos_export(caminho_arquivo: str) -> Dict[str, str]:
        """
        Lê um arquivo export_*.xml criando chaves únicas para cada elemento com texto:
        Chave: 'sheet_name/chave_linha/subcaminho'
        Valor: string do conteúdo interno (inner text/xml)
        """
        if not os.path.exists(caminho_arquivo):
            return {}

        arvore = ET.parse(caminho_arquivo)
        raiz = arvore.getroot()
        mapa: Dict[str, str] = {}

        for folha in raiz.findall("sheet"):
            nome_folha = folha.attrib.get("name", "")
            contagem_tags_linha: Dict[str, int] = {}
            for linha in folha:
                tag_linha = linha.tag
                contagem_tags_linha[tag_linha] = contagem_tags_linha.get(tag_linha, 0) + 1
                chave_linha = f"{tag_linha}#{contagem_tags_linha[tag_linha] - 1}" if contagem_tags_linha[tag_linha] > 1 else tag_linha

                def percorrer_filhos(elem: ET.Element, caminho_atual: str) -> None:
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
                            inner = (filho.text or "") + "".join(ET.tostring(c, encoding="unicode") for c in filho)
                            mapa[loc] = inner
                        else:
                            percorrer_filhos(filho, sub_c)

                percorrer_filhos(linha, "")

        return mapa

    def importar_projeto_completo(
        self,
        diretorio_vanilla: str,
        diretorio_mod: str,
        progresso_callback: Optional[Callable[[int, int, str], None]] = None,
        limpar_antes: bool = False
    ) -> Dict[str, Any]:
        """
        Importa e correlaciona todos os arquivos do jogo base e do mod.
        Preenche os dados de 4 vias (Vanilla EN, Vanilla PT, Mod EN, Tradução Atual).
        """
        if limpar_antes:
            self.banco.limpar_segmentos()

        # Caminhos dos arquivos Vanilla
        v_texts_en = os.path.join(diretorio_vanilla, "texts_en.xml")
        v_texts_pt = os.path.join(diretorio_vanilla, "texts_pt-BR.xml")
        v_export_en = os.path.join(diretorio_vanilla, "export_en.xml")
        v_export_pt = os.path.join(diretorio_vanilla, "export_pt-BR.xml")

        # Caminhos dos arquivos do Mod
        mod_texts_en = os.path.join(diretorio_mod, "texts_en.xml")
        mod_texts_pt = os.path.join(diretorio_mod, "texts_pt-BR.xml")
        mod_export_en = os.path.join(diretorio_mod, "export_en.xml")
        mod_export_pt = os.path.join(diretorio_mod, "export_pt-BR.xml")

        # Extração de dicionários
        dict_v_texts_en = self.extrair_dicionario_texts(v_texts_en)
        dict_v_texts_pt = self.extrair_dicionario_texts(v_texts_pt)
        dict_m_texts_en = self.extrair_dicionario_texts(mod_texts_en)
        dict_m_texts_pt = self.extrair_dicionario_texts(mod_texts_pt)

        dict_v_export_en = self.extrair_mapa_elementos_export(v_export_en)
        dict_v_export_pt = self.extrair_mapa_elementos_export(v_export_pt)
        dict_m_export_en = self.extrair_mapa_elementos_export(mod_export_en)
        dict_m_export_pt = self.extrair_mapa_elementos_export(mod_export_pt)

        termos_glossario = self.banco.listar_glossario()
        total_importados = 0
        total_inconsistencias = 0

        # 1. Processar texts_*.xml
        total_texts = len(dict_m_texts_en)
        indice = 0
        lote_texts = []
        for chave, texto_en in dict_m_texts_en.items():
            indice += 1
            vanilla_en = dict_v_texts_en.get(chave, "")
            vanilla_pt = dict_v_texts_pt.get(chave, "")
            traducao_atual = dict_m_texts_pt.get(chave, "")

            # Se não tem tradução atual do mod, busca no vanilla ou na memória de tradução
            if not traducao_atual:
                if vanilla_pt and normalizar_espacos(vanilla_en) == normalizar_espacos(texto_en):
                    traducao_atual = vanilla_pt
                else:
                    sugestao_mt = self.banco.buscar_sugestao_memoria(texto_en)
                    traducao_atual = sugestao_mt if sugestao_mt else texto_en

            # Avaliação de QA
            res_qa = ServicoGarantiaQualidade.validar_segmento(texto_en, traducao_atual, termos_glossario)
            tem_inc = 1 if res_qa["tem_inconsistencia"] else 0
            if tem_inc:
                total_inconsistencias += 1

            lote_texts.append({
                "arquivo": "texts_pt-BR.xml",
                "tag_nome": "t",
                "chave_hierarquica": chave,
                "caminho_xml": chave,
                "vanilla_en": vanilla_en,
                "vanilla_pt": vanilla_pt,
                "mod_en": texto_en,
                "traducao_atual": traducao_atual,
                "status": "pendente",
                "aviso_qa": "\n".join(res_qa["avisos"]),
                "tem_inconsistencia": tem_inc
            })
            total_importados += 1

            if len(lote_texts) >= 2000:
                self.banco.salvar_segmentos_em_lote(lote_texts)
                lote_texts.clear()
                if progresso_callback:
                    progresso_callback(indice, total_texts, "Importando texts.xml")

        if lote_texts:
            self.banco.salvar_segmentos_em_lote(lote_texts)
            lote_texts.clear()

        # 2. Processar export_*.xml
        total_export = len(dict_m_export_en)
        indice = 0
        lote_export = []
        for chave, texto_en in dict_m_export_en.items():
            indice += 1
            vanilla_en = dict_v_export_en.get(chave, "")
            vanilla_pt = dict_v_export_pt.get(chave, "")
            traducao_atual = dict_m_export_pt.get(chave, "")

            if not traducao_atual:
                if vanilla_pt and normalizar_espacos(vanilla_en) == normalizar_espacos(texto_en):
                    traducao_atual = vanilla_pt
                else:
                    sugestao_mt = self.banco.buscar_sugestao_memoria(texto_en)
                    traducao_atual = sugestao_mt if sugestao_mt else texto_en

            traducao_atual = sanitizar_para_castledb(traducao_atual)
            res_qa = ServicoGarantiaQualidade.validar_segmento(texto_en, traducao_atual, termos_glossario)
            tem_inc = 1 if res_qa["tem_inconsistencia"] else 0
            if tem_inc:
                total_inconsistencias += 1

            partes_chave = chave.split("/")
            tag_nome = partes_chave[-1] if partes_chave else "item"

            lote_export.append({
                "arquivo": "export_pt-BR.xml",
                "tag_nome": tag_nome,
                "chave_hierarquica": chave,
                "caminho_xml": chave,
                "vanilla_en": vanilla_en,
                "vanilla_pt": vanilla_pt,
                "mod_en": texto_en,
                "traducao_atual": traducao_atual,
                "status": "pendente",
                "aviso_qa": "\n".join(res_qa["avisos"]),
                "tem_inconsistencia": tem_inc
            })
            total_importados += 1

            if len(lote_export) >= 2000:
                self.banco.salvar_segmentos_em_lote(lote_export)
                lote_export.clear()
                if progresso_callback:
                    progresso_callback(indice, total_export, "Importando export.xml")

        if lote_export:
            self.banco.salvar_segmentos_em_lote(lote_export)
            lote_export.clear()

        return {
            "total_importados": total_importados,
            "total_texts": total_texts,
            "total_export": total_export,
            "total_inconsistencias": total_inconsistencias
        }
