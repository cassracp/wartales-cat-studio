# -*- coding: utf-8 -*-
"""
================================================================================
 Módulo Gerenciador de Projetos e Mods - Wartales CAT Studio
================================================================================
 Responsável pelo ciclo de vida e isolamento dos diferentes mods de Wartales:
 - Criação e seleção de projetos de mods
 - Mapeamento e validação de diretórios isolados
 - Autodetecção do jogo na Steam
 - Persistência das configurações em configuracao.json
================================================================================
"""

import os
import re
import json
from typing import Dict, Any, List, Optional


class GerenciadorProjetos:
    """Controla múltiplos projetos de localização e seus respectivos arquivos."""

    def __init__(self, caminho_configuracao: Optional[str] = None):
        diretorio_base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.diretorio_base = diretorio_base

        if caminho_configuracao is None:
            caminho_configuracao = os.path.join(diretorio_base, "configuracao.json")

        self.caminho_configuracao = caminho_configuracao
        self.config = self._carregar_configuracao()
        self._garantir_diretorios_base()

    def _carregar_configuracao(self) -> Dict[str, Any]:
        if os.path.exists(self.caminho_configuracao):
            try:
                with open(self.caminho_configuracao, "r", encoding="utf-8") as f:
                    dados = json.load(f)
                    return self._normalizar_configuracao(dados)
            except Exception:
                pass
        return self._normalizar_configuracao({})

    def _salvar_configuracao(self) -> None:
        with open(self.caminho_configuracao, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)

    def _normalizar_configuracao(self, dados: Dict[str, Any]) -> Dict[str, Any]:
        """Garante a presença de todos os campos estruturais na configuração."""
        padrao = {
            "porta_servidor": 5000,
            "host_servidor": "127.0.0.1",
            "titulo_aplicacao": "Wartales CAT Studio",
            "chave_api_gemini": dados.get("chave_api_gemini", os.environ.get("CHAVE_API_GEMINI", "")),
            "caminho_steam_wartales": dados.get("caminho_steam_wartales", self.autodetectar_caminho_steam() or ""),
            "projeto_ativo": dados.get("projeto_ativo", "wartales_remastered"),
            "projetos": dados.get("projetos", [
                {
                    "slug": "wartales_remastered",
                    "nome": "Wartales Remastered",
                    "versao": "7.40",
                    "descricao": "Overhaul oficial da comunidade com balanceamento e novas mecânicas.",
                    "diretorio_mod_en": "dados/mod_atual",
                    "diretorio_traducao_ia": "dados/mod_atual",
                    "caminho_banco": "dados/banco/wartales_cat.db"
                }
            ]),
            "diretorio_referencia_vanilla": dados.get("diretorio_referencia_vanilla", "dados/referencia_vanilla"),
            "diretorio_memoria_global": dados.get("diretorio_memoria_global", "dados/memoria_traducao")
        }
        padrao.update(dados)
        return padrao

    def _garantir_diretorios_base(self) -> None:
        dir_vanilla = self.obter_caminho_absoluto(self.config.get("diretorio_referencia_vanilla", "dados/referencia_vanilla"))
        dir_projetos = os.path.join(self.diretorio_base, "dados", "projetos")
        dir_memoria = self.obter_caminho_absoluto(self.config.get("diretorio_memoria_global", "dados/memoria_traducao"))

        os.makedirs(dir_vanilla, exist_ok=True)
        os.makedirs(dir_projetos, exist_ok=True)
        os.makedirs(dir_memoria, exist_ok=True)

    def obter_caminho_absoluto(self, caminho_relativo_ou_abs: str) -> str:
        if os.path.isabs(caminho_relativo_ou_abs):
            return caminho_relativo_ou_abs
        return os.path.normpath(os.path.join(self.diretorio_base, caminho_relativo_ou_abs))

    @staticmethod
    def gerar_slug(texto: str) -> str:
        """Converte um nome para um identificador seguro de pasta (slug)."""
        slug = re.sub(r'[^a-zA-Z0-9_\-]+', '_', texto.lower().strip())
        return slug.strip('_') or "mod_projeto"

    def autodetectar_caminho_steam(self) -> Optional[str]:
        """
        Procura dinamicamente a pasta de instalação de Wartales contendo res.pak:
        1. Inspeciona o Registro do Windows (winreg) e o arquivo libraryfolders.vdf da Steam.
        2. Varre todos os volumes/drives locais do sistema nos caminhos padrões da Steam.
        """
        candidatos = []

        # 1. Tentar detectar via Registro do Windows e libraryfolders.vdf
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as chave:
                caminho_steam_principal, _ = winreg.QueryValueEx(chave, "SteamPath")
                if caminho_steam_principal and os.path.exists(caminho_steam_principal):
                    candidatos.append(os.path.join(caminho_steam_principal, "steamapps", "common", "Wartales"))
                    vdf = os.path.join(caminho_steam_principal, "steamapps", "libraryfolders.vdf")
                    if os.path.exists(vdf):
                        with open(vdf, "r", encoding="utf-8", errors="ignore") as f:
                            for linha in f:
                                match = re.search(r'"path"\s+"([^"]+)"', linha)
                                if match:
                                    pasta_lib = match.group(1).replace("\\\\", "\\")
                                    candidatos.append(os.path.join(pasta_lib, "steamapps", "common", "Wartales"))
        except Exception:
            pass

        # 2. Caminhos comuns em todos os drives locais
        drives = ["D:", "C:", "E:", "F:", "G:", "H:"]
        subpastas = [
            os.path.join("SteamLibrary", "steamapps", "common", "Wartales"),
            os.path.join("Program Files (x86)", "Steam", "steamapps", "common", "Wartales"),
            os.path.join("Steam", "steamapps", "common", "Wartales"),
            os.path.join("Jogos", "Steam", "steamapps", "common", "Wartales"),
            os.path.join("Games", "Steam", "steamapps", "common", "Wartales")
        ]
        for drive in drives:
            for sub in subpastas:
                candidatos.append(os.path.join(drive + "\\", sub))

        # 3. Testar o primeiro candidato válido que possua res.pak
        for c in candidatos:
            caminho_norm = os.path.normpath(c)
            if os.path.exists(caminho_norm):
                pak = os.path.join(caminho_norm, "res.pak")
                if os.path.exists(pak):
                    return caminho_norm

        return None

    def verificar_arquivos_vanilla(self) -> Dict[str, Any]:
        """Verifica se os 4 arquivos essenciais do jogo base estão extraídos e presentes."""
        dir_vanilla = self.obter_caminho_absoluto(self.config.get("diretorio_referencia_vanilla", "dados/referencia_vanilla"))
        arquivos_esperados = ["export_en.xml", "export_pt-BR.xml", "texts_en.xml", "texts_pt-BR.xml"]

        status_arquivos = {}
        todos_presentes = True
        for arq in arquivos_esperados:
            caminho_arq = os.path.join(dir_vanilla, arq)
            presente = os.path.exists(caminho_arq) and os.path.getsize(caminho_arq) > 0
            status_arquivos[arq] = {
                "presente": presente,
                "tamanho_bytes": os.path.getsize(caminho_arq) if presente else 0,
                "caminho": caminho_arq
            }
            if not presente:
                todos_presentes = False

        caminho_steam = self.config.get("caminho_steam_wartales", "")
        res_pak_detectado = False
        caminho_res_pak = ""
        if caminho_steam and os.path.exists(caminho_steam):
            caminho_res_pak = os.path.join(caminho_steam, "res.pak")
            res_pak_detectado = os.path.exists(caminho_res_pak)

        return {
            "diretorio_vanilla": dir_vanilla,
            "completo": todos_presentes,
            "arquivos": status_arquivos,
            "caminho_steam": caminho_steam,
            "res_pak_detectado": res_pak_detectado,
            "caminho_res_pak": caminho_res_pak
        }

    def listar_projetos(self) -> List[Dict[str, Any]]:
        """Retorna a lista de todos os projetos de mod com verificação de status."""
        projetos = self.config.get("projetos", [])
        slug_ativo = self.config.get("projeto_ativo", "")

        resultado = []
        for p in projetos:
            dados_p = dict(p)
            dados_p["ativo"] = (p["slug"] == slug_ativo)

            # Verificar arquivos do mod
            dir_en = self.obter_caminho_absoluto(p.get("diretorio_mod_en", ""))
            dir_ia = self.obter_caminho_absoluto(p.get("diretorio_traducao_ia", ""))
            caminho_db = self.obter_caminho_absoluto(p.get("caminho_banco", ""))

            dados_p["mod_en_pronto"] = (
                os.path.exists(os.path.join(dir_en, "texts_en.xml")) or
                os.path.exists(os.path.join(dir_en, "export_en.xml"))
            )
            dados_p["traducao_ia_pronta"] = (
                os.path.exists(os.path.join(dir_ia, "texts_pt-BR.xml")) or
                os.path.exists(os.path.join(dir_ia, "export_pt-BR.xml"))
            )
            dados_p["banco_criado"] = os.path.exists(caminho_db)
            resultado.append(dados_p)

        return resultado

    def obter_projeto_ativo(self) -> Dict[str, Any]:
        """Retorna as configurações do projeto de mod atualmente ativo."""
        slug_ativo = self.config.get("projeto_ativo", "wartales_remastered")
        for p in self.config.get("projetos", []):
            if p["slug"] == slug_ativo:
                res = dict(p)
                res["diretorio_mod_en_abs"] = self.obter_caminho_absoluto(p["diretorio_mod_en"])
                res["diretorio_traducao_ia_abs"] = self.obter_caminho_absoluto(p["diretorio_traducao_ia"])
                res["caminho_banco_abs"] = self.obter_caminho_absoluto(p["caminho_banco"])
                return res

        # Fallback para o primeiro
        projetos = self.config.get("projetos", [])
        if projetos:
            p = projetos[0]
            res = dict(p)
            res["diretorio_mod_en_abs"] = self.obter_caminho_absoluto(p["diretorio_mod_en"])
            res["diretorio_traducao_ia_abs"] = self.obter_caminho_absoluto(p["diretorio_traducao_ia"])
            res["caminho_banco_abs"] = self.obter_caminho_absoluto(p["caminho_banco"])
            return res

        return {}

    def definir_projeto_ativo(self, slug: str) -> Dict[str, Any]:
        """Define o projeto ativo pelo slug e salva a configuração."""
        encontrado = False
        for p in self.config.get("projetos", []):
            if p["slug"] == slug:
                encontrado = True
                break

        if not encontrado:
            raise ValueError(f"Projeto com slug '{slug}' não encontrado.")

        self.config["projeto_ativo"] = slug
        self._salvar_configuracao()
        return self.obter_projeto_ativo()

    def criar_projeto(
        self,
        nome: str,
        versao: str = "1.0",
        descricao: str = ""
    ) -> Dict[str, Any]:
        """Cria um novo projeto de mod, gerando sua estrutura de pastas isolada."""
        if not nome or not nome.strip():
            raise ValueError("O nome do mod é obrigatório.")

        slug = self.gerar_slug(nome)
        # Verificar se slug já existe
        projetos = self.config.setdefault("projetos", [])
        for p in projetos:
            if p["slug"] == slug:
                raise ValueError(f"Já existe um projeto cadastrado com o identificador '{slug}'.")

        pasta_projeto = os.path.join("dados", "projetos", slug)
        dir_mod_en = os.path.join(pasta_projeto, "mod_en")
        dir_traducao_ia = os.path.join(pasta_projeto, "traducao_ia")
        caminho_banco = os.path.join(pasta_projeto, f"{slug}.db")

        # Criar fisicamente as pastas
        os.makedirs(self.obter_caminho_absoluto(dir_mod_en), exist_ok=True)
        os.makedirs(self.obter_caminho_absoluto(dir_traducao_ia), exist_ok=True)
        os.makedirs(os.path.dirname(self.obter_caminho_absoluto(caminho_banco)), exist_ok=True)

        novo_projeto = {
            "slug": slug,
            "nome": nome.strip(),
            "versao": versao.strip() or "1.0",
            "descricao": descricao.strip(),
            "diretorio_mod_en": dir_mod_en.replace("\\", "/"),
            "diretorio_traducao_ia": dir_traducao_ia.replace("\\", "/"),
            "caminho_banco": caminho_banco.replace("\\", "/")
        }

        projetos.append(novo_projeto)
        self.config["projeto_ativo"] = slug
        self._salvar_configuracao()

        return self.obter_projeto_ativo()

    def atualizar_chave_gemini(self, nova_chave: str) -> None:
        """Atualiza e persiste a chave da API do Gemini nas configurações."""
        self.config["chave_api_gemini"] = (nova_chave or "").strip()
        self._salvar_configuracao()

    def atualizar_caminho_steam(self, novo_caminho: str) -> None:
        """Atualiza e persiste o caminho da Steam nas configurações."""
        self.config["caminho_steam_wartales"] = (novo_caminho or "").strip()
        self._salvar_configuracao()
