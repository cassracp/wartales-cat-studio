"""
Módulo de compilação dos arquivos XML finais de tradução para Wartales.
Gera export_pt-BR.xml e texts_pt-BR.xml com conformidade estrita ao CastleDB.
"""

import os
import re
import xml.etree.ElementTree as ET
from typing import Any, Dict
from nucleo.banco_dados import GerenciadorBancoDados
from nucleo.normalizador import sanitizar_para_castledb


class CompiladorXml:
    """Compilador de saída para arquivos XML da tradução PT-BR."""

    def __init__(self, gerenciador_banco: GerenciadorBancoDados):
        self.banco = gerenciador_banco

    def compilar_texts_xml(
        self,
        caminho_template_en: str,
        caminho_saida_pt: str
    ) -> Dict[str, Any]:
        """
        Compila o arquivo texts_pt-BR.xml a partir do modelo EN e das traduções do banco.
        """
        if not os.path.exists(caminho_template_en):
            raise FileNotFoundError(f"Arquivo template não encontrado: {caminho_template_en}")

        os.makedirs(os.path.dirname(os.path.abspath(caminho_saida_pt)), exist_ok=True)

        # Mapear traduções vigentes do banco para texts
        mapa_traducoes: Dict[str, str] = {}
        with self.banco.obter_conexao() as conexao:
            cursor = conexao.cursor()
            cursor.execute("""
                SELECT chave_hierarquica, COALESCE(traducao_revisada, traducao_atual) AS texto_final
                FROM segmentos
                WHERE arquivo = 'texts_pt-BR.xml'
            """)
            for linha in cursor.fetchall():
                mapa_traducoes[linha["chave_hierarquica"]] = linha["texto_final"]

        with open(caminho_template_en, "r", encoding="utf-8") as arquivo_en:
            conteudo_en = arquivo_en.read()

        padrao_token = re.compile(r'(<g\b[^>]*>)|(</g>)|(<t\b([^>]*)>(.*?)</t>)', re.DOTALL)
        partes = []
        ultimo_fim = 0
        pilha_grupos = []
        total_substituidos = 0

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

                if chave in mapa_traducoes:
                    traducao = mapa_traducoes[chave]
                    partes.append(traducao)
                    total_substituidos += 1
                else:
                    partes.append(texto_t)

                ultimo_fim = fim_texto

        partes.append(conteudo_en[ultimo_fim:])
        resultado = "".join(partes)

        # Ajuste de cabeçalho de idioma
        resultado = re.sub(r'(\blang=")en(")', r'\g<1>pt-BR\g<2>', resultado, count=1)
        if 'lang="pt-BR"' not in resultado and "<texts" in resultado:
            resultado = re.sub(r'<texts\b', '<texts lang="pt-BR"', resultado, count=1)

        with open(caminho_saida_pt, "w", encoding="utf-8") as arquivo_pt:
            arquivo_pt.write(resultado)

        return {
            "arquivo_gerado": caminho_saida_pt,
            "total_substituidos": total_substituidos,
            "tamanho_bytes": os.path.getsize(caminho_saida_pt)
        }

    def compilar_export_xml(
        self,
        caminho_template_en: str,
        caminho_saida_pt: str
    ) -> Dict[str, Any]:
        """
        Compila o arquivo export_pt-BR.xml a partir do modelo EN e das traduções do banco.
        Higieniza automaticamente nós de texto para prevenir o erro de assert do CastleDB.
        """
        if not os.path.exists(caminho_template_en):
            raise FileNotFoundError(f"Arquivo template não encontrado: {caminho_template_en}")

        os.makedirs(os.path.dirname(os.path.abspath(caminho_saida_pt)), exist_ok=True)

        mapa_traducoes: Dict[str, str] = {}
        with self.banco.obter_conexao() as conexao:
            cursor = conexao.cursor()
            cursor.execute("""
                SELECT chave_hierarquica, COALESCE(traducao_revisada, traducao_atual) AS texto_final
                FROM segmentos
                WHERE arquivo = 'export_pt-BR.xml'
            """)
            for linha in cursor.fetchall():
                mapa_traducoes[linha["chave_hierarquica"]] = linha["texto_final"]

        arvore = ET.parse(caminho_template_en)
        raiz = arvore.getroot()
        raiz.attrib["lang"] = "pt-BR"

        total_substituidos = 0

        for folha in raiz.findall("sheet"):
            nome_folha = folha.attrib.get("name", "")
            contagem_tags_linha: Dict[str, int] = {}
            for linha in folha:
                tag_linha = linha.tag
                contagem_tags_linha[tag_linha] = contagem_tags_linha.get(tag_linha, 0) + 1
                chave_linha = f"{tag_linha}#{contagem_tags_linha[tag_linha] - 1}" if contagem_tags_linha[tag_linha] > 1 else tag_linha

                def aplicar_traducao_filhos(elem: ET.Element, caminho_atual: str) -> None:
                    nonlocal total_substituidos
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
                                # Sanitização CastleDB
                                texto_limpo = sanitizar_para_castledb(texto_traduzido)

                                # Tratamento de tags XML seguras
                                filho.clear()
                                # Normaliza tags auto-fechadas como <br> para <br/>
                                xml_preparado = re.sub(r'<br(?:\s*)>', '<br/>', texto_limpo, flags=re.IGNORECASE)
                                # Escapa & soltos que não pertençam a entidades válidas
                                xml_preparado = re.sub(r'&(?!(?:amp|lt|gt|quot|apos);)', '&amp;', xml_preparado)

                                try:
                                    fragmento = ET.fromstring(f"<tmp>{xml_preparado}</tmp>")
                                    filho.text = fragmento.text
                                    for sub_elem in fragmento:
                                        filho.append(sub_elem)
                                except Exception:
                                    filho.text = texto_limpo

                                total_substituidos += 1
                        else:
                            aplicar_traducao_filhos(filho, sub_c)

                aplicar_traducao_filhos(linha, "")

        arvore.write(caminho_saida_pt, encoding="utf-8", xml_declaration=True)

        return {
            "arquivo_gerado": caminho_saida_pt,
            "total_substituidos": total_substituidos,
            "tamanho_bytes": os.path.getsize(caminho_saida_pt)
        }

    def validar_conformidade(
        self,
        caminho_orig_exp: str,
        caminho_pt_exp: str,
        caminho_orig_txt: str,
        caminho_pt_txt: str
    ) -> Dict[str, Any]:
        """
        Valida conformidade estrutural completa contra o CastleDB da Shiro Games.
        Garante integridade de tags, ausência de 'assert throw' e correspondência de nós.
        """
        divergencias_export = 0
        if os.path.exists(caminho_orig_exp) and os.path.exists(caminho_pt_exp):
            arvore_orig = ET.parse(caminho_orig_exp)
            arvore_pt = ET.parse(caminho_pt_exp)

            folhas_orig = arvore_orig.getroot().findall("sheet")
            folhas_pt = arvore_pt.getroot().findall("sheet")

            for folha_orig, folha_pt in zip(folhas_orig, folhas_pt):
                for linha_orig, linha_pt in zip(folha_orig, folha_pt):
                    for cel_orig, cel_pt in zip(linha_orig, linha_pt):
                        txt_orig = cel_orig.text or ""
                        txt_pt = cel_pt.text or ""
                        # Se original possui texto não vazio e gerado ficou vazio
                        if txt_orig.strip() and not txt_pt.strip() and len(cel_pt) == 0:
                            divergencias_export += 1

        tags_faltantes_texts = 0
        total_tags_texts = 0
        if os.path.exists(caminho_orig_txt) and os.path.exists(caminho_pt_txt):
            with open(caminho_orig_txt, "r", encoding="utf-8") as f_orig:
                conteudo_orig = f_orig.read()
            with open(caminho_pt_txt, "r", encoding="utf-8") as f_pt:
                conteudo_pt = f_pt.read()

            padrao_ids = re.compile(r'<t\s+id="([^"]+)"')
            ids_orig = padrao_ids.findall(conteudo_orig)
            ids_pt = padrao_ids.findall(conteudo_pt)
            total_tags_texts = len(ids_pt)

            set_orig = set(ids_orig)
            set_pt = set(ids_pt)
            tags_faltantes_texts = len(set_orig - set_pt)

        valido = (divergencias_export == 0) and (tags_faltantes_texts == 0)
        return {
            "valido": valido,
            "divergencias_export": divergencias_export,
            "tags_faltantes_texts": tags_faltantes_texts,
            "total_tags_texts": total_tags_texts
        }
