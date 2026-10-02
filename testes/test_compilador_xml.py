"""
Testes unitários para o compilador de XML e conformidade CastleDB.
"""

import os
import shutil
import tempfile
import unittest
from nucleo.banco_dados import GerenciadorBancoDados
from exportadores.compilador_xml import CompiladorXml


class TesteCompiladorXml(unittest.TestCase):
    """Testa a compilação e integridade de XMLs para CastleDB."""

    def setUp(self):
        self.diretorio_temp = tempfile.mkdtemp()
        self.caminho_banco = os.path.join(self.diretorio_temp, "teste_cat.db")
        self.banco = GerenciadorBancoDados(self.caminho_banco)
        self.compilador = CompiladorXml(self.banco)

    def tearDown(self):
        shutil.rmtree(self.diretorio_temp, ignore_errors=True)

    def teste_compilar_texts_xml_e_validar_conformidade(self):
        caminho_template_txt = os.path.join(self.diretorio_temp, "texts_en.xml")
        caminho_saida_txt = os.path.join(self.diretorio_temp, "texts_pt-BR.xml")

        conteudo_en = (
            '<texts lang="en">\n'
            '    <t id="item_espada">Iron Sword</t>\n'
            '    <g id="missoes">\n'
            '        <t _id="missao_1">Save the troop</t>\n'
            '    </g>\n'
            '</texts>'
        )
        with open(caminho_template_txt, "w", encoding="utf-8") as f:
            f.write(conteudo_en)

        # Inserir traduções no banco
        self.banco.salvar_segmento(
            arquivo="texts_pt-BR.xml",
            tag_nome="t",
            chave_hierarquica="item_espada",
            caminho_xml="item_espada",
            vanilla_en="Iron Sword",
            vanilla_pt="Espada de Ferro",
            mod_en="Iron Sword",
            traducao_atual="Espada de Ferro",
            traducao_revisada="Espada de Ferro Impecável",
            status="revisado"
        )
        self.banco.salvar_segmento(
            arquivo="texts_pt-BR.xml",
            tag_nome="t",
            chave_hierarquica="missoes.missao_1",
            caminho_xml="missoes.missao_1",
            vanilla_en="Save the troop",
            vanilla_pt="Salvar a tropa",
            mod_en="Save the troop",
            traducao_atual="Salvar a tropa",
            traducao_revisada="Salve a tropa de mercenários",
            status="revisado"
        )

        res = self.compilador.compilar_texts_xml(caminho_template_txt, caminho_saida_txt)
        self.assertTrue(os.path.exists(caminho_saida_txt))
        self.assertEqual(res["total_substituidos"], 2)

        with open(caminho_saida_txt, "r", encoding="utf-8") as f:
            conteudo_gerado = f.read()

        self.assertIn("Espada de Ferro Impecável", conteudo_gerado)
        self.assertIn("Salve a tropa de mercenários", conteudo_gerado)
        self.assertIn('lang="pt-BR"', conteudo_gerado)

    def teste_compilar_export_xml_com_sanitizacao_tags(self):
        caminho_template_exp = os.path.join(self.diretorio_temp, "export_en.xml")
        caminho_saida_exp = os.path.join(self.diretorio_temp, "export_pt-BR.xml")

        conteudo_en = (
            '<cdb lang="en">\n'
            '    <sheet name="habilidades">\n'
            '        <linha>\n'
            '            <nome>Slash</nome>\n'
            '            <descricao>Deals 10 dmg</descricao>\n'
            '        </linha>\n'
            '    </sheet>\n'
            '</cdb>'
        )
        with open(caminho_template_exp, "w", encoding="utf-8") as f:
            f.write(conteudo_en)

        self.banco.salvar_segmento(
            arquivo="export_pt-BR.xml",
            tag_nome="nome",
            chave_hierarquica="habilidades/linha/nome",
            caminho_xml="habilidades/linha/nome",
            vanilla_en="Slash",
            vanilla_pt="Golpe",
            mod_en="Slash",
            traducao_atual="Golpe Cortante",
            status="revisado"
        )
        self.banco.salvar_segmento(
            arquivo="export_pt-BR.xml",
            tag_nome="descricao",
            chave_hierarquica="habilidades/linha/descricao",
            caminho_xml="habilidades/linha/descricao",
            vanilla_en="Deals 10 dmg",
            vanilla_pt="Causa 10 dano",
            mod_en="Deals 10 dmg",
            traducao_atual="<br/>Causa <b>10</b> de dano &amp; sangramento",
            status="revisado"
        )

        res = self.compilador.compilar_export_xml(caminho_template_exp, caminho_saida_exp)
        self.assertTrue(os.path.exists(caminho_saida_exp))
        self.assertEqual(res["total_substituidos"], 2)

        conf = self.compilador.validar_conformidade(
            caminho_orig_exp=caminho_template_exp,
            caminho_pt_exp=caminho_saida_exp,
            caminho_orig_txt="",
            caminho_pt_txt=""
        )
        self.assertTrue(conf["valido"])
        self.assertEqual(conf["divergencias_export"], 0)


if __name__ == "__main__":
    unittest.main()
