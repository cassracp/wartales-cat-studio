import unittest
from unittest.mock import MagicMock
from nucleo.aplicador_glossario_ia import AplicadorGlossarioIA
from nucleo.servico_ia import ServicoIA

TERMOS = [
    {"termo_en": "Camp", "termo_pt_padrao": "Acampamento", "sinonimos_proibidos": "Campo, Base", "notas": ""},
    {"termo_en": "Camp Fire", "termo_pt_padrao": "Fogueira", "sinonimos_proibidos": "", "notas": ""},
]


class TestesAplicadorGlossarioIA(unittest.TestCase):
    def setUp(self):
        self.aplicador = AplicadorGlossarioIA.de_lista(TERMOS)

    def test_seleciona_plural_e_ignora_termo_coberto(self):
        self.assertEqual([t["termo_en"] for t in self.aplicador.selecionar_termos("Build Camps")], ["Camp"])
        self.assertEqual([t["termo_en"] for t in self.aplicador.selecionar_termos("A Camp Fire")], ["Camp Fire"])
        self.assertEqual(self.aplicador.selecionar_termos("Campaign"), [])

    def test_prompt_contem_glossario(self):
        instrucoes = self.aplicador.montar_instrucoes(TERMOS[:1])
        self.assertIn('"Camp" => "Acampamento"', instrucoes)
        self.assertIn("PROIBIDO usar: Campo, Base", instrucoes)

    def test_verificacao(self):
        termos = TERMOS[:1]
        self.assertTrue(self.aplicador.verificar("Monte o Acampamento", termos).conforme)
        self.assertFalse(self.aplicador.verificar("Monte o Campo", termos).conforme)
        self.assertFalse(self.aplicador.verificar("Monte o local", termos).conforme)

    def test_servico_refaz_quando_viola(self):
        pool = MagicMock()
        pool.executar_traducao.side_effect = [
            {"sucesso": True, "traducao": "Monte o Campo"},
            {"sucesso": True, "traducao": "Monte o Acampamento"},
        ]
        r = ServicoIA(gerenciador_pool=pool, aplicador_glossario=self.aplicador).traduzir_texto("Build the Camp")
        self.assertEqual(pool.executar_traducao.call_count, 2)
        self.assertTrue(r["glossario"]["conforme"])
        self.assertEqual(r["traducao"], "Monte o Acampamento")


if __name__ == "__main__":
    unittest.main()
