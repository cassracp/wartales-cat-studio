"""
Testes unitários para o Gerenciador de Projetos Agnóstico a Mods e Memória Global Cross-Mod.
"""

import os
import json
import tempfile
import unittest
from nucleo.memoria_global import MemoriaTraducaoGlobal
from nucleo.gerenciador_projetos import GerenciadorProjetos
from nucleo.tradutor_lote_ia import MotorTraducaoLoteIA
from nucleo.normalizador import gerar_hash_conteudo, normalizar_espacos


class TesteGerenciadorProjetosEMemoriaGlobal(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.diretorio_base = self.temp_dir.name

        # Inicializar memória global no diretório temporário
        caminho_tm_db = os.path.join(self.diretorio_base, "tm_global_teste.db")
        self.memoria_global = MemoriaTraducaoGlobal(caminho_tm_db)

        # Inicializar gerenciador de projetos com arquivo de configuração temporário
        caminho_config = os.path.join(self.diretorio_base, "config_teste.json")
        self.gerenciador = GerenciadorProjetos(caminho_configuracao=caminho_config)

    def tearDown(self):
        del self.gerenciador
        del self.memoria_global
        self.temp_dir.cleanup()

    def teste_memoria_global_salvar_e_buscar(self):
        """Testa inserção e recuperação de termos na Memória Global Cross-Mod."""
        sucesso = self.memoria_global.salvar_traducao(
            texto_origem="Iron Sword",
            texto_traducao="Espada de Ferro",
            origem_mod="wartales-remastered"
        )
        self.assertTrue(sucesso)

        resultado = self.memoria_global.buscar_traducao("Iron Sword")
        self.assertEqual(resultado, "Espada de Ferro")

        dicionario = self.memoria_global.carregar_dicionario_completo()
        hash_termo = gerar_hash_conteudo(normalizar_espacos("Iron Sword"))
        self.assertIn(hash_termo, dicionario)
        self.assertEqual(dicionario[hash_termo], "Espada de Ferro")

        stats = self.memoria_global.obter_estatisticas()
        self.assertEqual(stats["total_pares"], 1)

        # Testar remoção ao desfazer aprovação
        removido = self.memoria_global.remover_traducao("Iron Sword")
        self.assertTrue(removido)
        self.assertIsNone(self.memoria_global.buscar_traducao("Iron Sword"))
        stats_pos = self.memoria_global.obter_estatisticas()
        self.assertEqual(stats_pos["total_pares"], 0)

    def teste_memoria_global_salvar_lote(self):
        """Testa salvar múltiplos itens em transação atômica."""
        itens = [
            {"en": "Leather Armor", "pt": "Armadura de Couro"},
            {"en": "Steel Ingot", "pt": "Lingote de Aço"},
        ]
        total_salvo = self.memoria_global.salvar_lote(itens, origem_mod="mod_teste")
        self.assertEqual(total_salvo, 2)

        stats = self.memoria_global.obter_estatisticas()
        self.assertEqual(stats["total_pares"], 2)

    def teste_criacao_e_listagem_de_projetos(self):
        """Testa a criação de um novo projeto isolado e a listagem de mods."""
        projeto_info = self.gerenciador.criar_projeto(
            nome="Wartales Expanded",
            descricao="Mod que expande as regiões e itens"
        )

        self.assertEqual(projeto_info["slug"], "wartales_expanded")
        self.assertTrue(os.path.exists(projeto_info["diretorio_mod_en_abs"]))
        self.assertTrue(os.path.exists(projeto_info["diretorio_traducao_ia_abs"]))

        projetos = self.gerenciador.listar_projetos()
        slugs = [p["slug"] for p in projetos]
        self.assertIn("wartales_expanded", slugs)

    def teste_ativar_projeto(self):
        """Testa a ativação dinâmica de um mod."""
        self.gerenciador.criar_projeto("Mod Teste 1")
        self.gerenciador.criar_projeto("Mod Teste 2")

        projeto_ativo = self.gerenciador.definir_projeto_ativo("mod_teste_2")
        self.assertEqual(projeto_ativo["slug"], "mod_teste_2")

        # Verificar se persistiu na configuração
        with open(self.gerenciador.caminho_configuracao, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        self.assertEqual(cfg.get("projeto_ativo"), "mod_teste_2")

    def teste_verificar_arquivos_vanilla(self):
        """Testa a validação de existência dos 4 arquivos do jogo base."""
        # Configurar pasta vanilla isolada no diretório temporário
        pasta_vanilla_teste = os.path.join(self.diretorio_base, "vanilla_teste")
        os.makedirs(pasta_vanilla_teste, exist_ok=True)
        self.gerenciador.config["diretorio_referencia_vanilla"] = pasta_vanilla_teste

        # Inicialmente vazia
        info = self.gerenciador.verificar_arquivos_vanilla()
        self.assertFalse(info["completo"])

        # Criar os 4 arquivos na pasta vanilla
        pasta_vanilla = info["diretorio_vanilla"]
        arquivos = [
            "export_en.xml",
            "texts_en.xml",
            "export_pt-BR.xml",
            "texts_pt-BR.xml"
        ]
        for arq in arquivos:
            with open(os.path.join(pasta_vanilla, arq), "w", encoding="utf-8") as f:
                f.write("<texts></texts>")

        info_atualizada = self.gerenciador.verificar_arquivos_vanilla()
        self.assertTrue(info_atualizada["completo"])

    def teste_analise_deltas_motor_ia(self):
        """Testa o isolamento de deltas entre mod, vanilla e memória global."""
        # 1. Alimentar a memória global temporária
        self.memoria_global.salvar_traducao("Magic Wand", "Varinha Mágica", "mod_antigo")

        # 2. Criar pastas mock para Vanilla e Mod
        pasta_vanilla = os.path.join(self.diretorio_base, "vanilla_mock")
        pasta_mod = os.path.join(self.diretorio_base, "mod_mock")
        os.makedirs(pasta_vanilla, exist_ok=True)
        os.makedirs(pasta_mod, exist_ok=True)

        conteudo_vanilla_en = '<texts><t id="1">Dagger</t><t id="2">Shield</t></texts>'
        conteudo_vanilla_pt = '<texts><t id="1">Adaga</t><t id="2">Escudo</t></texts>'
        conteudo_mod_en = '<texts><t id="1">Dagger</t><t id="2">Shield</t><t id="3">Magic Wand</t><t id="4">New Boss</t></texts>'

        conteudo_export = '<export><sheet name="items"><item><name>Potion</name></item></sheet></export>'

        with open(os.path.join(pasta_vanilla, "texts_en.xml"), "w", encoding="utf-8") as f:
            f.write(conteudo_vanilla_en)
        with open(os.path.join(pasta_vanilla, "texts_pt-BR.xml"), "w", encoding="utf-8") as f:
            f.write(conteudo_vanilla_pt)
        with open(os.path.join(pasta_vanilla, "export_en.xml"), "w", encoding="utf-8") as f:
            f.write(conteudo_export)
        with open(os.path.join(pasta_vanilla, "export_pt-BR.xml"), "w", encoding="utf-8") as f:
            f.write(conteudo_export)

        with open(os.path.join(pasta_mod, "texts_en.xml"), "w", encoding="utf-8") as f:
            f.write(conteudo_mod_en)
        with open(os.path.join(pasta_mod, "export_en.xml"), "w", encoding="utf-8") as f:
            f.write(conteudo_export)

        motor = MotorTraducaoLoteIA(memoria_global=self.memoria_global)
        relatorio = motor.analisar_deltas(
            diretorio_vanilla=pasta_vanilla,
            diretorio_mod_en=pasta_mod
        )

        self.assertEqual(relatorio["total_texts"], 4)
        self.assertEqual(relatorio["total_export"], 1)
        # 1 e 2 reaproveitados do Vanilla + export reaproveitado = 3 oficiais
        self.assertEqual(relatorio["reaproveitamento_oficial"], 3)
        # Magic Wand reaproveitado da Memória Global (id 3)
        self.assertEqual(relatorio["reaproveitamento_tm_global"], 1)
        # New Boss é o único que precisa da IA (id 4)
        self.assertEqual(relatorio["necessita_ia"], 1)


if __name__ == "__main__":
    unittest.main()
