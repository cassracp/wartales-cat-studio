# -*- coding: utf-8 -*-
"""
================================================================================
 Módulo de Memória de Tradução Global Compartilhada (Cross-Mod Deep TM)
================================================================================
 Mantém um repositório central unificado de todas as traduções humanas revisadas
 e aprovadas em qualquer mod de Wartales.

 Isso permite:
 1. Reutilização de 100% de esforço humano prévio em qualquer novo mod ou versão.
 2. Zero gasto de tokens de IA para qualquer frase já traduzida no passado.
 3. No novo mod, os termos herdados chegam como 'pendentes' para revisão e aprovação rápida.
================================================================================
"""

import os
import json
import sqlite3
from typing import Optional, Dict, Any, List
from nucleo.normalizador import normalizar_espacos, gerar_hash_conteudo


class MemoriaTraducaoGlobal:
    """Gerencia o banco central SQLite de memória de tradução cross-mod."""

    def __init__(self, caminho_banco: Optional[str] = None):
        if caminho_banco is None:
            diretorio_base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            caminho_banco = os.path.join(diretorio_base, "dados", "memoria_traducao", "tm_global.db")

        self.caminho_banco = caminho_banco
        os.makedirs(os.path.dirname(os.path.abspath(self.caminho_banco)), exist_ok=True)
        self._inicializar_esquema()

    def _obter_conexao(self) -> sqlite3.Connection:
        conexao = sqlite3.connect(self.caminho_banco)
        conexao.row_factory = sqlite3.Row
        return conexao

    def _inicializar_esquema(self) -> None:
        conexao = self._obter_conexao()
        try:
            with conexao:
                cursor = conexao.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS memoria_global (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        hash_origem TEXT UNIQUE NOT NULL,
                        texto_origem TEXT NOT NULL,
                        texto_traducao TEXT NOT NULL,
                        origem_mod TEXT DEFAULT '',
                        autor TEXT DEFAULT 'humano',
                        data_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_mg_hash ON memoria_global(hash_origem);")
        finally:
            conexao.close()

    def salvar_traducao(
        self,
        texto_origem: str,
        texto_traducao: str,
        origem_mod: str = "",
        autor: str = "humano"
    ) -> bool:
        """Salva ou atualiza um par de tradução na memória global."""
        if not texto_origem or not texto_origem.strip() or not texto_traducao or not texto_traducao.strip():
            return False

        origem_limpa = normalizar_espacos(texto_origem)
        traducao_limpa = normalizar_espacos(texto_traducao)
        hash_c = gerar_hash_conteudo(origem_limpa)

        conexao = self._obter_conexao()
        try:
            with conexao:
                cursor = conexao.cursor()
                cursor.execute("""
                    INSERT INTO memoria_global (hash_origem, texto_origem, texto_traducao, origem_mod, autor, data_atualizacao)
                    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(hash_origem) DO UPDATE SET
                        texto_traducao = excluded.texto_traducao,
                        origem_mod = CASE WHEN excluded.origem_mod != '' THEN excluded.origem_mod ELSE memoria_global.origem_mod END,
                        autor = excluded.autor,
                        data_atualizacao = CURRENT_TIMESTAMP
                """, (hash_c, origem_limpa, traducao_limpa, origem_mod, autor))
                return True
        finally:
            conexao.close()

    def remover_traducao(self, texto_origem: str) -> bool:
        """Remove um par de tradução da memória global se o usuário desfizer a aprovação."""
        if not texto_origem or not texto_origem.strip():
            return False

        hash_c = gerar_hash_conteudo(normalizar_espacos(texto_origem))
        conexao = self._obter_conexao()
        try:
            with conexao:
                cursor = conexao.cursor()
                cursor.execute("DELETE FROM memoria_global WHERE hash_origem = ?", (hash_c,))
                return cursor.rowcount > 0
        finally:
            conexao.close()

    def salvar_lote(self, pares: List[Dict[str, str]], origem_mod: str = "", autor: str = "humano") -> int:
        """Insere ou atualiza múltiplos pares de tradução em uma única transação atômica."""
        if not pares:
            return 0

        registros = []
        for p in pares:
            en = normalizar_espacos(p.get("texto_origem") or p.get("en") or "")
            pt = normalizar_espacos(p.get("texto_traducao") or p.get("pt") or "")
            if en and pt:
                registros.append((
                    gerar_hash_conteudo(en),
                    en,
                    pt,
                    p.get("origem_mod") or origem_mod,
                    autor
                ))

        if not registros:
            return 0

        conexao = self._obter_conexao()
        try:
            with conexao:
                cursor = conexao.cursor()
                cursor.executemany("""
                    INSERT INTO memoria_global (hash_origem, texto_origem, texto_traducao, origem_mod, autor, data_atualizacao)
                    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(hash_origem) DO UPDATE SET
                        texto_traducao = excluded.texto_traducao,
                        origem_mod = CASE WHEN excluded.origem_mod != '' THEN excluded.origem_mod ELSE memoria_global.origem_mod END,
                        autor = excluded.autor,
                        data_atualizacao = CURRENT_TIMESTAMP
                """, registros)
                return len(registros)
        finally:
            conexao.close()

    def buscar_traducao(self, texto_origem: str) -> Optional[str]:
        """Busca tradução existente na memória global usando hash estrito do texto normalizado."""
        if not texto_origem or not texto_origem.strip():
            return None

        hash_c = gerar_hash_conteudo(normalizar_espacos(texto_origem))
        conexao = self._obter_conexao()
        try:
            cursor = conexao.cursor()
            cursor.execute("SELECT texto_traducao FROM memoria_global WHERE hash_origem = ? LIMIT 1", (hash_c,))
            linha = cursor.fetchone()
            if linha:
                return linha["texto_traducao"]
            return None
        finally:
            conexao.close()

    def carregar_dicionario_completo(self) -> Dict[str, str]:
        """Carrega todos os pares em memória como dicionário {hash_origem: texto_traducao} para busca em ultra-alta velocidade."""
        conexao = self._obter_conexao()
        try:
            cursor = conexao.cursor()
            cursor.execute("SELECT hash_origem, texto_traducao FROM memoria_global")
            return {linha["hash_origem"]: linha["texto_traducao"] for linha in cursor.fetchall()}
        finally:
            conexao.close()

    def obter_estatisticas(self) -> Dict[str, Any]:
        """Retorna métricas gerais sobre a memória de tradução acumulada."""
        conexao = self._obter_conexao()
        try:
            cursor = conexao.cursor()
            cursor.execute("SELECT COUNT(*) AS total FROM memoria_global")
            total = cursor.fetchone()["total"]

            cursor.execute("""
                SELECT origem_mod, COUNT(*) as qtd
                FROM memoria_global
                GROUP BY origem_mod
                ORDER BY qtd DESC
            """)
            por_mod = {linha["origem_mod"] or "Geral": linha["qtd"] for linha in cursor.fetchall()}

            return {
                "total_pares": total,
                "por_mod": por_mod
            }
        finally:
            conexao.close()

    def migrar_cache_historico(self, caminho_json: str, origem_mod: str = "cache_historico") -> int:
        """Importa pares de um arquivo JSON legado no formato {'en': 'pt'}."""
        if not os.path.exists(caminho_json):
            return 0

        with open(caminho_json, "r", encoding="utf-8") as f:
            dados = json.load(f)

        pares = []
        if isinstance(dados, dict):
            for en, pt in dados.items():
                if isinstance(pt, str) and pt.strip():
                    pares.append({"en": en, "pt": pt})
        elif isinstance(dados, list):
            pares = dados

        return self.salvar_lote(pares, origem_mod=origem_mod, autor="cache_historico")
