"""
Módulo de persistência e gerenciamento do banco de dados SQLite com suporte a FTS5.
Implementa o padrão Repository para acesso desacoplado a dados de tradução e glossário.
"""

import os
import sqlite3
from contextlib import contextmanager
from typing import Any, Dict, Generator, List, Optional, Tuple
from nucleo.normalizador import gerar_hash_conteudo, normalizar_espacos


class GerenciadorBancoDados:
    """Gerenciador central de conexões e operações no SQLite."""

    def __init__(self, caminho_banco: str):
        self.caminho_banco = os.path.abspath(caminho_banco)
        pasta_banco = os.path.dirname(self.caminho_banco)
        if pasta_banco:
            os.makedirs(pasta_banco, exist_ok=True)
        self.inicializar_banco()

    @contextmanager
    def obter_conexao(self) -> Generator[sqlite3.Connection, None, None]:
        """Abre uma conexão configurada com WAL e garante fechamento seguro."""
        conexao = sqlite3.connect(self.caminho_banco, timeout=30.0)
        conexao.row_factory = sqlite3.Row
        conexao.execute("PRAGMA journal_mode = WAL;")
        conexao.execute("PRAGMA synchronous = NORMAL;")
        conexao.execute("PRAGMA foreign_keys = ON;")
        try:
            yield conexao
        finally:
            conexao.close()

    def inicializar_banco(self) -> None:
        """Cria as tabelas relacionais, índices e tabelas virtuais FTS5."""
        with self.obter_conexao() as conexao:
            cursor = conexao.cursor()

            # 1. Tabela principal de segmentos
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS segmentos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    arquivo TEXT NOT NULL,
                    tag_nome TEXT NOT NULL,
                    chave_hierarquica TEXT NOT NULL,
                    caminho_xml TEXT NOT NULL,
                    vanilla_en TEXT,
                    vanilla_pt TEXT,
                    mod_en TEXT NOT NULL,
                    traducao_atual TEXT NOT NULL,
                    traducao_revisada TEXT,
                    status TEXT DEFAULT 'pendente',
                    hash_conteudo TEXT NOT NULL,
                    tem_inconsistencia INTEGER DEFAULT 0,
                    aviso_qa TEXT DEFAULT '',
                    data_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(arquivo, chave_hierarquica, tag_nome)
                );
            """)

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_seg_arquivo ON segmentos(arquivo);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_seg_status ON segmentos(status);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_seg_hash ON segmentos(hash_conteudo);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_seg_chave ON segmentos(chave_hierarquica);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_seg_inconsistencia ON segmentos(tem_inconsistencia);")
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_seg_unique ON segmentos(arquivo, chave_hierarquica, tag_nome);")

            # 2. Tabela de termos do glossário / termbase
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS termos_glossario (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    termo_en TEXT UNIQUE NOT NULL,
                    termo_pt_padrao TEXT NOT NULL,
                    sinonimos_proibidos TEXT DEFAULT '',
                    categoria TEXT DEFAULT 'Geral',
                    notas TEXT DEFAULT '',
                    data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 2.1. Tabela de Memória de Tradução (Deep TM / cache histórico)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS memoria_traducao (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    texto_origem TEXT UNIQUE NOT NULL,
                    texto_traducao TEXT NOT NULL,
                    origem TEXT DEFAULT 'cache',
                    data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_mt_origem ON memoria_traducao(texto_origem);")

            # 3. Tabela virtual FTS5 para busca textual instantânea (<10ms)
            cursor.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS segmentos_fts USING fts5(
                    id UNINDEXED,
                    vanilla_en,
                    vanilla_pt,
                    mod_en,
                    traducao_atual,
                    traducao_revisada,
                    chave_hierarquica,
                    content='segmentos',
                    content_rowid='id'
                );
            """)

            # 4. Triggers para sincronização automática entre tabela relacional e FTS5
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS trg_segmentos_insert AFTER INSERT ON segmentos BEGIN
                    INSERT INTO segmentos_fts(rowid, id, vanilla_en, vanilla_pt, mod_en, traducao_atual, traducao_revisada, chave_hierarquica)
                    VALUES (new.id, new.id, new.vanilla_en, new.vanilla_pt, new.mod_en, new.traducao_atual, new.traducao_revisada, new.chave_hierarquica);
                END;
            """)

            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS trg_segmentos_delete AFTER DELETE ON segmentos BEGIN
                    INSERT INTO segmentos_fts(segmentos_fts, rowid, id, vanilla_en, vanilla_pt, mod_en, traducao_atual, traducao_revisada, chave_hierarquica)
                    VALUES ('delete', old.id, old.id, old.vanilla_en, old.vanilla_pt, old.mod_en, old.traducao_atual, old.traducao_revisada, old.chave_hierarquica);
                END;
            """)

            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS trg_segmentos_update AFTER UPDATE ON segmentos BEGIN
                    INSERT INTO segmentos_fts(segmentos_fts, rowid, id, vanilla_en, vanilla_pt, mod_en, traducao_atual, traducao_revisada, chave_hierarquica)
                    VALUES ('delete', old.id, old.id, old.vanilla_en, old.vanilla_pt, old.mod_en, old.traducao_atual, old.traducao_revisada, old.chave_hierarquica);
                    INSERT INTO segmentos_fts(rowid, id, vanilla_en, vanilla_pt, mod_en, traducao_atual, traducao_revisada, chave_hierarquica)
                    VALUES (new.id, new.id, new.vanilla_en, new.vanilla_pt, new.mod_en, new.traducao_atual, new.traducao_revisada, new.chave_hierarquica);
                END;
            """)

            conexao.commit()

    def salvar_segmento(
        self,
        arquivo: str,
        tag_nome: str,
        chave_hierarquica: str,
        caminho_xml: str,
        vanilla_en: Optional[str],
        vanilla_pt: Optional[str],
        mod_en: str,
        traducao_atual: str,
        traducao_revisada: Optional[str] = None,
        status: str = "pendente",
        aviso_qa: str = "",
        tem_inconsistencia: int = 0
    ) -> int:
        """Salva ou atualiza um segmento de texto com cálculo de hash de conteúdo."""
        hash_conteudo = gerar_hash_conteudo(mod_en)
        with self.obter_conexao() as conexao:
            cursor = conexao.cursor()
            cursor.execute("""
                SELECT id FROM segmentos
                WHERE arquivo = ? AND chave_hierarquica = ? AND tag_nome = ?
            """, (arquivo, chave_hierarquica, tag_nome))
            registro = cursor.fetchone()

            if registro:
                segmento_id = registro["id"]
                cursor.execute("""
                    UPDATE segmentos SET
                        caminho_xml = ?,
                        vanilla_en = ?,
                        vanilla_pt = ?,
                        mod_en = ?,
                        traducao_atual = ?,
                        traducao_revisada = COALESCE(?, traducao_revisada),
                        status = ?,
                        hash_conteudo = ?,
                        tem_inconsistencia = ?,
                        aviso_qa = ?,
                        data_atualizacao = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (
                    caminho_xml, vanilla_en, vanilla_pt, mod_en, traducao_atual,
                    traducao_revisada, status, hash_conteudo, tem_inconsistencia,
                    aviso_qa, segmento_id
                ))
            else:
                cursor.execute("""
                    INSERT INTO segmentos (
                        arquivo, tag_nome, chave_hierarquica, caminho_xml,
                        vanilla_en, vanilla_pt, mod_en, traducao_atual,
                        traducao_revisada, status, hash_conteudo,
                        tem_inconsistencia, aviso_qa
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    arquivo, tag_nome, chave_hierarquica, caminho_xml,
                    vanilla_en, vanilla_pt, mod_en, traducao_atual,
                    traducao_revisada, status, hash_conteudo,
                    tem_inconsistencia, aviso_qa
                ))
                segmento_id = cursor.lastrowid

            conexao.commit()
            if segmento_id is None:
                raise RuntimeError("Não foi possível obter o ID do segmento salvo.")
            return segmento_id

    def limpar_segmentos(self, arquivo: Optional[str] = None) -> int:
        """Limpa os segmentos de um arquivo específico ou de todo o banco."""
        with self.obter_conexao() as conexao:
            cursor = conexao.cursor()
            if arquivo:
                cursor.execute("DELETE FROM segmentos WHERE arquivo = ?", (arquivo,))
            else:
                cursor.execute("DELETE FROM segmentos")
            removidos = cursor.rowcount if cursor.rowcount is not None and cursor.rowcount >= 0 else 0
            if not arquivo:
                try:
                    cursor.execute("INSERT INTO segmentos_fts(segmentos_fts) VALUES('delete-all')")
                except Exception:
                    try:
                        cursor.execute("DELETE FROM segmentos_fts")
                    except Exception:
                        pass
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_seg_unique ON segmentos(arquivo, chave_hierarquica, tag_nome);")
            conexao.commit()
            return removidos

    def salvar_segmentos_em_lote(self, lista_segmentos: List[Dict[str, Any]]) -> int:
        """
        Insere ou atualiza uma lista de segmentos em lote dentro de uma transação única.
        Preserva traduções previamente revisadas pelo usuário em caso de reimportação.
        """
        if not lista_segmentos:
            return 0
        with self.obter_conexao() as conexao:
            cursor = conexao.cursor()
            for seg in lista_segmentos:
                hash_conteudo = gerar_hash_conteudo(seg["mod_en"])
                cursor.execute("""
                    INSERT INTO segmentos (
                        arquivo, tag_nome, chave_hierarquica, caminho_xml,
                        vanilla_en, vanilla_pt, mod_en, traducao_atual,
                        traducao_revisada, status, hash_conteudo,
                        tem_inconsistencia, aviso_qa
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(arquivo, chave_hierarquica, tag_nome) DO UPDATE SET
                        caminho_xml = excluded.caminho_xml,
                        vanilla_en = excluded.vanilla_en,
                        vanilla_pt = excluded.vanilla_pt,
                        mod_en = excluded.mod_en,
                        traducao_atual = excluded.traducao_atual,
                        traducao_revisada = COALESCE(segmentos.traducao_revisada, excluded.traducao_revisada),
                        status = CASE WHEN segmentos.status = 'revisado' THEN 'revisado' ELSE excluded.status END,
                        hash_conteudo = excluded.hash_conteudo,
                        tem_inconsistencia = excluded.tem_inconsistencia,
                        aviso_qa = excluded.aviso_qa,
                        data_atualizacao = CURRENT_TIMESTAMP
                """, (
                    seg["arquivo"],
                    seg["tag_nome"],
                    seg["chave_hierarquica"],
                    seg["caminho_xml"],
                    seg.get("vanilla_en"),
                    seg.get("vanilla_pt"),
                    seg["mod_en"],
                    seg["traducao_atual"],
                    seg.get("traducao_revisada"),
                    seg.get("status", "pendente"),
                    hash_conteudo,
                    seg.get("tem_inconsistencia", 0),
                    seg.get("aviso_qa", "")
                ))
            conexao.commit()
            return len(lista_segmentos)

    def carregar_memoria_traducao_lote(self, dicionario_tm: Dict[str, str], origem: str = "cache") -> int:
        """Importa pares de tradução para a tabela de memória de tradução."""
        if not dicionario_tm:
            return 0
        with self.obter_conexao() as conexao:
            cursor = conexao.cursor()
            itens = [(origem_txt, trad, origem) for origem_txt, trad in dicionario_tm.items() if origem_txt and trad]
            cursor.executemany("""
                INSERT INTO memoria_traducao (texto_origem, texto_traducao, origem)
                VALUES (?, ?, ?)
                ON CONFLICT(texto_origem) DO UPDATE SET
                    texto_traducao = excluded.texto_traducao,
                    origem = excluded.origem
            """, itens)
            conexao.commit()
            return len(itens)

    def buscar_sugestao_memoria(self, texto_origem: str) -> Optional[str]:
        """Busca correspondência exata na memória de tradução."""
        texto_limpo = normalizar_espacos(texto_origem)
        with self.obter_conexao() as conexao:
            cursor = conexao.cursor()
            cursor.execute("SELECT texto_traducao FROM memoria_traducao WHERE texto_origem = ?", (texto_limpo,))
            linha = cursor.fetchone()
            return linha["texto_traducao"] if linha else None

    def obter_segmento_por_id(self, segmento_id: int) -> Optional[Dict[str, Any]]:
        """Retorna todos os detalhes de um segmento específico."""
        with self.obter_conexao() as conexao:
            cursor = conexao.cursor()
            cursor.execute("""
                SELECT s.*,
                    CASE
                        WHEN s.vanilla_en IS NULL OR s.vanilla_en = '' THEN 'novo'
                        WHEN s.mod_en != s.vanilla_en THEN 'modificado'
                        ELSE 'vanilla'
                    END AS tipo_delta
                FROM segmentos s
                WHERE s.id = ?
            """, (segmento_id,))
            registro = cursor.fetchone()
            if registro:
                return dict(registro)
            return None

    def obter_primeiro_segmento_id(
        self,
        filtro_status: str = "",
        filtro_origem: str = "",
        filtro_arquivo: str = "",
        filtro_categoria: str = "",
        apenas_inconsistencias: bool = False,
        apenas_sem_ia: bool = False,
        termo_busca: str = ""
    ) -> Optional[int]:
        """Retorna o ID do primeiro segmento que corresponde aos filtros ativos, ou o menor ID geral."""
        where_sql, parametros = self._montar_clausulas_filtro(
            filtro_status=filtro_status,
            filtro_origem=filtro_origem,
            filtro_arquivo=filtro_arquivo,
            filtro_categoria=filtro_categoria,
            apenas_inconsistencias=apenas_inconsistencias,
            apenas_sem_ia=apenas_sem_ia,
            termo_busca=termo_busca
        )
        with self.obter_conexao() as conexao:
            cursor = conexao.cursor()
            cursor.execute(f"SELECT s.id FROM segmentos s {where_sql} ORDER BY s.id ASC LIMIT 1", parametros)
            linha = cursor.fetchone()
            if linha:
                return linha["id"]
            return None

    def atualizar_traducao_segmento(
        self,
        segmento_id: int,
        traducao_revisada: str,
        status: str = "revisado",
        aviso_qa: str = "",
        tem_inconsistencia: int = 0
    ) -> bool:
        """Atualiza a tradução revisada e status de um segmento."""
        with self.obter_conexao() as conexao:
            cursor = conexao.cursor()
            cursor.execute("""
                UPDATE segmentos SET
                    traducao_revisada = ?,
                    status = ?,
                    aviso_qa = ?,
                    tem_inconsistencia = ?,
                    data_atualizacao = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (traducao_revisada, status, aviso_qa, tem_inconsistencia, segmento_id))
            conexao.commit()
            return cursor.rowcount > 0

    def obter_repeticoes(self, hash_conteudo: str, excluir_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Retorna todos os segmentos que possuem o mesmo hash de conteúdo."""
        with self.obter_conexao() as conexao:
            cursor = conexao.cursor()
            if excluir_id is not None:
                cursor.execute("""
                    SELECT id, arquivo, chave_hierarquica, mod_en, traducao_atual, traducao_revisada, status
                    FROM segmentos
                    WHERE hash_conteudo = ? AND id != ?
                """, (hash_conteudo, excluir_id))
            else:
                cursor.execute("""
                    SELECT id, arquivo, chave_hierarquica, mod_en, traducao_atual, traducao_revisada, status
                    FROM segmentos
                    WHERE hash_conteudo = ?
                """, (hash_conteudo,))
            return [dict(linha) for linha in cursor.fetchall()]

    def propagar_traducao_por_hash(
        self,
        hash_conteudo: str,
        nova_traducao: str,
        status: str = "revisado"
    ) -> int:
        """Propaga a nova tradução atomicamente para todos os segmentos com o mesmo hash."""
        with self.obter_conexao() as conexao:
            cursor = conexao.cursor()
            cursor.execute("""
                UPDATE segmentos SET
                    traducao_revisada = ?,
                    status = ?,
                    data_atualizacao = CURRENT_TIMESTAMP
                WHERE hash_conteudo = ?
            """, (nova_traducao, status, hash_conteudo))
            conexao.commit()
            return cursor.rowcount

    def _montar_clausulas_filtro(
        self,
        filtro_status: str = "",
        filtro_origem: str = "",
        filtro_arquivo: str = "",
        filtro_categoria: str = "",
        apenas_inconsistencias: bool = False,
        apenas_sem_ia: bool = False,
        termo_busca: str = ""
    ) -> Tuple[str, List[Any]]:
        """
        Constrói dinamicamente cláusulas WHERE e parâmetros SQL para filtros combinados.
        Suporta filtros compostos (Origem do Mod + Status de Revisão + IA + QA)
        e presets consolidados com total compatibilidade retroativa.
        """
        clausulas = []
        parametros: List[Any] = []

        status_norm = (filtro_status or "").strip().lower()
        origem_norm = (filtro_origem or "").strip().lower()

        # Resolução de presets consolidados passados em filtro_status (se filtro_origem não foi fornecido)
        if status_norm in ("mod_pendentes", "apenas_mod_pendentes"):
            if not origem_norm:
                origem_norm = "apenas_mod"
            status_norm = "pendente"
        elif status_norm in ("mod_novos_pendentes", "novos_pendentes"):
            if not origem_norm:
                origem_norm = "novos"
            status_norm = "pendente"
        elif status_norm in ("mod_modificados_pendentes", "modificados_pendentes"):
            if not origem_norm:
                origem_norm = "modificados"
            status_norm = "pendente"
        elif status_norm in ("mod_todos", "apenas_mod", "mod"):
            if not origem_norm:
                origem_norm = "apenas_mod"
            status_norm = ""
        elif status_norm == "modificados":
            if not origem_norm:
                origem_norm = "modificados"
            status_norm = ""
        elif status_norm == "novos":
            if not origem_norm:
                origem_norm = "novos"
            status_norm = ""
        elif status_norm == "sem_ia":
            apenas_sem_ia = True
            status_norm = ""
        elif status_norm in ("inconsistencias", "inconsistencia"):
            apenas_inconsistencias = True
            status_norm = ""

        # 1. Filtro de Origem / Escopo do Mod (Deltas)
        if origem_norm in ("apenas_mod", "mod"):
            # Frases novas OU modificadas pelo Mod
            clausulas.append("((s.vanilla_en IS NULL OR s.vanilla_en = '') OR (s.vanilla_en IS NOT NULL AND s.mod_en != s.vanilla_en))")
        elif origem_norm == "novos":
            # Apenas frases novas / inexistentes no vanilla
            clausulas.append("(s.vanilla_en IS NULL OR s.vanilla_en = '')")
        elif origem_norm == "modificados":
            # Apenas frases que existiam no vanilla mas foram alteradas pelo mod
            clausulas.append("(s.vanilla_en IS NOT NULL AND s.vanilla_en != '' AND s.mod_en != s.vanilla_en)")
        elif origem_norm in ("vanilla", "identicos_vanilla", "inalterados"):
            # Frases que são idênticas ao vanilla oficial
            clausulas.append("(s.vanilla_en IS NOT NULL AND s.mod_en = s.vanilla_en)")

        # 2. Filtro de Status de Aprovação / Revisão
        if status_norm in ("pendente", "pendentes"):
            clausulas.append("s.status = 'pendente'")
        elif status_norm in ("revisado", "revisados", "aprovado", "aprovados"):
            clausulas.append("s.status = 'revisado'")
        elif status_norm and status_norm != "todos":
            clausulas.append("s.status = ?")
            parametros.append(status_norm)

        # 3. Filtro de IA / Sem Tradução
        if apenas_sem_ia:
            clausulas.append("((s.traducao_revisada IS NULL OR s.traducao_revisada = '') AND (s.traducao_atual IS NULL OR s.traducao_atual = '' OR s.traducao_atual = s.mod_en))")

        # 4. Filtro de Arquivo
        if filtro_arquivo:
            clausulas.append("s.arquivo = ?")
            parametros.append(filtro_arquivo)

        # 5. Filtro de Categoria
        if filtro_categoria:
            clausulas.append("(s.chave_hierarquica LIKE ? OR s.chave_hierarquica LIKE ? OR s.chave_hierarquica LIKE ? OR s.chave_hierarquica = ?)")
            parametros.extend([f"{filtro_categoria}/%", f"{filtro_categoria}.%", f"{filtro_categoria}_%", filtro_categoria])

        # 6. Filtro de Inconsistências / QA
        if apenas_inconsistencias:
            clausulas.append("s.tem_inconsistencia = 1")

        # 7. Busca Textual FTS5
        termo_limpo = termo_busca.strip()
        if termo_limpo:
            tokens = []
            for token in termo_limpo.split():
                token_sanitizado = token.replace('"', '').strip()
                if token_sanitizado:
                    tokens.append(f'"{token_sanitizado}"*')
            if tokens:
                consulta_fts = " ".join(tokens)
                clausulas.append("s.id IN (SELECT id FROM segmentos_fts WHERE segmentos_fts MATCH ?)")
                parametros.append(consulta_fts)

        where_sql = ("WHERE " + " AND ".join(clausulas)) if clausulas else ""
        return where_sql, parametros

    def buscar_segmentos(
        self,
        termo_busca: str = "",
        filtro_status: str = "",
        filtro_origem: str = "",
        filtro_arquivo: str = "",
        filtro_categoria: str = "",
        apenas_inconsistencias: bool = False,
        apenas_sem_ia: bool = False,
        pagina: int = 1,
        itens_por_pagina: int = 50
    ) -> Dict[str, Any]:
        """
        Executa busca paginada com suporte a FTS5 e múltiplos filtros combinados.
        """
        offset = (pagina - 1) * itens_por_pagina
        where_sql, parametros = self._montar_clausulas_filtro(
            filtro_status=filtro_status,
            filtro_origem=filtro_origem,
            filtro_arquivo=filtro_arquivo,
            filtro_categoria=filtro_categoria,
            apenas_inconsistencias=apenas_inconsistencias,
            apenas_sem_ia=apenas_sem_ia,
            termo_busca=termo_busca
        )
        with self.obter_conexao() as conexao:
            cursor = conexao.cursor()

            # Contagem total
            cursor.execute(f"SELECT COUNT(*) AS total FROM segmentos s {where_sql}", parametros)
            total_itens = cursor.fetchone()["total"]

            # Busca dos registros paginados
            consulta_final = f"""
                SELECT s.*,
                    CASE
                        WHEN s.vanilla_en IS NULL OR s.vanilla_en = '' THEN 'novo'
                        WHEN s.mod_en != s.vanilla_en THEN 'modificado'
                        ELSE 'vanilla'
                    END AS tipo_delta
                FROM segmentos s
                {where_sql}
                ORDER BY s.id ASC
                LIMIT ? OFFSET ?
            """
            cursor.execute(consulta_final, parametros + [itens_por_pagina, offset])
            registros = [dict(linha) for linha in cursor.fetchall()]

            total_paginas = (total_itens + itens_por_pagina - 1) // itens_por_pagina if total_itens > 0 else 1

            return {
                "itens": registros,
                "total_itens": total_itens,
                "pagina_atual": pagina,
                "total_paginas": total_paginas,
                "itens_por_pagina": itens_por_pagina
            }

    def navegar_segmento(
        self,
        id_atual: int,
        direcao: str = "proximo",
        filtro_status: str = "",
        filtro_origem: str = "",
        filtro_arquivo: str = "",
        filtro_categoria: str = "",
        apenas_inconsistencias: bool = False,
        apenas_sem_ia: bool = False,
        termo_busca: str = ""
    ) -> Optional[int]:
        """
        Navega para o próximo ou anterior ID de segmento dentro do conjunto filtrado.
        Retorna o ID do segmento ou None se não houver registros.
        """
        where_sql, parametros = self._montar_clausulas_filtro(
            filtro_status=filtro_status,
            filtro_origem=filtro_origem,
            filtro_arquivo=filtro_arquivo,
            filtro_categoria=filtro_categoria,
            apenas_inconsistencias=apenas_inconsistencias,
            apenas_sem_ia=apenas_sem_ia,
            termo_busca=termo_busca
        )
        with self.obter_conexao() as conexao:
            cursor = conexao.cursor()
            if direcao == "proximo":
                clausula_nav = f"{where_sql} AND s.id > ?" if where_sql else "WHERE s.id > ?"
                cursor.execute(f"SELECT s.id FROM segmentos s {clausula_nav} ORDER BY s.id ASC LIMIT 1", parametros + [id_atual])
                linha = cursor.fetchone()
                if linha:
                    return linha["id"]
                # Wrap-around para o primeiro do filtro
                cursor.execute(f"SELECT s.id FROM segmentos s {where_sql} ORDER BY s.id ASC LIMIT 1", parametros)
                linha_inicio = cursor.fetchone()
                return linha_inicio["id"] if linha_inicio else None
            else:
                clausula_nav = f"{where_sql} AND s.id < ?" if where_sql else "WHERE s.id < ?"
                cursor.execute(f"SELECT s.id FROM segmentos s {clausula_nav} ORDER BY s.id DESC LIMIT 1", parametros + [id_atual])
                linha = cursor.fetchone()
                if linha:
                    return linha["id"]
                # Wrap-around para o último do filtro
                cursor.execute(f"SELECT s.id FROM segmentos s {where_sql} ORDER BY s.id DESC LIMIT 1", parametros)
                linha_fim = cursor.fetchone()
                return linha_fim["id"] if linha_fim else None

    def obter_posicao_no_filtro(
        self,
        id_segmento: int,
        filtro_status: str = "",
        filtro_origem: str = "",
        filtro_arquivo: str = "",
        filtro_categoria: str = "",
        apenas_inconsistencias: bool = False,
        apenas_sem_ia: bool = False,
        termo_busca: str = ""
    ) -> Dict[str, int]:
        """Calcula a posição 1-based do segmento no subconjunto filtrado e os totais."""
        where_sql, parametros = self._montar_clausulas_filtro(
            filtro_status=filtro_status,
            filtro_origem=filtro_origem,
            filtro_arquivo=filtro_arquivo,
            filtro_categoria=filtro_categoria,
            apenas_inconsistencias=apenas_inconsistencias,
            apenas_sem_ia=apenas_sem_ia,
            termo_busca=termo_busca
        )
        with self.obter_conexao() as conexao:
            cursor = conexao.cursor()
            cursor.execute("SELECT COUNT(*) AS total_geral FROM segmentos")
            total_geral = cursor.fetchone()["total_geral"]

            cursor.execute(f"SELECT COUNT(*) AS total_filtrados FROM segmentos s {where_sql}", parametros)
            total_filtrados = cursor.fetchone()["total_filtrados"]

            if total_filtrados == 0:
                return {
                    "posicao_filtrada": 0,
                    "total_filtrados": 0,
                    "total_geral": total_geral
                }

            # Verificar se o segmento solicitado pertence ao conjunto filtrado
            clausula_pertence = f"{where_sql} AND s.id = ?" if where_sql else "WHERE s.id = ?"
            cursor.execute(f"SELECT COUNT(*) AS pertence FROM segmentos s {clausula_pertence}", parametros + [id_segmento])
            if cursor.fetchone()["pertence"] == 0:
                return {
                    "posicao_filtrada": 0,
                    "total_filtrados": total_filtrados,
                    "total_geral": total_geral
                }

            clausula_pos = f"{where_sql} AND s.id <= ?" if where_sql else "WHERE s.id <= ?"
            cursor.execute(f"SELECT COUNT(*) AS pos FROM segmentos s {clausula_pos}", parametros + [id_segmento])
            posicao = cursor.fetchone()["pos"]

            return {
                "posicao_filtrada": posicao if posicao > 0 else 1,
                "total_filtrados": total_filtrados,
                "total_geral": total_geral
            }

    def obter_arvore_hierarquica(self) -> List[Dict[str, Any]]:
        """Gera a árvore de categorias por arquivo com contagem de nós e pendências."""
        def extrair_categoria(chave: str) -> str:
            if "/" in chave:
                return chave.split("/")[0]
            elif "." in chave:
                return chave.split(".")[0]
            elif "_" in chave:
                partes = chave.split("_")
                return partes[0] if len(partes) > 1 else "geral"
            return "geral"

        with self.obter_conexao() as conexao:
            cursor = conexao.cursor()
            cursor.execute("SELECT arquivo, chave_hierarquica, status FROM segmentos")
            arvore: Dict[str, Dict[str, Dict[str, int]]] = {}
            for arq, chave, st in cursor.fetchall():
                cat = extrair_categoria(chave)
                if arq not in arvore:
                    arvore[arq] = {}
                if cat not in arvore[arq]:
                    arvore[arq][cat] = {"total": 0, "pendentes": 0}
                arvore[arq][cat]["total"] += 1
                if st == "pendente":
                    arvore[arq][cat]["pendentes"] += 1

            resultado = []
            for arq in sorted(arvore.keys()):
                categorias_lista = []
                total_arq = 0
                pendentes_arq = 0
                for cat_nome in sorted(arvore[arq].keys()):
                    dados = arvore[arq][cat_nome]
                    total_arq += dados["total"]
                    pendentes_arq += dados["pendentes"]
                    categorias_lista.append({
                        "id_categoria": f"cat::{arq}::{cat_nome}",
                        "nome": cat_nome,
                        "rotulo": cat_nome,
                        "arquivo": arq,
                        "total": dados["total"],
                        "pendentes": dados["pendentes"]
                    })
                resultado.append({
                    "id_no": f"arq::{arq}",
                    "arquivo": arq,
                    "rotulo": f"{arq} ({'CastleDB' if 'export' in arq else 'Diálogos/UI'})",
                    "total_itens": total_arq,
                    "total_pendentes": pendentes_arq,
                    "categorias": categorias_lista
                })
            return resultado

    def obter_estatisticas(self) -> Dict[str, Any]:
        """Retorna métricas gerais e métricas específicas do Mod para o painel de status da CAT Tool."""
        with self.obter_conexao() as conexao:
            cursor = conexao.cursor()
            cursor.execute("""
                SELECT
                    COUNT(*) AS total_segmentos,
                    SUM(CASE WHEN status = 'revisado' THEN 1 ELSE 0 END) AS revisados,
                    SUM(CASE WHEN status = 'pendente' THEN 1 ELSE 0 END) AS pendentes,
                    SUM(CASE WHEN status = 'bloqueado' THEN 1 ELSE 0 END) AS bloqueados,
                    SUM(CASE WHEN tem_inconsistencia = 1 THEN 1 ELSE 0 END) AS inconsistencias,
                    SUM(CASE WHEN aviso_qa IS NOT NULL AND aviso_qa != '' THEN 1 ELSE 0 END) AS qa_avisos_total,
                    COUNT(DISTINCT hash_conteudo) AS total_frases_unicas,

                    -- Escopo Real do Mod (Novos + Modificados)
                    SUM(CASE WHEN (vanilla_en IS NULL OR vanilla_en = '') OR (vanilla_en IS NOT NULL AND mod_en != vanilla_en) THEN 1 ELSE 0 END) AS mod_total,
                    SUM(CASE WHEN ((vanilla_en IS NULL OR vanilla_en = '') OR (vanilla_en IS NOT NULL AND mod_en != vanilla_en)) AND status = 'revisado' THEN 1 ELSE 0 END) AS mod_revisados,
                    SUM(CASE WHEN ((vanilla_en IS NULL OR vanilla_en = '') OR (vanilla_en IS NOT NULL AND mod_en != vanilla_en)) AND status = 'pendente' THEN 1 ELSE 0 END) AS mod_pendentes,
                    SUM(CASE WHEN ((vanilla_en IS NULL OR vanilla_en = '') OR (vanilla_en IS NOT NULL AND mod_en != vanilla_en)) AND tem_inconsistencia = 1 THEN 1 ELSE 0 END) AS mod_inconsistencias,
                    SUM(CASE WHEN ((vanilla_en IS NULL OR vanilla_en = '') OR (vanilla_en IS NOT NULL AND mod_en != vanilla_en)) AND (aviso_qa IS NOT NULL AND aviso_qa != '') THEN 1 ELSE 0 END) AS qa_avisos_mod,
                    SUM(CASE WHEN ((vanilla_en IS NULL OR vanilla_en = '') OR (vanilla_en IS NOT NULL AND mod_en != vanilla_en)) AND (status = 'revisado' OR (traducao_revisada IS NOT NULL AND traducao_revisada != '') OR (traducao_atual IS NOT NULL AND traducao_atual != '' AND traducao_atual != mod_en)) THEN 1 ELSE 0 END) AS mod_com_traducao,

                    -- Termos Novos
                    SUM(CASE WHEN vanilla_en IS NULL OR vanilla_en = '' THEN 1 ELSE 0 END) AS novos_total,
                    SUM(CASE WHEN (vanilla_en IS NULL OR vanilla_en = '') AND status = 'revisado' THEN 1 ELSE 0 END) AS novos_revisados,
                    SUM(CASE WHEN (vanilla_en IS NULL OR vanilla_en = '') AND status = 'pendente' THEN 1 ELSE 0 END) AS novos_pendentes,

                    -- Termos Modificados
                    SUM(CASE WHEN vanilla_en IS NOT NULL AND vanilla_en != '' AND mod_en != vanilla_en THEN 1 ELSE 0 END) AS modificados_total,
                    SUM(CASE WHEN (vanilla_en IS NOT NULL AND vanilla_en != '' AND mod_en != vanilla_en) AND status = 'revisado' THEN 1 ELSE 0 END) AS modificados_revisados,
                    SUM(CASE WHEN (vanilla_en IS NOT NULL AND vanilla_en != '' AND mod_en != vanilla_en) AND status = 'pendente' THEN 1 ELSE 0 END) AS modificados_pendentes,

                    -- Jogo Base Vanilla
                    SUM(CASE WHEN vanilla_en IS NOT NULL AND mod_en = vanilla_en THEN 1 ELSE 0 END) AS vanilla_total,
                    SUM(CASE WHEN (vanilla_en IS NOT NULL AND mod_en = vanilla_en) AND status = 'revisado' THEN 1 ELSE 0 END) AS vanilla_revisados,
                    SUM(CASE WHEN (vanilla_en IS NOT NULL AND mod_en = vanilla_en) AND (vanilla_pt IS NOT NULL AND vanilla_pt != '') THEN 1 ELSE 0 END) AS vanilla_com_pt
                FROM segmentos
            """)
            linha = cursor.fetchone()
            stats = dict(linha) if linha else {}

            for k in list(stats.keys()):
                if stats[k] is None:
                    stats[k] = 0

            total = stats.get("total_segmentos") or 0
            revisados = stats.get("revisados") or 0
            porcentagem = (revisados / total * 100.0) if total > 0 else 0.0
            stats["porcentagem_concluida"] = round(porcentagem, 1)

            mod_total = stats.get("mod_total") or 0
            mod_revisados = stats.get("mod_revisados") or 0
            mod_trad = stats.get("mod_com_traducao") or 0
            stats["mod_porcentagem_concluida"] = round((mod_revisados / mod_total * 100.0), 1) if mod_total > 0 else 0.0
            stats["mod_porcentagem_traducao"] = round((mod_trad / mod_total * 100.0), 1) if mod_total > 0 else 0.0

            cursor.execute("SELECT COUNT(*) AS total_termos FROM termos_glossario")
            stats["total_termos_glossario"] = cursor.fetchone()["total_termos"]

            cursor.execute("SELECT COUNT(*) AS total_mt FROM memoria_traducao")
            stats["total_memoria_traducao"] = cursor.fetchone()["total_mt"]

            return stats

    # =========================================================================
    # Operações de Glossário / Termbase
    # =========================================================================

    def listar_glossario(self) -> List[Dict[str, Any]]:
        """Retorna todos os termos cadastrados no glossário oficial."""
        with self.obter_conexao() as conexao:
            cursor = conexao.cursor()
            cursor.execute("""
                SELECT * FROM termos_glossario
                ORDER BY termo_en COLLATE NOCASE ASC
            """)
            return [dict(linha) for linha in cursor.fetchall()]

    def salvar_termo_glossario(
        self,
        termo_en: str,
        termo_pt_padrao: str,
        sinonimos_proibidos: str = "",
        categoria: str = "Geral",
        notas: str = ""
    ) -> int:
        """Cadastra ou atualiza um termo no glossário."""
        termo_en_limpo = normalizar_espacos(termo_en)
        termo_pt_limpo = normalizar_espacos(termo_pt_padrao)

        with self.obter_conexao() as conexao:
            cursor = conexao.cursor()
            cursor.execute("""
                INSERT INTO termos_glossario (termo_en, termo_pt_padrao, sinonimos_proibidos, categoria, notas)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(termo_en) DO UPDATE SET
                    termo_pt_padrao = excluded.termo_pt_padrao,
                    sinonimos_proibidos = excluded.sinonimos_proibidos,
                    categoria = excluded.categoria,
                    notas = excluded.notas
            """, (termo_en_limpo, termo_pt_limpo, sinonimos_proibidos, categoria, notas))
            conexao.commit()
            return cursor.lastrowid or 0

    def remover_termo_glossario(self, termo_id: int) -> bool:
        """Exclui um termo do glossário."""
        with self.obter_conexao() as conexao:
            cursor = conexao.cursor()
            cursor.execute("DELETE FROM termos_glossario WHERE id = ?", (termo_id,))
            conexao.commit()
            return cursor.rowcount > 0
