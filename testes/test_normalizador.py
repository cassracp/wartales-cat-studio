"""
Testes unitários para o módulo normalizador e sanitização CastleDB.
"""

import unittest
from nucleo.normalizador import (
    normalizar_espacos,
    sanitizar_para_castledb,
    extrair_tokens_protegidos,
    gerar_hash_conteudo
)


class TesteNormalizador(unittest.TestCase):

    def teste_normalizar_espacos(self):
        entrada = "  Texto   com \n múltiplos   espaços e \t tabs.  "
        esperado = "Texto com múltiplos espaços e tabs."
        self.assertEqual(normalizar_espacos(entrada), esperado)
        self.assertEqual(normalizar_espacos(""), "")
        self.assertEqual(normalizar_espacos(None), "")

    def teste_sanitizar_castledb(self):
        # Caso clássico de crash assert cdb.Lang
        entrada_com_br = "<br/>Este é um texto que quebra o CastleDB se iniciar com quebra."
        esperado = "Este é um texto que quebra o CastleDB se iniciar com quebra."
        self.assertEqual(sanitizar_para_castledb(entrada_com_br), esperado)

        entrada_com_multiplos_br = " <br /> <br/> Texto após quebras"
        self.assertEqual(sanitizar_para_castledb(entrada_com_multiplos_br), "Texto após quebras")

        # Texto que tem <br/> no meio deve ser preservado!
        entrada_meio = "Primeira linha.<br/>Segunda linha."
        self.assertEqual(sanitizar_para_castledb(entrada_meio), entrada_meio)

    def teste_extrair_tokens_protegidos(self):
        texto = "Causa [DMG] de dano em ::target:: e recupera <good>+5</good> de vida usando $habilidade."
        tokens = extrair_tokens_protegidos(texto)
        self.assertIn("[DMG]", tokens)
        self.assertIn("::target::", tokens)
        self.assertIn("<good>", tokens)
        self.assertIn("</good>", tokens)
        self.assertIn("$habilidade", tokens)

    def teste_gerar_hash_conteudo(self):
        texto_a = "O bando descansou no acampamento."
        texto_b = "  o  bando  descansou   no acampamento.  "
        texto_c = "A tropa descansou no acampamento."

        # Case-insensitive e whitespace-insensitive para repetições
        self.assertEqual(gerar_hash_conteudo(texto_a), gerar_hash_conteudo(texto_b))
        self.assertNotEqual(gerar_hash_conteudo(texto_a), gerar_hash_conteudo(texto_c))


if __name__ == "__main__":
    unittest.main()
