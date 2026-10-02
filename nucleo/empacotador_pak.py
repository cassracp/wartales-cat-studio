"""
Módulo de empacotamento oficial para arquivos .PAK da engine Heaps.io (Shiro Games).
Respeita rigorosamente a especificação do motor e do CastleDB:
- Assinatura mágica: 'PAK\\0'
- Cabeçalho global de 18 bytes
- Árvore de nós com CRC32 para cada arquivo
- Marcador ASCII obrigatório de 4 bytes 'DATA' imediatamente antes do bloco de dados
- Offsets relativos ao DataOffset
"""

import io
import os
import struct
import zlib
from typing import Any, Dict, List


class EmpacotadorPakHeaps:
    """Empacotador em conformidade estrita com o formato .PAK da Shiro Games."""

    @staticmethod
    def empacotar_diretorio(diretorio_origem: str, caminho_pak_destino: str) -> Dict[str, Any]:
        """
        Empacota todos os arquivos de diretorio_origem em caminho_pak_destino.
        Garante criação de pastas intermediárias e calcula CRC32 de cada arquivo.
        """
        if not os.path.exists(diretorio_origem):
            raise FileNotFoundError(f"Diretório de origem não existe: {diretorio_origem}")

        os.makedirs(os.path.dirname(os.path.abspath(caminho_pak_destino)), exist_ok=True)

        def construir_arvore(diretorio_atual: str, nome_no: str = "") -> Dict[str, Any]:
            entradas = sorted(os.listdir(diretorio_atual))
            filhos = []
            for entrada in entradas:
                caminho_completo = os.path.join(diretorio_atual, entrada)
                if os.path.isdir(caminho_completo):
                    subpasta = construir_arvore(caminho_completo, entrada)
                    filhos.append(subpasta)
                else:
                    with open(caminho_completo, "rb") as arquivo_leitura:
                        conteudo_bytes = arquivo_leitura.read()
                    tamanho = len(conteudo_bytes)
                    crc = zlib.crc32(conteudo_bytes) & 0xFFFFFFFF
                    filhos.append({
                        "tipo": 0,  # 0 = Arquivo
                        "nome": entrada,
                        "caminho_arquivo": caminho_completo,
                        "tamanho": tamanho,
                        "crc32": crc
                    })
            return {
                "tipo": 1,  # 1 = Diretório
                "nome": nome_no,
                "filhos": filhos
            }

        no_raiz = construir_arvore(diretorio_origem)
        filhos_raiz = no_raiz["filhos"]
        quantidade_pastas_raiz = len(filhos_raiz)

        # Coletar arquivos em ordem DFS
        todos_arquivos = []

        def coletar_arquivos(no: Dict[str, Any]) -> None:
            if no["tipo"] == 0:
                todos_arquivos.append(no)
            else:
                for filho in no["filhos"]:
                    coletar_arquivos(filho)

        for filho in filhos_raiz:
            coletar_arquivos(filho)

        # Calcular offsets relativos
        deslocamento_atual = 0
        for arquivo in todos_arquivos:
            arquivo["deslocamento"] = deslocamento_atual
            deslocamento_atual += arquivo["tamanho"]

        tamanho_total_dados = deslocamento_atual

        # Serializar árvore em memória
        buffer_arvore = io.BytesIO()

        def serializar_no(no: Dict[str, Any]) -> None:
            nome_bytes = no["nome"].encode("utf-8")
            buffer_arvore.write(struct.pack("B", len(nome_bytes)))
            buffer_arvore.write(nome_bytes)
            tipo_no = no["tipo"]
            buffer_arvore.write(struct.pack("B", tipo_no))
            if tipo_no == 1:
                quantidade_entradas = len(no["filhos"])
                buffer_arvore.write(struct.pack("<I", quantidade_entradas))
                for filho in no["filhos"]:
                    serializar_no(filho)
            else:
                deslocamento = no["deslocamento"]
                tamanho = no["tamanho"]
                crc = no["crc32"]
                buffer_arvore.write(struct.pack("<III", deslocamento, tamanho, crc))

        for filho in filhos_raiz:
            serializar_no(filho)

        bytes_arvore = buffer_arvore.getvalue()

        # Cabeçalho global = 18 bytes + bytes_arvore + 4 bytes do marcador 'DATA'
        tamanho_cabecalho = 18 + len(bytes_arvore) + 4
        deslocamento_dados = tamanho_cabecalho
        tamanho_total_arquivo = deslocamento_dados + tamanho_total_dados
        versao_heaps = 0x0100  # 256

        with open(caminho_pak_destino, "wb") as arquivo_saida:
            # 1. Cabeçalho de 18 bytes
            arquivo_saida.write(
                struct.pack("<4sIIHI", b"PAK\x00", deslocamento_dados, tamanho_total_arquivo, versao_heaps, quantidade_pastas_raiz)
            )
            # 2. Árvore serializada
            arquivo_saida.write(bytes_arvore)
            # 3. Marcador ASCII DATA
            arquivo_saida.write(b"DATA")
            # 4. Dados binários dos arquivos
            for arquivo in todos_arquivos:
                with open(arquivo["caminho_arquivo"], "rb") as arquivo_entrada:
                    while True:
                        bloco = arquivo_entrada.read(1024 * 1024)
                        if not bloco:
                            break
                        arquivo_saida.write(bloco)

        return {
            "caminho_arquivo": caminho_pak_destino,
            "tamanho_bytes": tamanho_total_arquivo,
            "quantidade_arquivos": len(todos_arquivos),
            "deslocamento_dados": deslocamento_dados
        }

    @staticmethod
    def descompactar_pak(
        caminho_pak: str,
        diretorio_destino: str,
        apenas_linguagem: bool = False,
        filtro_extensoes: Any = None
    ) -> Dict[str, Any]:
        """
        Descompacta arquivos de um pacote .PAK da engine Heaps.io (Shiro Games).
        Suporta extração completa ou filtrada (apenas_linguagem=True extrai apenas lang/*.xml).
        """
        if not os.path.exists(caminho_pak):
            raise FileNotFoundError(f"Arquivo .PAK não encontrado: {caminho_pak}")

        os.makedirs(diretorio_destino, exist_ok=True)

        with open(caminho_pak, "rb") as f_pak:
            # 1. Leitura do cabeçalho de 18 bytes
            cabecalho = f_pak.read(18)
            if len(cabecalho) < 18:
                raise ValueError("Arquivo .PAK corrompido ou incompleto (cabeçalho < 18 bytes).")

            magic, deslocamento_dados, tamanho_total, versao, qtd_pastas_raiz = struct.unpack("<4sIIHI", cabecalho)
            if magic != b"PAK\x00":
                raise ValueError(f"Assinatura mágica inválida: {magic}. Esperado: b'PAK\\x00'.")

            # 2. Ler árvore de diretórios (TOC) até deslocamento_dados - 4
            tamanho_toc = deslocamento_dados - 18 - 4
            if tamanho_toc <= 0:
                raise ValueError("Tamanho da tabela de conteúdos inválido no arquivo .PAK.")

            bytes_toc = f_pak.read(tamanho_toc)
            marcador_data = f_pak.read(4)

            # Parser recursivo da TOC
            stream_toc = io.BytesIO(bytes_toc)
            arquivos_para_extrair = []

            def ler_no(caminho_pai: str) -> None:
                bytes_tam = stream_toc.read(1)
                if not bytes_tam:
                    return
                namelen = struct.unpack("B", bytes_tam)[0]
                nome = stream_toc.read(namelen).decode("utf-8", errors="replace")
                tipo = struct.unpack("B", stream_toc.read(1))[0]

                caminho_atual = os.path.join(caminho_pai, nome) if caminho_pai else nome

                if tipo == 1:  # Diretório
                    num_entradas = struct.unpack("<I", stream_toc.read(4))[0]
                    for _ in range(num_entradas):
                        ler_no(caminho_atual)
                else:  # Arquivo (tipo 0 ou 2)
                    deslocamento, tamanho, crc = struct.unpack("<III", stream_toc.read(12))
                    arquivos_para_extrair.append({
                        "caminho_relativo": caminho_atual,
                        "nome": nome,
                        "deslocamento": deslocamento,
                        "tamanho": tamanho,
                        "crc32": crc
                    })

            for _ in range(qtd_pastas_raiz):
                ler_no("")

            # 3. Extrair arquivos selecionados
            arquivos_extraidos = []
            for item in arquivos_para_extrair:
                rel = item["caminho_relativo"].replace("\\", "/")
                # Filtro de linguagem
                if apenas_linguagem:
                    eh_linguagem = (
                        rel.startswith("lang/") or
                        "export_" in item["nome"] or
                        "texts_" in item["nome"] or
                        item["nome"].endswith(".xml")
                    )
                    if not eh_linguagem:
                        continue

                if filtro_extensoes:
                    ext = os.path.splitext(item["nome"])[1].lower()
                    if ext not in filtro_extensoes:
                        continue

                caminho_final = os.path.join(diretorio_destino, item["caminho_relativo"])
                os.makedirs(os.path.dirname(caminho_final), exist_ok=True)

                posicao_absoluta = deslocamento_dados + item["deslocamento"]
                f_pak.seek(posicao_absoluta)
                conteudo_arquivo = f_pak.read(item["tamanho"])

                with open(caminho_final, "wb") as f_out:
                    f_out.write(conteudo_arquivo)

                arquivos_extraidos.append(caminho_final)

            return {
                "caminho_pak": caminho_pak,
                "diretorio_destino": diretorio_destino,
                "total_arquivos_pak": len(arquivos_para_extrair),
                "total_extraidos": len(arquivos_extraidos),
                "arquivos": arquivos_extraidos
            }

    @classmethod
    def extrair_arquivos_linguagem(cls, caminho_pak: str, diretorio_destino: str) -> Dict[str, Any]:
        """Extrai seletivamente apenas arquivos XML de localização (export_*.xml e texts_*.xml)."""
        return cls.descompactar_pak(caminho_pak, diretorio_destino, apenas_linguagem=True)

