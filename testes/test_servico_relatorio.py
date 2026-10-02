"""
Testes unitários e de integração para o ServicoRelatorio e estatísticas inteligentes.
Valida a separação precisa entre o escopo do Mod e o jogo base (Vanilla),
cálculo de porcentagens e geração de textos BBCode para o Nexus Mods.
"""

import os
import shutil
import tempfile
import unittest

from nucleo.banco_dados import GerenciadorBancoDados
from nucleo.servico_relatorio import ServicoRelatorio


class TesteServicoRelatorio(unittest.TestCase):

    def setUp(self):
        self.diretorio_temp = tempfile.mkdtemp()
        self.caminho_banco = os.path.join(self.diretorio_temp, "teste_relatorio.db")
        self.banco = GerenciadorBancoDados(self.caminho_banco)
        self.servico_relatorio = ServicoRelatorio()

    def tearDown(self):
        shutil.rmtree(self.diretorio_temp, ignore_errors=True)

    def teste_gerar_barra_progresso_bbcode(self):
        """Valida que as barras visuais de progresso em BBCode usem blocos Unicode e cores corretas."""
        # 1. 0%
        barra_zero = ServicoRelatorio.gerar_barra_progresso_bbcode(0.0, tamanho=10)
        self.assertEqual(barra_zero, "[color=#555555]░░░░░░░░░░[/color]")

        # 2. 100%
        barra_cem = ServicoRelatorio.gerar_barra_progresso_bbcode(100.0, tamanho=10)
        self.assertEqual(barra_cem, "[color=#4caf50]██████████[/color]")

        # 3. 50% (faixa média - azul)
        barra_cinquenta = ServicoRelatorio.gerar_barra_progresso_bbcode(50.0, tamanho=10)
        self.assertIn("█████", barra_cinquenta)
        self.assertIn("░░░░░", barra_cinquenta)
        self.assertIn("#2196f3", barra_cinquenta)

        # 4. 20% (faixa baixa - laranja)
        barra_vinte = ServicoRelatorio.gerar_barra_progresso_bbcode(20.0, tamanho=10)
        self.assertIn("██", barra_vinte)
        self.assertIn("░░░░░░░░", barra_vinte)
        self.assertIn("#ff9800", barra_vinte)

        # 5. Limites extremos (< 0 e > 100)
        barra_negativa = ServicoRelatorio.gerar_barra_progresso_bbcode(-15.0, tamanho=10)
        self.assertEqual(barra_negativa, barra_zero)
        barra_super = ServicoRelatorio.gerar_barra_progresso_bbcode(150.0, tamanho=10)
        self.assertEqual(barra_super, barra_cem)

    def teste_obter_relatorio_completo_com_deltas(self):
        """
        Valida que o relatório diferencie com exatidão o escopo do Mod
        (termos novos e modificados) dos termos do jogo base (Vanilla).
        """
        # Inserir conjunto representativo:
        # 1. Vanilla inalterado (Jogo base): 3 frases
        self.banco.salvar_segmento(
            arquivo="export_pt-BR.xml",
            tag_nome="cell",
            chave_hierarquica="itens/sword_01",
            caminho_xml="/itens/1",
            vanilla_en="Iron Sword",
            vanilla_pt="Espada de Ferro",
            mod_en="Iron Sword",
            traducao_atual="Espada de Ferro",
            status="pendente"
        )
        self.banco.salvar_segmento(
            arquivo="export_pt-BR.xml",
            tag_nome="cell",
            chave_hierarquica="itens/shield_01",
            caminho_xml="/itens/2",
            vanilla_en="Wooden Shield",
            vanilla_pt="Escudo de Madeira",
            mod_en="Wooden Shield",
            traducao_atual="Escudo de Madeira",
            status="pendente"
        )
        self.banco.salvar_segmento(
            arquivo="texts_pt-BR.xml",
            tag_nome="t",
            chave_hierarquica="dialogo_padrao",
            caminho_xml="/texts/1",
            vanilla_en="Hello mercenary",
            vanilla_pt="Olá mercenário",
            mod_en="Hello mercenary",
            traducao_atual="Olá mercenário",
            status="pendente"
        )

        # 2. Termos Novos do Mod (vanilla_en vazio ou None): 2 frases (1 revisada, 1 pendente com IA)
        self.banco.salvar_segmento(
            arquivo="export_pt-BR.xml",
            tag_nome="cell",
            chave_hierarquica="skills/mod_nova_skill_1",
            caminho_xml="/skills/100",
            vanilla_en=None,
            vanilla_pt=None,
            mod_en="Berserker Rage",
            traducao_atual="Fúria do Berserker",
            traducao_revisada="Fúria Selvagem do Berserker",
            status="revisado"
        )
        self.banco.salvar_segmento(
            arquivo="export_pt-BR.xml",
            tag_nome="cell",
            chave_hierarquica="skills/mod_nova_skill_2",
            caminho_xml="/skills/101",
            vanilla_en="",
            vanilla_pt="",
            mod_en="Blood Feast",
            traducao_atual="Banquete de Sangue",
            status="pendente"
        )

        # 3. Termos Modificados pelo Mod (vanilla_en != mod_en): 2 frases (1 revisada, 1 pendente)
        self.banco.salvar_segmento(
            arquivo="export_pt-BR.xml",
            tag_nome="cell",
            chave_hierarquica="itens/axe_rebalance",
            caminho_xml="/itens/3",
            vanilla_en="Heavy Axe deals 15 damage",
            vanilla_pt="Machado Pesado causa 15 de dano",
            mod_en="Heavy Axe deals 22 damage and bleeds",
            traducao_atual="Machado Pesado causa 22 de dano e sangramento",
            traducao_revisada="Machado Pesado inflige 22 de dano e sangra o alvo",
            status="revisado"
        )
        self.banco.salvar_segmento(
            arquivo="texts_pt-BR.xml",
            tag_nome="t",
            chave_hierarquica="ui_rebalance",
            caminho_xml="/texts/2",
            vanilla_en="Critical Hit Chance: 5%",
            vanilla_pt="Chance de Acerto Crítico: 5%",
            mod_en="Critical Strike Rating: +12%",
            traducao_atual="Taxa de Golpe Crítico: +12%",
            status="pendente"
        )

        # Total no Banco: 3 vanilla + 2 novos + 2 modificados = 7 segmentos
        # Escopo Real do Mod: 2 novos + 2 modificados = 4 segmentos
        # Revisados do Mod: 1 novo + 1 modificado = 2 de 4 (50.0% do Mod!)
        # Revisados no Total Geral: 2 de 7 = 28.6%
        relatorio = self.servico_relatorio.obter_relatorio_completo(self.banco)

        # Validações do Escopo do Mod
        self.assertEqual(relatorio["mod"]["total"], 4)
        self.assertEqual(relatorio["mod"]["revisados"], 2)
        self.assertEqual(relatorio["mod"]["pendentes"], 2)
        self.assertEqual(relatorio["mod"]["com_traducao"], 4)
        self.assertEqual(relatorio["mod"]["porcentagem_revisao"], 50.0)
        self.assertEqual(relatorio["mod"]["porcentagem_traducao"], 100.0)

        # Validações de Termos Novos
        self.assertEqual(relatorio["novos"]["total"], 2)
        self.assertEqual(relatorio["novos"]["revisados"], 1)
        self.assertEqual(relatorio["novos"]["pendentes"], 1)
        self.assertEqual(relatorio["novos"]["porcentagem_revisao"], 50.0)

        # Validações de Termos Modificados
        self.assertEqual(relatorio["modificados"]["total"], 2)
        self.assertEqual(relatorio["modificados"]["revisados"], 1)
        self.assertEqual(relatorio["modificados"]["pendentes"], 1)
        self.assertEqual(relatorio["modificados"]["porcentagem_revisao"], 50.0)

        # Validações do Jogo Base Vanilla
        self.assertEqual(relatorio["vanilla"]["total"], 3)
        self.assertEqual(relatorio["vanilla"]["com_pt_oficial"], 3)
        self.assertEqual(relatorio["vanilla"]["porcentagem_oficial"], 100.0)

        # Validações do Geral
        self.assertEqual(relatorio["geral"]["total"], 7)
        self.assertEqual(relatorio["geral"]["revisados"], 2)
        self.assertEqual(relatorio["geral"]["porcentagem_revisao"], 28.6)

        # Validações por Arquivo
        arqs = {a["arquivo"]: a for a in relatorio["arquivos"]}
        self.assertIn("export_pt-BR.xml", arqs)
        self.assertIn("texts_pt-BR.xml", arqs)
        self.assertEqual(arqs["export_pt-BR.xml"]["mod_total"], 3)
        self.assertEqual(arqs["texts_pt-BR.xml"]["mod_total"], 1)

    def teste_gerar_texto_nexus_modelos(self):
        """Valida a geração de posts para o Nexus Mods nos modelos de Devlog, Descrição Completa e Compacto."""
        dados_simulados = {
            "projeto": {"nome": "Wartales Remastered", "versao": "v7.40", "autor": "Cassr"},
            "mod": {
                "total": 6118,
                "revisados": 4800,
                "pendentes": 1318,
                "com_traducao": 5900,
                "porcentagem_revisao": 78.5,
                "porcentagem_traducao": 96.4
            },
            "novos": {
                "total": 2383,
                "revisados": 2000,
                "pendentes": 383,
                "com_traducao": 2300,
                "porcentagem_revisao": 83.9,
                "porcentagem_traducao": 96.5
            },
            "modificados": {
                "total": 3735,
                "revisados": 2800,
                "pendentes": 935,
                "com_traducao": 3600,
                "porcentagem_revisao": 75.0,
                "porcentagem_traducao": 96.4
            },
            "vanilla": {
                "total": 26228,
                "com_pt_oficial": 26228,
                "porcentagem_oficial": 100.0
            },
            "geral": {
                "total": 32346,
                "revisados": 4800,
                "porcentagem_revisao": 14.8
            },
            "arquivos": [
                {
                    "arquivo": "export_pt-BR.xml",
                    "rotulo_amigavel": "CastleDB",
                    "mod_total": 5777,
                    "mod_com_traducao": 5560,
                    "porcentagem_traducao_mod": 96.2
                }
            ]
        }

        # 1. Modelo Atualização / Devlog
        post_atualizacao = self.servico_relatorio.gerar_texto_nexus(dados_simulados, {"modelo": "atualizacao"})
        bbcode_at = post_atualizacao["bbcode"]
        self.assertIn("[size=5][b][color=#4caf50]⚔️ Wartales Remastered - Andamento da Tradução PT-BR[/color][/b][/size]", bbcode_at)
        self.assertIn("res2.pak", bbcode_at)
        self.assertIn("CastleDB", bbcode_at)
        self.assertIn("78.5%", bbcode_at)
        self.assertIn("96.4%", bbcode_at)
        self.assertIn("<h3 class=\"nexus-preview-h3\">", post_atualizacao["html_preview"])

        # 2. Modelo Descrição Completa da Página
        post_desc = self.servico_relatorio.gerar_texto_nexus(dados_simulados, {"modelo": "descricao"})
        bbcode_desc = post_desc["bbcode"]
        self.assertIn("Destaques da Tradução", bbcode_desc)
        self.assertIn("Instalação Simples", bbcode_desc)
        self.assertIn("100% Preservados", bbcode_desc)

        # 3. Modelo Compacto / Badge
        post_compacto = self.servico_relatorio.gerar_texto_nexus(dados_simulados, {"modelo": "compacto"})
        bbcode_comp = post_compacto["bbcode"]
        self.assertIn("TRADUÇÃO PT-BR - Wartales Remastered v7.40", bbcode_comp)

    def teste_banco_vazio(self):
        """Valida que o serviço lide graciosamente com banco de dados vazio sem divisão por zero."""
        relatorio = self.servico_relatorio.obter_relatorio_completo(self.banco)
        self.assertEqual(relatorio["mod"]["total"], 0)
        self.assertEqual(relatorio["mod"]["porcentagem_revisao"], 0.0)
        self.assertEqual(relatorio["geral"]["total"], 0)
        self.assertEqual(relatorio["geral"]["porcentagem_revisao"], 0.0)

        post = self.servico_relatorio.gerar_texto_nexus(relatorio)
        self.assertIn("0.0%", post["bbcode"])
        self.assertIsNotNone(post["html_preview"])

    def teste_formatar_numero_br(self):
        """Valida que a formatação numérica use o padrão brasileiro de milhares com ponto."""
        self.assertEqual(ServicoRelatorio.formatar_numero_br(26228), "26.228")
        self.assertEqual(ServicoRelatorio.formatar_numero_br(6118), "6.118")
        self.assertEqual(ServicoRelatorio.formatar_numero_br(1000000), "1.000.000")
        self.assertEqual(ServicoRelatorio.formatar_numero_br(0), "0")
        self.assertEqual(ServicoRelatorio.formatar_numero_br(None), "0")
        self.assertEqual(ServicoRelatorio.formatar_numero_br("5432"), "5.432")
        self.assertEqual(ServicoRelatorio.formatar_numero_br("invalido"), "0")

    def teste_converter_bbcode_para_html(self):
        """Valida a conversão precisa de tags BBCode para HTML e sanitização de URLs contra XSS."""
        # 1. Títulos e cabeçalhos
        html_h3 = ServicoRelatorio.converter_bbcode_para_html("[size=5]Título Grande[/size]")
        self.assertIn('<h3 class="nexus-preview-h3">Título Grande</h3>', html_h3)

        html_h4 = ServicoRelatorio.converter_bbcode_para_html("[size=4]Subtítulo[/size]")
        self.assertIn('<h4 class="nexus-preview-h4">Subtítulo</h4>', html_h4)

        # 2. Cores e formatação de texto
        html_cor = ServicoRelatorio.converter_bbcode_para_html("[color=#4caf50][b]Verde Negrito[/b][/color]")
        self.assertIn('style="color: #4caf50;', html_cor)
        self.assertIn('<strong>Verde Negrito</strong>', html_cor)

        html_format = ServicoRelatorio.converter_bbcode_para_html("[i]Itálico[/i] e [u]Sublinhado[/u]")
        self.assertIn('<em>Itálico</em>', html_format)
        self.assertIn('<u>Sublinhado</u>', html_format)

        # 3. Alinhamento, blocos de código e citações
        html_centro = ServicoRelatorio.converter_bbcode_para_html("[center]Centralizado[/center]")
        self.assertIn('<div style="text-align: center;">Centralizado</div>', html_centro)

        html_codigo = ServicoRelatorio.converter_bbcode_para_html("[code]res2.pak[/code]")
        self.assertIn('<pre class="nexus-preview-code"><code>res2.pak</code></pre>', html_codigo)

        html_citacao = ServicoRelatorio.converter_bbcode_para_html("[quote]Citação de status[/quote]")
        self.assertIn('<div class="nexus-preview-quote">Citação de status</div>', html_citacao)

        # 4. Links seguros e proteção contra XSS
        html_link = ServicoRelatorio.converter_bbcode_para_html("[url=https://nexusmods.com]Nexus[/url]")
        self.assertIn('href="https://nexusmods.com"', html_link)
        self.assertIn('rel="noopener noreferrer"', html_link)

        html_link_direto = ServicoRelatorio.converter_bbcode_para_html("[url]https://nexusmods.com/wartales[/url]")
        self.assertIn('href="https://nexusmods.com/wartales"', html_link_direto)

        # Proteção contra pseudoprotocolo javascript:
        html_xss = ServicoRelatorio.converter_bbcode_para_html("[url=javascript:alert('xss')]Ataque[/url]")
        self.assertNotIn('href="javascript:', html_xss)
        self.assertIn('href="#"', html_xss)

    def teste_gerar_texto_nexus_toggles_e_opcoes(self):
        """Valida que todas as opções de inclusão/exclusão sejam respeitadas em todos os modelos."""
        dados = {
            "projeto": {"nome": "Mod Teste", "versao": "v1.0", "autor": "Tester"},
            "mod": {"total": 100, "revisados": 40, "pendentes": 60, "com_traducao": 80, "porcentagem_revisao": 40.0, "porcentagem_traducao": 80.0},
            "novos": {"total": 50, "revisados": 20, "pendentes": 30, "com_traducao": 40, "porcentagem_revisao": 40.0, "porcentagem_traducao": 80.0},
            "modificados": {"total": 50, "revisados": 20, "pendentes": 30, "com_traducao": 40, "porcentagem_revisao": 40.0, "porcentagem_traducao": 80.0},
            "vanilla": {"total": 1000, "com_pt_oficial": 1000, "porcentagem_oficial": 100.0},
            "geral": {"total": 1100, "revisados": 40, "porcentagem_revisao": 3.6},
            "arquivos": [{"arquivo": "export_pt-BR.xml", "rotulo_amigavel": "CastleDB", "mod_total": 100, "mod_com_traducao": 80, "porcentagem_traducao_mod": 80.0}]
        }

        # Desativar todas as seções opcionais no modelo Devlog
        opcoes_desativadas = {
            "modelo": "atualizacao",
            "incluir_barras_progresso": False,
            "incluir_detalhes_escopo": False,
            "incluir_detalhes_arquivos": False,
            "incluir_castledb": False,
            "incluir_instalacao": False,
            "incluir_feedback": False
        }
        res_desativado = self.servico_relatorio.gerar_texto_nexus(dados, opcoes_desativadas)
        bbcode = res_desativado["bbcode"]
        self.assertNotIn("BARRAS DE PROGRESSO DO MOD", bbcode)
        self.assertNotIn("Raio-X dos Termos", bbcode)
        self.assertNotIn("Andamento por Arquivo", bbcode)
        self.assertNotIn("Estabilidade e Integridade CastleDB", bbcode)
        self.assertNotIn("Como Instalar", bbcode)
        self.assertNotIn("Feedback e Sugestões", bbcode)

        # Validar no modelo compacto com toggles ativados
        opcoes_compacto_completo = {
            "modelo": "compacto",
            "incluir_barras_progresso": True,
            "incluir_detalhes_escopo": True,
            "incluir_detalhes_arquivos": True,
            "incluir_castledb": True,
            "incluir_instalacao": True,
            "incluir_feedback": True
        }
        res_compacto = self.servico_relatorio.gerar_texto_nexus(dados, opcoes_compacto_completo)
        bbcode_comp = res_compacto["bbcode"]
        self.assertIn("CastleDB Validado", bbcode_comp)
        self.assertIn("Instalação: Copie res2.pak", bbcode_comp)
        self.assertIn("Comente na aba Posts", bbcode_comp)
        self.assertIn("Arquivos: export_pt-BR.xml", bbcode_comp)


if __name__ == "__main__":
    unittest.main()
