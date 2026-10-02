"""
Testes de integridade da Interface, HTML, CSS e JavaScript do Wartales CAT Studio.
Garante que modais, seletores de ID e classes do Design System existam sem discrepâncias.
"""

import os
import re
import unittest

DIRETORIO_PROJETO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAMINHO_HTML = os.path.join(DIRETORIO_PROJETO, "interface", "index.html")
CAMINHO_CSS = os.path.join(DIRETORIO_PROJETO, "interface", "css", "estilos.css")
CAMINHO_APP_JS = os.path.join(DIRETORIO_PROJETO, "interface", "js", "app.js")
CAMINHO_GLOSSARIO_JS = os.path.join(DIRETORIO_PROJETO, "interface", "js", "glossario.js")
CAMINHO_GERENCIADOR_JS = os.path.join(DIRETORIO_PROJETO, "interface", "js", "gerenciador_mod.js")
CAMINHO_API_JS = os.path.join(DIRETORIO_PROJETO, "interface", "js", "api.js")


class TesteIntegridadeInterface(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        with open(CAMINHO_HTML, "r", encoding="utf-8") as f:
            cls.conteudo_html = f.read()
        with open(CAMINHO_CSS, "r", encoding="utf-8") as f:
            cls.conteudo_css = f.read()
        with open(CAMINHO_APP_JS, "r", encoding="utf-8") as f:
            cls.conteudo_app_js = f.read()
        with open(CAMINHO_GLOSSARIO_JS, "r", encoding="utf-8") as f:
            cls.conteudo_glossario_js = f.read()
        with open(CAMINHO_GERENCIADOR_JS, "r", encoding="utf-8") as f:
            cls.conteudo_gerenciador_js = f.read()
        with open(CAMINHO_API_JS, "r", encoding="utf-8") as f:
            cls.conteudo_api_js = f.read()

    def teste_ids_dom_referenciados_no_javascript(self):
        """Todos os IDs buscados com getElementById no JS devem existir no HTML."""
        padrao_id = re.compile(r'document\.getElementById\(["\']([a-zA-Z0-9\-_]+)["\']\)')
        ids_app = padrao_id.findall(self.conteudo_app_js)
        ids_glossario = padrao_id.findall(self.conteudo_glossario_js)
        ids_gerenciador = padrao_id.findall(self.conteudo_gerenciador_js)
        todos_ids = set(ids_app + ids_glossario + ids_gerenciador)

        ids_ausentes = []
        for id_alvo in todos_ids:
            if f'id="{id_alvo}"' not in self.conteudo_html and f"id='{id_alvo}'" not in self.conteudo_html:
                ids_ausentes.append(id_alvo)

        self.assertEqual(ids_ausentes, [], f"IDs referenciados no JS ausentes no HTML: {ids_ausentes}")

    def teste_modais_estruturados_corretamente(self):
        """Modais devem ter classe modal-overlay, estar inicialmente ocultos e conter modal-caixa."""
        modais = [
            "modal-atalhos",
            "modal-compilacao",
            "modal-glossario",
            "modal-propagacao",
            "modal-gerenciador-mod",
            "modal-filtros-avancados",
            "modal-relatorio"
        ]

        for modal_id in modais:
            self.assertIn(f'id="{modal_id}"', self.conteudo_html, f"Modal #{modal_id} não encontrado no HTML")
            # Extrair o bloco da tag do modal
            padrao = re.compile(rf'<div[^>]*id="{modal_id}"[^>]*class="([^"]+)"', re.DOTALL)
            match = padrao.search(self.conteudo_html)
            self.assertIsNotNone(match, f"Não foi possível ler as classes de #{modal_id}")
            classes = match.group(1).split() if match is not None else []
            self.assertIn("modal-overlay", classes, f"#{modal_id} deve ter a classe 'modal-overlay'")
            self.assertIn("oculto", classes, f"#{modal_id} deve ter a classe 'oculto' por padrão")

    def teste_classes_css_essenciais_design_system(self):
        """Classes críticas para modais flutuantes, overview e notificações devem existir no CSS."""
        classes_obrigatorias = [
            ".modal-overlay",
            ".modal-caixa",
            ".modal-cabecalho",
            ".modal-titulo",
            ".btn-fechar-modal",
            ".modal-corpo",
            ".modal-rodape",
            ".tabela-atalhos",
            ".compilacao-log",
            ".toast-notificacao",
            ".linha-segmento-overview",
            ".linha-segmento-topo",
            ".linha-segmento-comparacao",
            ".col-previa",
            ".rotulo-col-previa",
            ".icone-pasta",
            ".lista-filhos",
            ".form-glossario",
            ".tabela-glossario-wrapper",
            ".tabela-glossario",
            ".lista-previa-repeticoes",
            ".tecla-atalho"
        ]

        for classe in classes_obrigatorias:
            self.assertIn(classe, self.conteudo_css, f"Classe CSS essencial '{classe}' ausente em estilos.css")

    def teste_toast_notificacao_acessivel(self):
        """Toast deve ter role status e aria-live polite."""
        self.assertIn('id="toast-notificacao"', self.conteudo_html)
        self.assertIn('role="status"', self.conteudo_html)
        self.assertIn('aria-live="polite"', self.conteudo_html)

    def teste_metodos_api_cat_sincronizados(self):
        """Métodos chamados pelo app.js e glossario.js devem existir em ApiCat."""
        metodos_necessarios = [
            "obterPrimeiroSegmento",
            "obterSegmento",
            "navegarSegmento",
            "salvarSegmento",
            "obterEstatisticas",
            "obterArvore",
            "buscarSegmentos",
            "compilarProjeto",
            "listarGlossario",
            "salvarTermoGlossario",
            "removerTermoGlossario",
            "substituirSinonimoLote",
            "auditarInconsistencias",
            "traduzirIa",
            "obterProjetos",
            "obterInfoVanilla",
            "autodetectarSteam",
            "criarProjeto",
            "ativarProjeto",
            "sincronizarBancoProjeto",
            "extrairPak",
            "salvarCaminhoSteam",
            "salvarChaveGemini",
            "analisarDeltasIa",
            "iniciarTraducaoLoteIa",
            "obterStatusLoteIa",
            "obterEstatisticasMemoriaGlobal",
            "obterRelatorio",
            "gerarTextoNexus",
            "salvarTextoNexus"
        ]
        for metodo in metodos_necessarios:
            self.assertIn(f"{metodo}(", self.conteudo_api_js, f"Método '{metodo}' ausente no objeto ApiCat em api.js")

    def teste_scrollbars_customizadas_tema_escuro(self):
        """O CSS deve conter regras de scrollbar escura para evitar barras brancas nativas."""
        self.assertIn("::-webkit-scrollbar", self.conteudo_css)
        self.assertIn("scrollbar-color", self.conteudo_css)

    def teste_classes_responsivas_e_design_system(self):
        """Classes de botões compactos, inputs genéricos e modais dimensionados devem existir no CSS."""
        classes = [
            ".btn-compacto",
            ".btn-xs",
            ".campo-entrada",
            ".modal-caixa.modal-ampla",
            ".modal-caixa.modal-media",
            ".arvore-acoes",
            ".glossario-busca-linha",
            ".tabs-nav-setup",
            ".tab-botao-setup",
            ".card-status-arquivo",
            ".grade-estatisticas-deltas",
            ".progresso-ia-caixa"
        ]
        for cls in classes:
            self.assertIn(cls, self.conteudo_css, f"Classe '{cls}' ausente em estilos.css")

    def teste_acessibilidade_botoes_e_dialogos(self):
        """Modais devem ter aria-labelledby e botões disparadores devem ter aria-haspopup."""
        self.assertIn('aria-haspopup="dialog"', self.conteudo_html)
        self.assertIn('aria-labelledby="titulo-modal-atalhos"', self.conteudo_html)
        self.assertIn('aria-labelledby="titulo-modal-compilacao"', self.conteudo_html)
        self.assertIn('aria-labelledby="titulo-modal-glossario"', self.conteudo_html)
        self.assertIn('aria-labelledby="titulo-modal-propagacao"', self.conteudo_html)
        self.assertIn('aria-labelledby="titulo-modal-gerenciador"', self.conteudo_html)
        self.assertIn('aria-labelledby="titulo-modal-filtros"', self.conteudo_html)

    def teste_modulo_glossario_exportado_globalmente(self):
        """glossario.js deve exportar ModuloGlossario para window para ser acessível pelo app.js e eventos DOM."""
        self.assertIn("window.ModuloGlossario = ModuloGlossario", self.conteudo_glossario_js)
        self.assertIn("carregarTermos", self.conteudo_glossario_js)
        self.assertIn("aplicarSubstituicaoLotePorId", self.conteudo_glossario_js)

    def teste_modulo_gerenciador_exportado_globalmente(self):
        """gerenciador_mod.js deve exportar ModuloGerenciadorMod para window."""
        self.assertIn("window.ModuloGerenciadorMod = ModuloGerenciadorMod", self.conteudo_gerenciador_js)
        self.assertIn("trocarAba", self.conteudo_gerenciador_js)
        self.assertIn("carregarProjetos", self.conteudo_gerenciador_js)

    def teste_elementos_filtros_compostos(self):
        """Valida que todos os controles e classes de filtros compostos estão íntegros e acessíveis."""
        # 1. Presets do Modo Foco
        presets_esperados = [
            'value="mod_pendentes"',
            'value="mod_novos_pendentes"',
            'value="mod_modificados_pendentes"',
            'value="mod_todos"'
        ]
        for preset in presets_esperados:
            self.assertIn(preset, self.conteudo_html, f"Preset '{preset}' ausente em index.html")

        # 2. Controles granulares do Modo Foco
        ids_foco = [
            'id="btn-toggle-filtros-detalhados"',
            'id="painel-filtros-detalhados"',
            'id="select-composto-origem"',
            'id="select-composto-status"',
            'id="select-composto-especial"',
            'id="btn-aplicar-filtros-compostos"',
            'id="btn-resetar-filtros-compostos"'
        ]
        for id_foco in ids_foco:
            self.assertIn(id_foco, self.conteudo_html, f"Elemento '{id_foco}' ausente em index.html")

        # 3. Controles da Visão Geral
        ids_overview = [
            'id="badge-resumo-filtros-overview"',
            'id="btn-limpar-filtros-overview"',
            'id="btn-limpar-busca-overview"'
        ]
        for id_ov in ids_overview:
            self.assertIn(id_ov, self.conteudo_html, f"Elemento '{id_ov}' ausente em index.html")

        # 4. Classes CSS do Design System
        classes_filtro = [
            ".painel-filtros-compostos",
            ".grade-filtros-compostos",
            ".item-filtro-composto",
            ".rotulo-filtro-composto",
            ".campo-select-composto",
            ".grupos-filtros-compostos",
            ".linha-grupo-filtro",
            ".rotulo-grupo-filtro",
            ".filtros-pills-grupo",
            ".barra-resumo-filtros",
            ".badge-resumo-filtros"
        ]
        for cls in classes_filtro:
            self.assertIn(cls, self.conteudo_css, f"Classe '{cls}' ausente em estilos.css")

    def teste_elementos_relatorio_inteligente_e_nexus(self):
        """Valida que todos os controles, abas e classes do Relatório Inteligente e Gerador Nexus estão íntegros."""
        ids_obrigatorios = [
            'id="container-progresso-geral"',
            'id="btn-abrir-relatorio"',
            'id="modal-relatorio"',
            'id="btn-fechar-modal-relatorio"',
            'id="btn-aba-relatorio-metricas"',
            'id="btn-aba-relatorio-faltantes"',
            'id="btn-aba-relatorio-nexus"',
            'id="btn-atualizar-relatorio"',
            'id="relatorio-mod-pct-revisao"',
            'id="relatorio-novos-pct"',
            'id="relatorio-modificados-pct"',
            'id="relatorio-vanilla-oficial-pct"',
            'id="relatorio-geral-pct"',
            'id="select-relatorio-filtro-escopo"',
            'id="select-relatorio-filtro-status"',
            'id="select-relatorio-filtro-arquivo"',
            'id="select-relatorio-filtro-categoria"',
            'id="input-relatorio-busca-faltantes"',
            'id="btn-relatorio-aplicar-modo-foco"',
            'id="tabela-relatorio-faltantes-corpo"',
            'id="select-nexus-modelo"',
            'id="check-nexus-barras"',
            'id="btn-copiar-nexus-bbcode"',
            'id="container-nexus-preview"',
            'id="textarea-nexus-bbcode"'
        ]
        for id_el in ids_obrigatorios:
            self.assertIn(id_el, self.conteudo_html, f"Elemento '{id_el}' ausente em index.html")

        classes_css_esperadas = [
            ".progresso-clicavel",
            ".btn-destaque-relatorio",
            ".modal-extra-largo",
            ".relatorio-modal-corpo",
            ".relatorio-abas-nav",
            ".aba-botao",
            ".banner-escopo-explicativo",
            ".grade-cards-relatorio",
            ".card-relatorio",
            ".card-relatorio-destaque",
            ".barra-trilho-relatorio",
            ".barra-preenchimento-relatorio",
            ".badge-delta-novo",
            ".badge-delta-modificado",
            ".badge-delta-vanilla",
            ".tabela-relatorio",
            ".nexus-preview-caixa",
            ".nexus-bbcode-textarea"
        ]
        for classe_css in classes_css_esperadas:
            self.assertIn(classe_css, self.conteudo_css, f"Classe '{classe_css}' ausente em estilos.css")


if __name__ == "__main__":
    unittest.main()

