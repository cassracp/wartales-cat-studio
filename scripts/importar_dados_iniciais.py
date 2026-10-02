"""
Script utilitário para importar os dados autênticos do Wartales para o projeto CAT Studio.
Copia os arquivos de referência Vanilla (jogo base), os arquivos do Mod Remastered (v7.40)
e a memória de tradução histórica (traducoes_cache.json), em seguida popula o banco SQLite com índice FTS5.
"""

import json
import os
import shutil
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

DIRETORIO_PROJETO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if DIRETORIO_PROJETO not in sys.path:
    sys.path.insert(0, DIRETORIO_PROJETO)

from nucleo.banco_dados import GerenciadorBancoDados
from nucleo.sincronizador import SincronizadorXml
from nucleo.servico_glossario import ServicoGlossario


def importar_dados(diretorio_origem_downloads: str = "") -> None:
    dir_vanilla_destino = os.path.join(DIRETORIO_PROJETO, "dados", "referencia_vanilla")
    dir_mod_destino = os.path.join(DIRETORIO_PROJETO, "dados", "mod_atual")
    dir_mt_destino = os.path.join(DIRETORIO_PROJETO, "dados", "memoria_traducao")
    caminho_banco = os.path.join(DIRETORIO_PROJETO, "dados", "banco", "wartales_cat.db")

    os.makedirs(dir_vanilla_destino, exist_ok=True)
    os.makedirs(dir_mod_destino, exist_ok=True)
    os.makedirs(dir_mt_destino, exist_ok=True)

    print("=" * 65)
    print(" INICIALIZANDO BANCO DE DADOS E DADOS DE REFERENCIA DO WARTALES")
    print("=" * 65)

    # 1. Se fornecido diretório raiz de downloads, copiar arquivos autênticos
    if diretorio_origem_downloads and os.path.exists(diretorio_origem_downloads):
        print(f"\n[1/4] Copiando arquivos autênticos de: {diretorio_origem_downloads}")

        # 1.1 Vanilla
        pasta_vanilla_orig = os.path.join(diretorio_origem_downloads, "referencia_vanilla")
        if os.path.exists(pasta_vanilla_orig):
            for nome_arq in ["export_en.xml", "export_pt-BR.xml", "texts_en.xml", "texts_pt-BR.xml"]:
                orig = os.path.join(pasta_vanilla_orig, nome_arq)
                if os.path.exists(orig):
                    dest = os.path.join(dir_vanilla_destino, nome_arq)
                    shutil.copy2(orig, dest)
                    print(f"  [OK Vanilla] {nome_arq} ({os.path.getsize(dest):,} bytes)")

        # 1.2 Mod 7.40 (EN de extracted_lang, PT de 7.40)
        pasta_740 = os.path.join(diretorio_origem_downloads, "7.40")
        pasta_740_extracted = os.path.join(pasta_740, "extracted_lang")

        if os.path.exists(pasta_740_extracted):
            for nome_arq in ["export_en.xml", "texts_en.xml"]:
                orig = os.path.join(pasta_740_extracted, nome_arq)
                if os.path.exists(orig):
                    dest = os.path.join(dir_mod_destino, nome_arq)
                    shutil.copy2(orig, dest)
                    print(f"  [OK Mod EN] {nome_arq} ({os.path.getsize(dest):,} bytes)")

        if os.path.exists(pasta_740):
            for nome_arq in ["export_pt-BR.xml", "texts_pt-BR.xml"]:
                orig = os.path.join(pasta_740, nome_arq)
                if os.path.exists(orig):
                    dest = os.path.join(dir_mod_destino, nome_arq)
                    shutil.copy2(orig, dest)
                    print(f"  [OK Mod PT] {nome_arq} ({os.path.getsize(dest):,} bytes)")

        # 1.3 Cache de tradução
        cache_orig = os.path.join(diretorio_origem_downloads, "traducoes_cache.json")
        if os.path.exists(cache_orig):
            dest = os.path.join(dir_mt_destino, "traducoes_cache.json")
            shutil.copy2(cache_orig, dest)
            print(f"  [OK Memória TM] traducoes_cache.json ({os.path.getsize(dest):,} bytes)")

    # 2. Inicializar banco e glossário
    print(f"\n[2/4] Inicializando conexão SQLite ({caminho_banco})...")
    banco = GerenciadorBancoDados(caminho_banco)
    glossario = ServicoGlossario(banco)
    inseridos_glossario = glossario.inicializar_glossario_padrao()
    print(f"  [OK] Glossário base populado com {inseridos_glossario} termos padrão.")

    # 3. Carregar Memória de Tradução
    caminho_cache_local = os.path.join(dir_mt_destino, "traducoes_cache.json")
    if os.path.exists(caminho_cache_local):
        print(f"\n[3/4] Carregando Memória de Tradução (Deep TM)...")
        with open(caminho_cache_local, "r", encoding="utf-8") as f_cache:
            dados_cache = json.load(f_cache)
        total_mt = banco.carregar_memoria_traducao_lote(dados_cache, origem="cache_historico")
        print(f"  [OK] {total_mt:,} pares carregados na Memória de Tradução.")
    else:
        print("\n[3/4] Memória de tradução em cache não encontrada, prosseguindo...")

    # 4. Sincronizar XMLs no banco com limpeza prévia
    print(f"\n[4/4] Sincronizando segmentos XML com o SQLite e índice FTS5...")
    sincronizador = SincronizadorXml(banco)
    res = sincronizador.importar_projeto_completo(dir_vanilla_destino, dir_mod_destino, limpar_antes=True)

    print(f"  [OK] Importação concluída com sucesso:")
    print(f"    - Total de nós importados: {res['total_importados']:,}")
    print(f"    - Nós de texts.xml: {res['total_texts']:,}")
    print(f"    - Nós de export.xml: {res['total_export']:,}")
    print(f"    - Alertas de QA / Inconsistências: {res['total_inconsistencias']:,}")

    stats = banco.obter_estatisticas()
    print(f"\n[ESTATÍSTICAS ATUAIS]")
    print(f"  - Total Segmentos: {stats.get('total_segmentos', 0):,}")
    print(f"  - Revisados: {stats.get('revisados', 0):,}")
    print(f"  - Pendentes: {stats.get('pendentes', 0):,}")
    print(f"  - Inconsistências: {stats.get('inconsistencias', 0):,}")
    print(f"  - Termos Glossário: {stats.get('total_termos_glossario', 0):,}")
    print(f"  - Memória de Tradução (TM): {stats.get('total_memoria_traducao', 0):,}")
    print("\n[CONCLUÍDO] Wartales CAT Studio configurado e pronto para uso!")


if __name__ == "__main__":
    dir_downloads_padrao = r"c:\Users\cassr\Downloads\Wartales Remastered Translation"
    importar_dados(dir_downloads_padrao)
