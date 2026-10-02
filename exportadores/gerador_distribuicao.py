"""
Módulo gerador de pacotes de distribuição para o Nexus Mods e instalação na Steam.
Empacota res2.pak modular e gera o arquivo compactado ZIP pronto para publicação.
"""

import os
import shutil
import zipfile
from typing import Any, Dict, Optional
from nucleo.empacotador_pak import EmpacotadorPakHeaps
from exportadores.compilador_xml import CompiladorXml
from nucleo.banco_dados import GerenciadorBancoDados


TEXTO_LEIAME_PADRAO = """========================================================================
WARTALES REMASTERED - TRADUÇÃO PT-BR (PACOTE MODULAR RES2.PAK)
========================================================================

Instalação Simples e Rápida:
1. Certifique-se de que o mod Wartales Remastered já está instalado na pasta do jogo.
2. Copie o arquivo 'res2.pak' desta pasta para o diretório raiz do seu Wartales:
   Exemplo: D:\\SteamLibrary\\steamapps\\common\\Wartales\\
3. Ao iniciar o jogo, selecione o idioma Português (Brasil) nas opções.
4. Bom jogo!

Compatibilidade:
- Formato modular oficial Heaps.io (res2.pak).
- 100% compatível com as atualizações do mod sem sobrescrever arquivos originais.
"""

TEXTO_DESCRICAO_NEXUS = """[b]Tradução Português do Brasil para Wartales Remastered[/b]

Esta tradução foi construída e revisada profissionalmente através do Wartales CAT Studio,
com 100% de cobertura dos textos, consistência terminológica rigorosa e compatibilidade
completa com o motor CastleDB da Shiro Games (zero travamentos e zero asserts).

[b]Como Instalar:[/b]
1. Baixe e extraia o arquivo ZIP.
2. Mova o arquivo [b]res2.pak[/b] diretamente para a pasta principal do seu Wartales na Steam.
3. Inicie o jogo em Português!
"""


class GeradorDistribuicao:
    """Gerador do pacote de distribuição e instalador."""

    def __init__(self, gerenciador_banco: GerenciadorBancoDados):
        self.banco = gerenciador_banco
        self.compilador = CompiladorXml(gerenciador_banco)

    def gerar_pacote_completo(
        self,
        diretorio_mod: str,
        diretorio_saida_compilados: str,
        diretorio_distribuicao: str,
        versao_mod: str = "7.40",
        caminho_steam: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executa o pipeline completo:
        1. Compilação dos XMLs a partir dos dados atuais
        2. Montagem da estrutura de pastas lang/
        3. Empacotamento Heaps.io para res2.pak
        4. Criação do ZIP de distribuição para o Nexus Mods
        5. Cópia opcional para a instalação da Steam
        """
        os.makedirs(diretorio_saida_compilados, exist_ok=True)
        os.makedirs(diretorio_distribuicao, exist_ok=True)

        template_texts_en = os.path.join(diretorio_mod, "texts_en.xml")
        template_export_en = os.path.join(diretorio_mod, "export_en.xml")

        out_texts_pt = os.path.join(diretorio_saida_compilados, "texts_pt-BR.xml")
        out_export_pt = os.path.join(diretorio_saida_compilados, "export_pt-BR.xml")

        # 1. Compilar XMLs
        res_texts = self.compilador.compilar_texts_xml(template_texts_en, out_texts_pt)
        res_export = self.compilador.compilar_export_xml(template_export_en, out_export_pt)

        # 2. Estrutura temporária para o PAK: pasta lang/
        pasta_temp_pak = os.path.join(diretorio_distribuicao, "_temp_pak")
        pasta_lang = os.path.join(pasta_temp_pak, "lang")
        os.makedirs(pasta_lang, exist_ok=True)

        shutil.copy2(out_texts_pt, os.path.join(pasta_lang, "texts_pt-BR.xml"))
        shutil.copy2(out_export_pt, os.path.join(pasta_lang, "export_pt-BR.xml"))

        # 3. Gerar res2.pak
        caminho_res2_pak = os.path.join(diretorio_distribuicao, "res2.pak")
        res_pak = EmpacotadorPakHeaps.empacotar_diretorio(pasta_temp_pak, caminho_res2_pak)

        # 4. Gerar arquivos auxiliares de documentação
        caminho_leiame = os.path.join(diretorio_distribuicao, "LEIAME_INSTALACAO.txt")
        with open(caminho_leiame, "w", encoding="utf-8") as f_leiame:
            f_leiame.write(TEXTO_LEIAME_PADRAO)

        caminho_desc_nexus = os.path.join(diretorio_distribuicao, "DESCRICAO_PAGINA_NEXUS.txt")
        with open(caminho_desc_nexus, "w", encoding="utf-8") as f_nexus:
            f_nexus.write(TEXTO_DESCRICAO_NEXUS)

        # 5. Criar arquivo ZIP para o Nexus Mods
        nome_zip = f"Wartales_Remastered_v{versao_mod}_PTBR_res2.zip"
        caminho_zip = os.path.join(diretorio_distribuicao, nome_zip)
        with zipfile.ZipFile(caminho_zip, "w", zipfile.ZIP_DEFLATED) as arquivo_zip:
            arquivo_zip.write(caminho_res2_pak, arcname="res2.pak")
            arquivo_zip.write(caminho_leiame, arcname="LEIAME_INSTALACAO.txt")

        # 6. Atualização opcional da Steam
        atualizou_steam = False
        if caminho_steam and os.path.exists(caminho_steam):
            try:
                destino_steam = os.path.join(caminho_steam, "res2.pak")
                shutil.copy2(caminho_res2_pak, destino_steam)
                atualizou_steam = True
            except Exception:
                atualizou_steam = False

        # Limpeza da pasta temporária
        try:
            shutil.rmtree(pasta_temp_pak)
        except Exception:
            pass

        # 7. Validação de conformidade CastleDB
        res_conformidade = self.compilador.validar_conformidade(
            caminho_orig_exp=template_export_en,
            caminho_pt_exp=out_export_pt,
            caminho_orig_txt=template_texts_en,
            caminho_pt_txt=out_texts_pt
        )

        return {
            "sucesso": True,
            "caminho_res2_pak": caminho_res2_pak,
            "tamanho_pak_bytes": res_pak["tamanho_bytes"],
            "caminho_zip_nexus": caminho_zip,
            "tamanho_zip_bytes": os.path.getsize(caminho_zip),
            "atualizou_steam": atualizou_steam,
            "conformidade_castledb": res_conformidade,
            "estatisticas_compilacao": {
                "texts": res_texts,
                "export": res_export
            }
        }
