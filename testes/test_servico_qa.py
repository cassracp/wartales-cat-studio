"""
Testes unitários para o módulo de Garantia de Qualidade (QA) e glossário.
"""

import os
import tempfile
import unittest
from nucleo.banco_dados import GerenciadorBancoDados
from nucleo.servico_glossario import ServicoGlossario
from nucleo.servico_qa import ServicoGarantiaQualidade


class TesteServicoQA(unittest.TestCase):

    def teste_validar_tags_ausentes(self):
        origem = "Ganha [DMG] e ::bonus:: pontos de vida."
        # Tradução onde o tradutor esqueceu o token ::bonus::
        traducao = "Ganha [DMG] e pontos de vida."

        res = ServicoGarantiaQualidade.validar_segmento(origem, traducao)
        self.assertFalse(res["valido"])
        self.assertTrue(res["tem_inconsistencia"])
        self.assertIn("::bonus::", res["tags_faltantes"])

    def teste_validar_alerta_castledb_br_inicio(self):
        origem = "Habilidade especial de combate."
        traducao_com_bug = "<br/>Habilidade especial de combate."

        res = ServicoGarantiaQualidade.validar_segmento(origem, traducao_com_bug)
        self.assertFalse(res["valido"])
        self.assertTrue(res["tem_inconsistencia"])
        self.assertTrue(any("Alerta CastleDB" in a for a in res["avisos"]))

    def teste_validar_tags_desbalanceadas(self):
        origem = "Aumenta <b>dano crítico</b>."
        traducao_errada = "Aumenta <b>dano crítico."

        res = ServicoGarantiaQualidade.validar_segmento(origem, traducao_errada)
        self.assertFalse(res["valido"])
        self.assertTrue(res["tem_inconsistencia"])
        self.assertTrue(any("Desbalanceamento" in a for a in res["avisos"]))

    def teste_validar_sinonimo_proibido_glossario(self):
        glossario = [
            {
                "termo_en": "Troop",
                "termo_pt_padrao": "Tropa",
                "sinonimos_proibidos": "bando, Grupo",
                "categoria": "Mecânica"
            }
        ]

        origem = "The troop is tired."
        traducao_com_sinonimo = "O bando está cansado."

        res = ServicoGarantiaQualidade.validar_segmento(origem, traducao_com_sinonimo, glossario)
        self.assertFalse(res["valido"])
        self.assertTrue(res["tem_inconsistencia"])
        self.assertTrue(any("Detectado uso do sinônimo não padronizado 'bando'" in a for a in res["avisos"]))


    def teste_substituicao_em_lote_preserva_status_pendente_e_reavalia_qa(self):
        """Valida que a substituição de sinônimo em lote NÃO aprova automaticamente itens pendentes e reavalia QA."""
        with tempfile.TemporaryDirectory() as temp_dir:
            caminho_banco = os.path.join(temp_dir, "teste_glossario_qa.db")
            banco = GerenciadorBancoDados(caminho_banco)
            servico_glossario = ServicoGlossario(banco)

            # Cadastrar termo oficial e sinônimo proibido
            banco.salvar_termo_glossario(
                termo_en="Troop",
                termo_pt_padrao="Tropa",
                sinonimos_proibidos="bando, Grupo",
                categoria="Mecânica"
            )

            # Segmento 1: Pendente com sinônimo 'bando'
            id1 = banco.salvar_segmento(
                arquivo="export_pt-BR.xml",
                tag_nome="name",
                chave_hierarquica="tropa.1",
                caminho_xml="tropa/1",
                vanilla_en="Troop",
                vanilla_pt="Tropa",
                mod_en="The troop arrives.",
                traducao_atual="O bando chega.",
                status="pendente",
                tem_inconsistencia=1,
                aviso_qa="Detectado uso do sinônimo não padronizado 'bando'"
            )

            # Segmento 2: Pendente com sinônimo 'bando' E tag desbalanceada <b>
            id2 = banco.salvar_segmento(
                arquivo="export_pt-BR.xml",
                tag_nome="name",
                chave_hierarquica="tropa.2",
                caminho_xml="tropa/2",
                vanilla_en="Troop",
                vanilla_pt="Tropa",
                mod_en="The troop is <b>strong</b>.",
                traducao_atual="O bando é <b>forte.",
                status="pendente",
                tem_inconsistencia=1,
                aviso_qa="Desbalanceamento da tag <b>"
            )

            # Segmento 3: Já Aprovado (revisado) pelo humano, com sinônimo 'bando'
            id3 = banco.salvar_segmento(
                arquivo="export_pt-BR.xml",
                tag_nome="name",
                chave_hierarquica="tropa.3",
                caminho_xml="tropa/3",
                vanilla_en="Troop",
                vanilla_pt="Tropa",
                mod_en="Elite troop.",
                traducao_atual="O bando de elite.",
                traducao_revisada="O bando de elite.",
                status="revisado",
                tem_inconsistencia=1,
                aviso_qa="Detectado uso do sinônimo não padronizado 'bando'"
            )

            # Executa a substituição em lote
            total = servico_glossario.substituir_sinonimo_em_lote("bando", "Tropa")
            self.assertEqual(total, 3)

            seg1 = banco.obter_segmento_por_id(id1)
            seg2 = banco.obter_segmento_por_id(id2)
            seg3 = banco.obter_segmento_por_id(id3)

            # 1. Segmento 1 deve ter sido corrigido, mas CONTINUAR 'pendente' (não aprovado automaticamente!)
            self.assertIn("tropa", seg1["traducao_revisada"].lower())
            self.assertEqual(seg1["status"], "pendente", "Segmento pendente NÃO deve se tornar 'revisado' após substituição de termo!")
            self.assertEqual(seg1["tem_inconsistencia"], 0, "Inconsistência resolvida deve zerar a flag")
            self.assertEqual(seg1["aviso_qa"], "")

            # 2. Segmento 2 deve ter sido corrigido, continuar 'pendente', mas MANTER flag de inconsistência por causa da tag <b> desbalanceada!
            self.assertIn("tropa", seg2["traducao_revisada"].lower())
            self.assertEqual(seg2["status"], "pendente")
            self.assertEqual(seg2["tem_inconsistencia"], 1, "Inconsistência da tag <b> deve permanecer detectada")
            self.assertIn("Desbalanceamento", seg2["aviso_qa"])

            # 3. Segmento 3 era 'revisado' e deve CONTINUAR 'revisado'
            self.assertIn("tropa", seg3["traducao_revisada"].lower())
            self.assertEqual(seg3["status"], "revisado", "Segmento previamente aprovado deve preservar seu status revisado")
            self.assertEqual(seg3["tem_inconsistencia"], 0)


if __name__ == "__main__":
    unittest.main()
