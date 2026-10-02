"""
Testes unitários para o módulo de empacotamento .PAK da engine Heaps.io (Shiro Games).
"""

import os
import struct
import tempfile
import unittest
import zlib
from nucleo.empacotador_pak import EmpacotadorPakHeaps


class TesteEmpacotadorPak(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.pasta_origem = os.path.join(self.temp_dir.name, "origem")
        self.pasta_lang = os.path.join(self.pasta_origem, "lang")
        os.makedirs(self.pasta_lang, exist_ok=True)

        self.conteudo_export = b"<export lang=\"pt-BR\"><sheet name=\"teste\"><t>Ola Mundo</t></sheet></export>"
        self.conteudo_texts = b"<texts lang=\"pt-BR\"><t id=\"1\">Texto Teste</t></texts>"

        with open(os.path.join(self.pasta_lang, "export_pt-BR.xml"), "wb") as f:
            f.write(self.conteudo_export)

        with open(os.path.join(self.pasta_lang, "texts_pt-BR.xml"), "wb") as f:
            f.write(self.conteudo_texts)

        self.caminho_pak_saida = os.path.join(self.temp_dir.name, "res2_teste.pak")

    def tearDown(self):
        self.temp_dir.cleanup()

    def teste_conformidade_cabecalho_heaps(self):
        info = EmpacotadorPakHeaps.empacotar_diretorio(self.pasta_origem, self.caminho_pak_saida)
        self.assertTrue(os.path.exists(self.caminho_pak_saida))
        self.assertEqual(info["quantidade_arquivos"], 2)

        tamanho_real = os.path.getsize(self.caminho_pak_saida)
        self.assertEqual(tamanho_real, info["tamanho_bytes"])

        with open(self.caminho_pak_saida, "rb") as f:
            # 1. Verificar cabeçalho de 18 bytes
            magica, data_offset, total_size, versao, num_pastas = struct.unpack("<4sIIHI", f.read(18))
            self.assertEqual(magica, b"PAK\x00")
            self.assertEqual(versao, 256)
            self.assertEqual(total_size, tamanho_real)
            self.assertGreater(data_offset, 18)

            # 2. Verificar marcador ASCII DATA exatamente antes do bloco de dados
            f.seek(data_offset - 4)
            marcador_data = f.read(4)
            self.assertEqual(marcador_data, b"DATA")

            # 3. Verificar integridade dos dados dos arquivos
            f.seek(data_offset)
            bloco_dados = f.read()
            self.assertIn(self.conteudo_export, bloco_dados)
            self.assertIn(self.conteudo_texts, bloco_dados)

    def teste_descompactar_pak_e_extrair_linguagem(self):
        # 1. Empacotar
        EmpacotadorPakHeaps.empacotar_diretorio(self.pasta_origem, self.caminho_pak_saida)

        # 2. Descompactar seletivamente linguagem
        pasta_destino = os.path.join(self.temp_dir.name, "extraidos")
        resultado = EmpacotadorPakHeaps.extrair_arquivos_linguagem(self.caminho_pak_saida, pasta_destino)

        self.assertEqual(resultado["total_extraidos"], 2)
        arq_export = os.path.join(pasta_destino, "lang", "export_pt-BR.xml")
        arq_texts = os.path.join(pasta_destino, "lang", "texts_pt-BR.xml")

        self.assertTrue(os.path.exists(arq_export))
        self.assertTrue(os.path.exists(arq_texts))

        with open(arq_export, "rb") as f:
            self.assertEqual(f.read(), self.conteudo_export)
        with open(arq_texts, "rb") as f:
            self.assertEqual(f.read(), self.conteudo_texts)


if __name__ == "__main__":
    unittest.main()
