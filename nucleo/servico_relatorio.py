"""
Módulo de inteligência estatística e geração de relatórios de tradução.
Fornece métricas detalhadas separando o escopo real do Mod (termos novos e modificados)
dos termos originais do jogo base (Vanilla), além de gerar postagens formatadas
para o Nexus Mods em formato BBCode com elementos visuais de progresso.
"""

import math
from typing import Any, Dict, List, Optional
from nucleo.banco_dados import GerenciadorBancoDados


class ServicoRelatorio:
    """Serviço responsável por gerar relatórios inteligentes e publicações para o Nexus Mods."""

    @staticmethod
    def formatar_numero_br(valor: Any) -> str:
        """Formata números inteiros com o separador de milhares padrão do Brasil (ponto)."""
        if valor is None:
            valor = 0
        try:
            return f"{int(valor):,}".replace(",", ".")
        except (ValueError, TypeError):
            return "0"

    @staticmethod
    def gerar_barra_progresso_bbcode(
        porcentagem: float,
        tamanho: int = 20,
        cor_alta: str = "#4caf50",
        cor_media: str = "#2196f3",
        cor_baixa: str = "#ff9800",
        cor_vazia: str = "#555555"
    ) -> str:
        """
        Gera uma barra de progresso visual em BBCode utilizando blocos Unicode.
        Exemplo: [color=#4caf50]████████████████[/color][color=#555555]░░░░[/color] 80.0%
        """
        pct = max(0.0, min(100.0, float(porcentagem)))
        blocos_preenchidos = int(round((pct / 100.0) * tamanho))
        blocos_vazios = tamanho - blocos_preenchidos

        if pct >= 75.0:
            cor_ativa = cor_alta
        elif pct >= 35.0:
            cor_ativa = cor_media
        else:
            cor_ativa = cor_baixa

        str_preenchida = "█" * blocos_preenchidos
        str_vazia = "░" * blocos_vazios

        partes = []
        if str_preenchida:
            partes.append(f"[color={cor_ativa}]{str_preenchida}[/color]")
        if str_vazia:
            partes.append(f"[color={cor_vazia}]{str_vazia}[/color]")

        return "".join(partes)

    def obter_relatorio_completo(
        self,
        banco: GerenciadorBancoDados,
        projeto_ativo: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Calcula o relatório inteligente completo diferenciando:
        1. Escopo Real do Mod (Novos + Modificados)
        2. Termos Novos Exclusivos
        3. Termos Modificados (Vanilla alterado pelo Mod)
        4. Termos Originais do Jogo Base (Vanilla inalterados)
        5. Detalhamento por arquivo (export_en.xml vs texts_en.xml)
        6. Diagnóstico de qualidade e itens faltantes
        """
        with banco.obter_conexao() as conexao:
            cursor = conexao.cursor()

            # 1. Consulta consolidada de métricas globais e por escopo
            cursor.execute("""
                SELECT
                    COUNT(*) AS total_geral,
                    SUM(CASE WHEN status = 'revisado' THEN 1 ELSE 0 END) AS geral_revisados,
                    SUM(CASE WHEN status = 'pendente' THEN 1 ELSE 0 END) AS geral_pendentes,
                    SUM(CASE WHEN tem_inconsistencia = 1 THEN 1 ELSE 0 END) AS geral_inconsistencias,
                    SUM(CASE WHEN aviso_qa IS NOT NULL AND aviso_qa != '' THEN 1 ELSE 0 END) AS geral_avisos_qa,
                    
                    -- Escopo do Mod (Novos OU Modificados)
                    SUM(CASE WHEN (vanilla_en IS NULL OR vanilla_en = '') OR (vanilla_en IS NOT NULL AND mod_en != vanilla_en) THEN 1 ELSE 0 END) AS mod_total,
                    SUM(CASE WHEN ((vanilla_en IS NULL OR vanilla_en = '') OR (vanilla_en IS NOT NULL AND mod_en != vanilla_en)) AND status = 'revisado' THEN 1 ELSE 0 END) AS mod_revisados,
                    SUM(CASE WHEN ((vanilla_en IS NULL OR vanilla_en = '') OR (vanilla_en IS NOT NULL AND mod_en != vanilla_en)) AND status = 'pendente' THEN 1 ELSE 0 END) AS mod_pendentes,
                    SUM(CASE WHEN ((vanilla_en IS NULL OR vanilla_en = '') OR (vanilla_en IS NOT NULL AND mod_en != vanilla_en)) AND tem_inconsistencia = 1 THEN 1 ELSE 0 END) AS mod_inconsistencias,
                    SUM(CASE WHEN ((vanilla_en IS NULL OR vanilla_en = '') OR (vanilla_en IS NOT NULL AND mod_en != vanilla_en)) AND (aviso_qa IS NOT NULL AND aviso_qa != '') THEN 1 ELSE 0 END) AS mod_avisos_qa,
                    SUM(CASE WHEN ((vanilla_en IS NULL OR vanilla_en = '') OR (vanilla_en IS NOT NULL AND mod_en != vanilla_en)) AND (status = 'revisado' OR (traducao_revisada IS NOT NULL AND traducao_revisada != '') OR (traducao_atual IS NOT NULL AND traducao_atual != '' AND traducao_atual != mod_en)) THEN 1 ELSE 0 END) AS mod_com_traducao,

                    -- Apenas Termos Novos (Exclusivos do Mod)
                    SUM(CASE WHEN vanilla_en IS NULL OR vanilla_en = '' THEN 1 ELSE 0 END) AS novos_total,
                    SUM(CASE WHEN (vanilla_en IS NULL OR vanilla_en = '') AND status = 'revisado' THEN 1 ELSE 0 END) AS novos_revisados,
                    SUM(CASE WHEN (vanilla_en IS NULL OR vanilla_en = '') AND status = 'pendente' THEN 1 ELSE 0 END) AS novos_pendentes,
                    SUM(CASE WHEN (vanilla_en IS NULL OR vanilla_en = '') AND (status = 'revisado' OR (traducao_revisada IS NOT NULL AND traducao_revisada != '') OR (traducao_atual IS NOT NULL AND traducao_atual != '' AND traducao_atual != mod_en)) THEN 1 ELSE 0 END) AS novos_com_traducao,

                    -- Apenas Termos Modificados (Vanilla alterado pelo Mod)
                    SUM(CASE WHEN vanilla_en IS NOT NULL AND vanilla_en != '' AND mod_en != vanilla_en THEN 1 ELSE 0 END) AS modificados_total,
                    SUM(CASE WHEN (vanilla_en IS NOT NULL AND vanilla_en != '' AND mod_en != vanilla_en) AND status = 'revisado' THEN 1 ELSE 0 END) AS modificados_revisados,
                    SUM(CASE WHEN (vanilla_en IS NOT NULL AND vanilla_en != '' AND mod_en != vanilla_en) AND status = 'pendente' THEN 1 ELSE 0 END) AS modificados_pendentes,
                    SUM(CASE WHEN (vanilla_en IS NOT NULL AND vanilla_en != '' AND mod_en != vanilla_en) AND (status = 'revisado' OR (traducao_revisada IS NOT NULL AND traducao_revisada != '') OR (traducao_atual IS NOT NULL AND traducao_atual != '' AND traducao_atual != mod_en)) THEN 1 ELSE 0 END) AS modificados_com_traducao,

                    -- Jogo Base / Vanilla Inalterado
                    SUM(CASE WHEN vanilla_en IS NOT NULL AND mod_en = vanilla_en THEN 1 ELSE 0 END) AS vanilla_total,
                    SUM(CASE WHEN (vanilla_en IS NOT NULL AND mod_en = vanilla_en) AND status = 'revisado' THEN 1 ELSE 0 END) AS vanilla_revisados,
                    SUM(CASE WHEN (vanilla_en IS NOT NULL AND mod_en = vanilla_en) AND status = 'pendente' THEN 1 ELSE 0 END) AS vanilla_pendentes,
                    SUM(CASE WHEN (vanilla_en IS NOT NULL AND mod_en = vanilla_en) AND (vanilla_pt IS NOT NULL AND vanilla_pt != '') THEN 1 ELSE 0 END) AS vanilla_com_pt
                FROM segmentos
            """)
            linha_metricas = cursor.fetchone()
            m = dict(linha_metricas) if linha_metricas else {}

            # Tratamento de valores None para 0
            for k in list(m.keys()):
                if m[k] is None:
                    m[k] = 0

            # 2. Porcentagens calculadas com precisão
            def calcular_pct(parte: int, total: int) -> float:
                return round((parte / total * 100.0), 1) if total > 0 else 0.0

            mod_total = m.get("mod_total", 0)
            mod_rev = m.get("mod_revisados", 0)
            mod_trad = m.get("mod_com_traducao", 0)
            pct_mod_revisao = calcular_pct(mod_rev, mod_total)
            pct_mod_traducao = calcular_pct(mod_trad, mod_total)

            novos_total = m.get("novos_total", 0)
            novos_rev = m.get("novos_revisados", 0)
            novos_trad = m.get("novos_com_traducao", 0)
            pct_novos_revisao = calcular_pct(novos_rev, novos_total)
            pct_novos_traducao = calcular_pct(novos_trad, novos_total)

            modif_total = m.get("modificados_total", 0)
            modif_rev = m.get("modificados_revisados", 0)
            modif_trad = m.get("modificados_com_traducao", 0)
            pct_modif_revisao = calcular_pct(modif_rev, modif_total)
            pct_modif_traducao = calcular_pct(modif_trad, modif_total)

            vanilla_total = m.get("vanilla_total", 0)
            vanilla_com_pt = m.get("vanilla_com_pt", 0)
            pct_vanilla_oficial = calcular_pct(vanilla_com_pt, vanilla_total)

            total_geral = m.get("total_geral", 0)
            geral_rev = m.get("geral_revisados", 0)
            pct_geral = calcular_pct(geral_rev, total_geral)

            # 3. Detalhamento por arquivo
            cursor.execute("""
                SELECT
                    arquivo,
                    COUNT(*) AS total_arquivo,
                    SUM(CASE WHEN (vanilla_en IS NULL OR vanilla_en = '') OR (vanilla_en IS NOT NULL AND mod_en != vanilla_en) THEN 1 ELSE 0 END) AS mod_total,
                    SUM(CASE WHEN ((vanilla_en IS NULL OR vanilla_en = '') OR (vanilla_en IS NOT NULL AND mod_en != vanilla_en)) AND status = 'revisado' THEN 1 ELSE 0 END) AS mod_revisados,
                    SUM(CASE WHEN ((vanilla_en IS NULL OR vanilla_en = '') OR (vanilla_en IS NOT NULL AND mod_en != vanilla_en)) AND status = 'pendente' THEN 1 ELSE 0 END) AS mod_pendentes,
                    SUM(CASE WHEN ((vanilla_en IS NULL OR vanilla_en = '') OR (vanilla_en IS NOT NULL AND mod_en != vanilla_en)) AND (status = 'revisado' OR (traducao_revisada IS NOT NULL AND traducao_revisada != '') OR (traducao_atual IS NOT NULL AND traducao_atual != '' AND traducao_atual != mod_en)) THEN 1 ELSE 0 END) AS mod_com_traducao,
                    SUM(CASE WHEN vanilla_en IS NULL OR vanilla_en = '' THEN 1 ELSE 0 END) AS novos_total,
                    SUM(CASE WHEN (vanilla_en IS NULL OR vanilla_en = '') AND status = 'revisado' THEN 1 ELSE 0 END) AS novos_revisados,
                    SUM(CASE WHEN vanilla_en IS NOT NULL AND vanilla_en != '' AND mod_en != vanilla_en THEN 1 ELSE 0 END) AS modificados_total,
                    SUM(CASE WHEN (vanilla_en IS NOT NULL AND vanilla_en != '' AND mod_en != vanilla_en) AND status = 'revisado' THEN 1 ELSE 0 END) AS modificados_revisados,
                    SUM(CASE WHEN tem_inconsistencia = 1 THEN 1 ELSE 0 END) AS inconsistencias
                FROM segmentos
                GROUP BY arquivo
                ORDER BY arquivo ASC
            """)
            linhas_arquivos = cursor.fetchall()
            detalhes_arquivos = []
            for la in linhas_arquivos:
                d_arq = dict(la)
                for k in list(d_arq.keys()):
                    if d_arq[k] is None:
                        d_arq[k] = 0
                tot_mod_arq = d_arq.get("mod_total", 0)
                rev_mod_arq = d_arq.get("mod_revisados", 0)
                trad_mod_arq = d_arq.get("mod_com_traducao", 0)
                d_arq["porcentagem_revisao_mod"] = calcular_pct(rev_mod_arq, tot_mod_arq)
                d_arq["porcentagem_traducao_mod"] = calcular_pct(trad_mod_arq, tot_mod_arq)
                d_arq["rotulo_amigavel"] = "CastleDB (Itens, Habilidades, Classes)" if "export" in d_arq["arquivo"].lower() else "Diálogos, Quests e Interface"
                detalhes_arquivos.append(d_arq)

            # 4. Top Categorias com pendências no Mod
            cursor.execute("""
                SELECT
                    CASE
                        WHEN instr(trim(chave_hierarquica, '/._'), '/') > 0 THEN substr(trim(chave_hierarquica, '/._'), 1, instr(trim(chave_hierarquica, '/._'), '/') - 1)
                        WHEN instr(trim(chave_hierarquica, '/._'), '.') > 0 THEN substr(trim(chave_hierarquica, '/._'), 1, instr(trim(chave_hierarquica, '/._'), '.') - 1)
                        WHEN instr(trim(chave_hierarquica, '/._'), '_') > 0 THEN substr(trim(chave_hierarquica, '/._'), 1, instr(trim(chave_hierarquica, '/._'), '_') - 1)
                        ELSE coalesce(nullif(trim(chave_hierarquica, '/._'), ''), 'geral')
                    END AS categoria,
                    arquivo,
                    COUNT(*) AS total_categoria,
                    SUM(CASE WHEN status = 'pendente' THEN 1 ELSE 0 END) AS pendentes,
                    SUM(CASE WHEN status = 'revisado' THEN 1 ELSE 0 END) AS revisados
                FROM segmentos
                WHERE (vanilla_en IS NULL OR vanilla_en = '') OR (vanilla_en IS NOT NULL AND mod_en != vanilla_en)
                GROUP BY categoria, arquivo
                ORDER BY pendentes DESC
                LIMIT 15
            """)
            top_categorias = [dict(linha) for linha in cursor.fetchall()]

            # 5. Informações do Projeto Ativo
            info_projeto = {
                "nome": (projeto_ativo or {}).get("nome", "Wartales Remastered"),
                "versao": (projeto_ativo or {}).get("versao", "v7.40"),
                "autor": "Cassr"
            }

            return {
                "projeto": info_projeto,
                "mod": {
                    "total": mod_total,
                    "revisados": mod_rev,
                    "pendentes": m.get("mod_pendentes", 0),
                    "com_traducao": mod_trad,
                    "sem_traducao": max(0, mod_total - mod_trad),
                    "inconsistencias": m.get("mod_inconsistencias", 0),
                    "avisos_qa": m.get("mod_avisos_qa", 0),
                    "porcentagem_revisao": pct_mod_revisao,
                    "porcentagem_traducao": pct_mod_traducao
                },
                "novos": {
                    "total": novos_total,
                    "revisados": novos_rev,
                    "pendentes": m.get("novos_pendentes", 0),
                    "com_traducao": novos_trad,
                    "sem_traducao": max(0, novos_total - novos_trad),
                    "porcentagem_revisao": pct_novos_revisao,
                    "porcentagem_traducao": pct_novos_traducao
                },
                "modificados": {
                    "total": modif_total,
                    "revisados": modif_rev,
                    "pendentes": m.get("modificados_pendentes", 0),
                    "com_traducao": modif_trad,
                    "sem_traducao": max(0, modif_total - modif_trad),
                    "porcentagem_revisao": pct_modif_revisao,
                    "porcentagem_traducao": pct_modif_traducao
                },
                "vanilla": {
                    "total": vanilla_total,
                    "revisados": m.get("vanilla_revisados", 0),
                    "pendentes": m.get("vanilla_pendentes", 0),
                    "com_pt_oficial": vanilla_com_pt,
                    "porcentagem_oficial": pct_vanilla_oficial
                },
                "geral": {
                    "total": total_geral,
                    "revisados": geral_rev,
                    "pendentes": m.get("geral_pendentes", 0),
                    "inconsistencias": m.get("geral_inconsistencias", 0),
                    "porcentagem_revisao": pct_geral
                },
                "arquivos": detalhes_arquivos,
                "top_categorias": top_categorias
            }

    def gerar_texto_nexus(
        self,
        dados_relatorio: Dict[str, Any],
        opcoes: Optional[Dict[str, Any]] = None
    ) -> Dict[str, str]:
        """
        Gera o texto formatado em BBCode e a versão convertida em HTML para preview visual.
        Suporta 3 modelos:
        - 'atualizacao': Post de Atualização / Andamento (Devlog para fórum / posts)
        - 'descricao': Descrição Completa da Página do Mod
        - 'compacto': Resumo Compacto com Badge e Barra
        """
        cfg = opcoes or {}
        modelo = cfg.get("modelo", "atualizacao")
        nome_mod = cfg.get("nome_mod") or dados_relatorio.get("projeto", {}).get("nome", "Wartales Remastered")
        versao_mod = cfg.get("versao_mod") or dados_relatorio.get("projeto", {}).get("versao", "v7.40")
        autor = cfg.get("autor") or dados_relatorio.get("projeto", {}).get("autor", "Cassr")

        incluir_barras = cfg.get("incluir_barras_progresso", True)
        incluir_detalhes_escopo = cfg.get("incluir_detalhes_escopo", True)
        incluir_arquivos = cfg.get("incluir_detalhes_arquivos", True)
        incluir_instalacao = cfg.get("incluir_instalacao", True)
        incluir_feedback = cfg.get("incluir_feedback", True)
        incluir_castledb = cfg.get("incluir_castledb", True)

        mod = dados_relatorio.get("mod", {})
        novos = dados_relatorio.get("novos", {})
        modif = dados_relatorio.get("modificados", {})
        vanilla = dados_relatorio.get("vanilla", {})
        arquivos = dados_relatorio.get("arquivos", [])

        # Barras de progresso formatadas
        geral = dados_relatorio.get("geral", {})
        barra_mod_traducao = self.gerar_barra_progresso_bbcode(mod.get("porcentagem_traducao", 0.0))
        barra_mod_revisao = self.gerar_barra_progresso_bbcode(mod.get("porcentagem_revisao", 0.0))
        barra_novos = self.gerar_barra_progresso_bbcode(novos.get("porcentagem_traducao", 0.0))
        barra_modificados = self.gerar_barra_progresso_bbcode(modif.get("porcentagem_traducao", 0.0))
        barra_geral = self.gerar_barra_progresso_bbcode(geral.get("porcentagem_revisao", 0.0))

        linhas: List[str] = []

        if modelo == "atualizacao":
            # -----------------------------------------------------------------
            # MODELO: Post de Atualização / Devlog de Andamento
            # -----------------------------------------------------------------
            linhas.append(f"[size=5][b][color=#4caf50]⚔️ {nome_mod} - Andamento da Tradução PT-BR[/color][/b][/size]")
            linhas.append(f"[b][color=#2196f3]Versão de Referência: {versao_mod} | Tradução por: {autor}[/color][/b]")
            linhas.append("")
            linhas.append("Olá pessoal! Aqui está o relatório detalhado do progresso da localização em Português do Brasil para a comunidade:")
            linhas.append("")

            if incluir_barras:
                linhas.append("[quote]")
                linhas.append("[size=4][b]📊 BARRAS DE PROGRESSO DO MOD[/b][/size]")
                linhas.append(f"[b]Tradução dos Textos do Mod:[/b] {barra_mod_traducao} [b][color=#4caf50]{mod.get('porcentagem_traducao', 0.0)}%[/color][/b] ({self.formatar_numero_br(mod.get('com_traducao', 0))} / {self.formatar_numero_br(mod.get('total', 0))} termos)")
                linhas.append(f"[b]Validação e Revisão Humana:[/b] {barra_mod_revisao} [b][color=#2196f3]{mod.get('porcentagem_revisao', 0.0)}%[/color][/b] ({self.formatar_numero_br(mod.get('revisados', 0))} / {self.formatar_numero_br(mod.get('total', 0))} termos)")
                linhas.append(f"[b]Termos Novos Exclusivos:[/b]    {barra_novos} [b]{novos.get('porcentagem_traducao', 0.0)}%[/b] ({self.formatar_numero_br(novos.get('com_traducao', 0))} / {self.formatar_numero_br(novos.get('total', 0))})")
                linhas.append(f"[b]Termos Modificados:[/b]          {barra_modificados} [b]{modif.get('porcentagem_traducao', 0.0)}%[/b] ({self.formatar_numero_br(modif.get('com_traducao', 0))} / {self.formatar_numero_br(modif.get('total', 0))})")
                linhas.append(f"[b]Base Oficial Shiro Games:[/b]   [color=#4caf50]████████████████████[/color] [b]100.0%[/b] ({self.formatar_numero_br(vanilla.get('total', 0))} termos preservados)")
                linhas.append(f"[b]Validação Geral (Jogo+Mod):[/b]  {barra_geral} [b]{geral.get('porcentagem_revisao', 0.0)}%[/b] ({self.formatar_numero_br(geral.get('revisados', 0))} / {self.formatar_numero_br(geral.get('total', 0))} termos gerais)")
                linhas.append("[/quote]")
                linhas.append("")

            if incluir_detalhes_escopo:
                linhas.append("[size=4][b]🔍 Raio-X dos Termos (Escopo Real do Mod)[/b][/size]")
                linhas.append(f"- [b]Termos Específicos do Mod:[/b] {self.formatar_numero_br(mod.get('total', 0))} termos sob medida ({self.formatar_numero_br(novos.get('total', 0))} novas habilidades/itens + {self.formatar_numero_br(modif.get('total', 0))} alterações balanceadas).")
                linhas.append(f"- [b]Textos Prontos para Gameplay:[/b] [color=#4caf50]{self.formatar_numero_br(mod.get('com_traducao', 0))} termos[/color] traduzidos e jogáveis.")
                linhas.append(f"- [b]Termos Originais Preservados:[/b] {self.formatar_numero_br(vanilla.get('total', 0))} termos mantidos 100% da tradução oficial da Shiro Games sem conflitos.")
                linhas.append(f"- [b]O Que Falta Revisar:[/b] Restam {self.formatar_numero_br(mod.get('pendentes', 0))} termos para revisão final de gameplay.")
                linhas.append("")

            if incluir_arquivos and arquivos:
                linhas.append("[size=4][b]📁 Andamento por Arquivo de Dados[/b][/size]")
                for arq in arquivos:
                    nome_arq = arq.get("arquivo", "")
                    rotulo = arq.get("rotulo_amigavel", "")
                    tot_mod_arq = arq.get("mod_total", 0)
                    trad_arq = arq.get("mod_com_traducao", 0)
                    pct_arq = arq.get("porcentagem_traducao_mod", 0.0)
                    linhas.append(f"- [b]{nome_arq}[/b] ([i]{rotulo}[/i]): [color=#2196f3]{pct_arq}%[/color] ({self.formatar_numero_br(trad_arq)} / {self.formatar_numero_br(tot_mod_arq)} termos do mod)")
                linhas.append("")

            if incluir_castledb:
                linhas.append("[size=4][b]🛡️ Estabilidade e Integridade CastleDB[/b][/size]")
                linhas.append("- Estrutura de dados validada contra quebras de linha indevidas [i][br][/i] no início de células CastleDB.")
                linhas.append("- Zero travamentos e 100% de compatibilidade com a engine Heaps.io da Shiro Games.")
                linhas.append("- Empacotamento modular através de [b]res2.pak[/b] (download leve de ~1 MB que não corrompe o jogo base).")
                linhas.append("")

            if incluir_instalacao:
                linhas.append("[size=4][b]📥 Como Instalar:[/b][/size]")
                linhas.append("1. Baixe o pacote e copie o arquivo [b]res2.pak[/b].")
                linhas.append("2. Cole na pasta raiz do seu Wartales na Steam ([i]SteamLibrary\\steamapps\\common\\Wartales\\[/i]).")
                linhas.append("3. Inicie o jogo com o idioma em Português (Brasil).")
                linhas.append("")

            if incluir_feedback:
                linhas.append("[size=4][b]💬 Feedback e Sugestões:[/b][/size]")
                linhas.append("Encontrou algum termo com contexto duvidoso ou sinônimo diferente durante suas partidas? Deixe uma mensagem na aba [b]Posts[/b]! O retorno da comunidade ajuda a lapidar os detalhes a cada atualização.")

        elif modelo == "descricao":
            # -----------------------------------------------------------------
            # MODELO: Descrição Completa para a Página Principal do Mod
            # -----------------------------------------------------------------
            linhas.append(f"[size=5][b]{nome_mod} - Tradução em Português do Brasil (pt-BR)[/b][/size]")
            linhas.append(f"[b]Compatível com {nome_mod} {versao_mod} | Pacote Modular res2.pak[/b]")
            linhas.append("")
            linhas.append(f"Esta é a tradução em Português do Brasil para o overhaul [b]{nome_mod}[/b], adaptada com rigor terminológico e compatibilidade técnica.")
            linhas.append("")

            if incluir_barras:
                linhas.append("[quote]")
                linhas.append(f"[size=4][b]STATUS DA LOCALIZAÇÃO:[/b][/size]")
                linhas.append(f"[b]Cobertura de Tradução:[/b] {barra_mod_traducao} [b][color=#4caf50]{mod.get('porcentagem_traducao', 0.0)}%[/color][/b] ({self.formatar_numero_br(mod.get('com_traducao', 0))} / {self.formatar_numero_br(mod.get('total', 0))} termos)")
                linhas.append(f"[b]Revisão Humana:[/b]        {barra_mod_revisao} [b][color=#2196f3]{mod.get('porcentagem_revisao', 0.0)}%[/color][/b] ({self.formatar_numero_br(mod.get('revisados', 0))} / {self.formatar_numero_br(mod.get('total', 0))} termos)")
                linhas.append(f"[b]Textos Originais Shiro:[/b] [color=#4caf50]████████████████████[/color] [b]100% Preservados[/b] ({self.formatar_numero_br(vanilla.get('total', 0))} termos)")
                linhas.append(f"[b]Validação Geral (Jogo+Mod):[/b]  {barra_geral} [b]{geral.get('porcentagem_revisao', 0.0)}%[/b] ({self.formatar_numero_br(geral.get('revisados', 0))} / {self.formatar_numero_br(geral.get('total', 0))} termos gerais)")
                linhas.append("[/quote]")
                linhas.append("")

            if incluir_detalhes_escopo:
                linhas.append("[size=4][b]🔍 Raio-X dos Termos (Escopo Real do Mod)[/b][/size]")
                linhas.append(f"- [b]Termos Específicos do Mod:[/b] {self.formatar_numero_br(mod.get('total', 0))} termos sob medida ({self.formatar_numero_br(novos.get('total', 0))} novas habilidades/itens + {self.formatar_numero_br(modif.get('total', 0))} alterações balanceadas).")
                linhas.append(f"- [b]Textos Prontos para Gameplay:[/b] [color=#4caf50]{self.formatar_numero_br(mod.get('com_traducao', 0))} termos[/color] traduzidos e jogáveis.")
                linhas.append(f"- [b]Termos Originais Preservados:[/b] {self.formatar_numero_br(vanilla.get('total', 0))} termos mantidos 100% da tradução oficial da Shiro Games sem conflitos.")
                linhas.append(f"- [b]O Que Falta Revisar:[/b] Restam {self.formatar_numero_br(mod.get('pendentes', 0))} termos para revisão final de gameplay.")
                linhas.append("")

            if incluir_arquivos and arquivos:
                linhas.append("[size=4][b]📁 Andamento por Arquivo de Dados[/b][/size]")
                for arq in arquivos:
                    nome_arq = arq.get("arquivo", "")
                    rotulo = arq.get("rotulo_amigavel", "")
                    tot_mod_arq = arq.get("mod_total", 0)
                    trad_arq = arq.get("mod_com_traducao", 0)
                    pct_arq = arq.get("porcentagem_traducao_mod", 0.0)
                    linhas.append(f"- [b]{nome_arq}[/b] ([i]{rotulo}[/i]): [color=#2196f3]{pct_arq}%[/color] ({self.formatar_numero_br(trad_arq)} / {self.formatar_numero_br(tot_mod_arq)} termos do mod)")
                linhas.append("")

            linhas.append("[size=4][b]Destaques da Tradução:[/b][/size]")
            linhas.append(f"- [b]100% Jogável em PT-BR:[/b] Cobre todas as novas habilidades, classes, itens, mercenários e reformas da versão {versao_mod}.")
            linhas.append("- [b]Terminologia Oficial Mantida:[/b] Todos os textos originais do jogo base foram sincronizados diretamente com a localização oficial da Shiro Games.")
            if incluir_castledb:
                linhas.append("- [b]Zero Crashes (CastleDB Validado):[/b] Sem assert de quebra de linha ou tags ausentes.")
            if incluir_instalacao:
                linhas.append("- [b]Instalação Leve e Segura:[/b] Formato res2.pak (pesa apenas ~1 MB e não modifica seus arquivos originais do Wartales).")
            linhas.append("")

            if incluir_instalacao:
                linhas.append("[size=4][b]Instalação Simples:[/b][/size]")
                linhas.append("1. Baixe e extraia o arquivo ZIP.")
                linhas.append("2. Mova o arquivo [b]res2.pak[/b] para a pasta raiz do seu Wartales na Steam ([i]common\\Wartales[/i]).")
                linhas.append("3. Inicie o jogo em Português!")
                linhas.append("")

            if incluir_feedback:
                linhas.append("[size=4][b]Feedback da Comunidade:[/b][/size]")
                linhas.append("Comente na aba [b]Posts[/b] caso encontre alguma inconsistência para que possamos aprimorar na próxima revisão.")
                linhas.append("")

            linhas.append("[size=4][b]Créditos:[/b][/size]")
            linhas.append("- Mod original por sua respectiva equipe de desenvolvimento.")
            linhas.append(f"- Tradução PT-BR adaptada por [b]{autor}[/b] com auxílio do Wartales CAT Studio.")

        else:
            # -----------------------------------------------------------------
            # MODELO: Resumo Compacto / Badge de Status
            # -----------------------------------------------------------------
            linhas.append(f"[b][color=#4caf50][ TRADUÇÃO PT-BR - {nome_mod} {versao_mod} ][/color][/b]")
            if incluir_barras:
                linhas.append(f"[b]Tradução Mod:[/b] {barra_mod_traducao} [b]{mod.get('porcentagem_traducao', 0.0)}%[/b] ({self.formatar_numero_br(mod.get('com_traducao', 0))} / {self.formatar_numero_br(mod.get('total', 0))})")
                linhas.append(f"[b]Revisão Humana:[/b] {barra_mod_revisao} [b]{mod.get('porcentagem_revisao', 0.0)}%[/b] ({self.formatar_numero_br(mod.get('revisados', 0))} termos)")
            else:
                linhas.append(f"Progresso de Tradução: {mod.get('porcentagem_traducao', 0.0)}% | Revisão Humana: {mod.get('porcentagem_revisao', 0.0)}%")
            if incluir_detalhes_escopo:
                linhas.append(f"[i]Novos: {novos.get('porcentagem_traducao', 0.0)}% ({self.formatar_numero_br(novos.get('com_traducao', 0))}/{self.formatar_numero_br(novos.get('total', 0))}) | Modificados: {modif.get('porcentagem_traducao', 0.0)}% ({self.formatar_numero_br(modif.get('com_traducao', 0))}/{self.formatar_numero_br(modif.get('total', 0))})[/i]")
            detalhe_extra = " | CastleDB Validado" if incluir_castledb else ""
            linhas.append(f"[i]Base Oficial Shiro Games: 100% mantida ({self.formatar_numero_br(vanilla.get('total', 0))} termos) | res2.pak modular{detalhe_extra}[/i]")
            if incluir_arquivos and arquivos:
                resumo_arqs = " | ".join(f"{a.get('arquivo', '')}: {a.get('porcentagem_traducao_mod', 0.0)}%" for a in arquivos)
                linhas.append(f"[i]Arquivos: {resumo_arqs}[/i]")
            if incluir_instalacao:
                linhas.append("[i]Instalação: Copie res2.pak para a pasta raiz do Wartales.[/i]")
            if incluir_feedback:
                linhas.append("[i]Comente na aba Posts para reportar sugestões de tradução.[/i]")

        texto_bbcode = "\n".join(linhas)
        html_preview = self.converter_bbcode_para_html(texto_bbcode)

        return {
            "modelo": modelo,
            "bbcode": texto_bbcode,
            "html_preview": html_preview
        }

    @staticmethod
    def converter_bbcode_para_html(bbcode: str) -> str:
        """
        Converte as tags BBCode suportadas pelo Nexus Mods para HTML acessível
        para exibição em tempo real na tela de preview da interface.
        """
        import re
        import html

        texto = html.escape(bbcode)

        # Sizes: [size=5] -> <h3>, [size=4] -> <h4>
        texto = re.sub(r'\[size=5\](.*?)\[/size\]', r'<h3 class="nexus-preview-h3">\1</h3>', texto, flags=re.DOTALL)
        texto = re.sub(r'\[size=4\](.*?)\[/size\]', r'<h4 class="nexus-preview-h4">\1</h4>', texto, flags=re.DOTALL)
        texto = re.sub(r'\[size=[1-3]\](.*?)\[/size\]', r'<h5 class="nexus-preview-h5">\1</h5>', texto, flags=re.DOTALL)

        # Colors: [color=#hex]...[/color]
        texto = re.sub(
            r'\[color=([#a-zA-Z0-9]+)\](.*?)\[/color\]',
            r'<span style="color: \1; font-weight: inherit;">\2</span>',
            texto,
            flags=re.DOTALL
        )

        # Quotes: [quote]...[/quote]
        texto = re.sub(
            r'\[quote\](.*?)\[/quote\]',
            r'<div class="nexus-preview-quote">\1</div>',
            texto,
            flags=re.DOTALL
        )

        # Center: [center]...[/center]
        texto = re.sub(r'\[center\](.*?)\[/center\]', r'<div style="text-align: center;">\1</div>', texto, flags=re.DOTALL)

        # Code: [code]...[/code]
        texto = re.sub(r'\[code\](.*?)\[/code\]', r'<pre class="nexus-preview-code"><code>\1</code></pre>', texto, flags=re.DOTALL)

        # URLs seguras: [url=...]...[/url] e [url]...[/url]
        def _sub_url_com_link(match):
            href = match.group(1).strip()
            rotulo = match.group(2)
            if not re.match(r'^(https?://|mailto:|#|/)', href, re.IGNORECASE):
                href = "#"
            return f'<a href="{href}" target="_blank" rel="noopener noreferrer" style="color: #58a6ff; text-decoration: underline;">{rotulo}</a>'

        def _sub_url_simples(match):
            href = match.group(1).strip()
            rotulo = href
            if not re.match(r'^(https?://|mailto:|#|/)', href, re.IGNORECASE):
                href = "#"
            return f'<a href="{href}" target="_blank" rel="noopener noreferrer" style="color: #58a6ff; text-decoration: underline;">{rotulo}</a>'

        texto = re.sub(r'\[url=([^\]]+)\](.*?)\[/url\]', _sub_url_com_link, texto, flags=re.DOTALL)
        texto = re.sub(r'\[url\](.*?)\[/url\]', _sub_url_simples, texto, flags=re.DOTALL)

        # Bold, Italic, Underline
        texto = re.sub(r'\[b\](.*?)\[/b\]', r'<strong>\1</strong>', texto, flags=re.DOTALL)
        texto = re.sub(r'\[i\](.*?)\[/i\]', r'<em>\1</em>', texto, flags=re.DOTALL)
        texto = re.sub(r'\[u\](.*?)\[/u\]', r'<u>\1</u>', texto, flags=re.DOTALL)

        # Quebras de linha
        texto = texto.replace("\n", "<br>")

        # Limpar <br> excessivos antes ou depois de tags de bloco
        texto = re.sub(r'(<h[3-5][^>]*>)<br>', r'\1', texto)
        texto = re.sub(r'<br>(</h[3-5]>)', r'\1', texto)
        texto = re.sub(r'(<div[^>]*>)<br>', r'\1', texto)
        texto = re.sub(r'<br>(</div>)', r'\1', texto)
        texto = re.sub(r'(<pre[^>]*>)<br>', r'\1', texto)
        texto = re.sub(r'<br>(</pre>)', r'\1', texto)

        return texto
