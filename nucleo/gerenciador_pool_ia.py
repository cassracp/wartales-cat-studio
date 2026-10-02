# -*- coding: utf-8 -*-
"""
================================================================================
 Módulo de Pool de Chaves de IA e Circuit Breaker - Wartales CAT Studio
================================================================================
 Gerencia múltiplas chaves de API com suporte a:
 - Estratégias de seleção: Round-Robin (balanceamento) e Fallback (prioridade).
 - Circuit Breaker / Isolamento temporário (HTTP 429 -> cooldown; HTTP 403 -> bloqueio permanente).
 - Padrão Adapter para múltiplos provedores (inicialmente Gemini Flash Lite, extensível).
 - Persistência segura em SQLite com mascaramento de credenciais e proteção no Git.
 - Migração e sincronização com o arquivo .env existente.
 Nomenclatura 100% em Português do Brasil (pt-BR).
================================================================================
"""

import os
import re
import json
import time
import logging
import sqlite3
import threading
import urllib.request
import urllib.error
from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Optional, Callable, Generator, Set

logger = logging.getLogger("cat_wartales.pool_ia")

DIRETORIO_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAMINHO_BANCO_POOL_PADRAO = os.path.join(DIRETORIO_RAIZ, "dados", "banco", "chaves_ia.db")
CAMINHO_ENV_PADRAO = os.path.join(DIRETORIO_RAIZ, ".env")

PROMPT_SISTEMA_WARTALES_PADRAO = """Você é um tradutor sênior especializado na localização oficial de Wartales para Português do Brasil (pt-BR).
Traduza o texto em inglês mantendo fidelidade absoluta ao estilo do jogo original da Shiro Games.

REGRAS:
1. Mantenha TODAS as tags XML, HTML e marcações intactas:
   - Ex: [DMG], [Fervor], [Bleeding], [Movement], [Willpower], ::value::, $val$, {val}
   - Ex: <skill>Lone Wolf</skill>, <b>...</b>, <br />, <br/>, &lt;b&gt;...&lt;/b&gt;
   - NUNCA adicione nem remova tags de quebra de linha ou formatação.
2. Padrões de terminologia:
   - "Armour:" -> "Armadura:"
   - "Helmet:" -> "Capacete:"
   - "Default Scaling, Levels 1 -> 15:" -> "Escalonamento Padrão, Níveis 1 -> 15:"
   - "Strength:" -> "Força:", "Dexterity:" -> "Destreza:", "Constitution:" -> "Constituição:"
   - "Additional abilities, Level -> Skill:" -> "Habilidades adicionais, Nível -> Habilidade:"
   - "Capture: 1 rope" -> "Captura: 1 corda"
   - "Light" -> "Leve", "Medium" -> "Média" (ou Médio), "Heavy" -> "Pesada" (ou Pesado), "None" -> "Nenhuma"
3. Responda ESTRITAMENTE em formato JSON com o schema:
   {"pt": "texto traduzido"}
"""


# ==============================================================================
# 1. Modelo de Dados da Chave de API
# ==============================================================================

@dataclass
class ChaveIA:
    """Entidade que representa uma credencial de API no Pool de IA."""
    id: int
    chave: str
    rotulo: str
    provedor: str = "gemini"
    modelo: str = "gemini-flash-lite-latest"
    prioridade: int = 1
    ativo: bool = True
    em_cooldown_ate: float = 0.0
    motivo_cooldown: str = ""
    bloqueada_permanentemente: bool = False
    total_requisicoes: int = 0
    total_sucessos: int = 0
    total_falhas: int = 0
    ultimo_erro: str = ""
    ultima_utilizacao: float = 0.0
    data_criacao: str = ""

    def esta_em_cooldown(self) -> bool:
        """Indica se a chave está em período de espera temporário após falha ou HTTP 429."""
        return time.time() < self.em_cooldown_ate

    def segundos_cooldown_restantes(self) -> int:
        """Retorna os segundos inteiros que restam para o término do cooldown."""
        restante = self.em_cooldown_ate - time.time()
        return max(0, int(restante))

    def esta_apta(self) -> bool:
        """Determina se a chave pode ser selecionada para atender a uma requisição."""
        return bool(self.ativo and (not self.bloqueada_permanentemente) and (not self.esta_em_cooldown()))

    def mascarar_chave(self) -> str:
        """Gera uma versão ofuscada da chave para exibição pública e logs de auditoria."""
        val = self.chave or ""
        tamanho = len(val)
        if tamanho <= 8:
            return "****"
        return f"{val[:4]}...{val[-4:]}"

    def para_dicionario(self, incluir_chave_completa: bool = False) -> Dict[str, Any]:
        """Converte a entidade para dicionário, protegendo a chave secreta por padrão."""
        dados = asdict(self)
        if not incluir_chave_completa:
            dados["chave"] = self.mascarar_chave()
        dados["chave_mascarada"] = self.mascarar_chave()
        dados["esta_em_cooldown"] = self.esta_em_cooldown()
        dados["segundos_cooldown_restantes"] = self.segundos_cooldown_restantes()
        dados["esta_apta"] = self.esta_apta()
        return dados


# ==============================================================================
# 2. Padrão Strategy: Estratégias de Seleção de Chaves
# ==============================================================================

class EstrategiaSelecaoChave(ABC):
    """Contrato abstrato para algoritmos de seleção de chaves no pool."""

    @abstractmethod
    def selecionar_chave(self, chaves_aptas: List[ChaveIA]) -> Optional[ChaveIA]:
        """Seleciona a melhor chave entre a lista de chaves aptas."""
        pass


class EstrategiaRoundRobin(EstrategiaSelecaoChave):
    """
    Estratégia de balanceamento de carga circular (Round-Robin).
    Distribui as requisições de forma uniforme entre todas as chaves aptas.
    """

    def __init__(self):
        self._indice_atual: int = 0
        self._lock = threading.Lock()

    def selecionar_chave(self, chaves_aptas: List[ChaveIA]) -> Optional[ChaveIA]:
        if not chaves_aptas:
            return None
        with self._lock:
            chaves_ordenadas = sorted(chaves_aptas, key=lambda c: c.id)
            escolhida = chaves_ordenadas[self._indice_atual % len(chaves_ordenadas)]
            self._indice_atual = (self._indice_atual + 1) % len(chaves_ordenadas)
            return escolhida

    def redefinir_indice(self) -> None:
        """Reinicia o ponteiro de distribuição circular."""
        with self._lock:
            self._indice_atual = 0


class EstrategiaFallback(EstrategiaSelecaoChave):
    """
    Estratégia de failover por prioridade estrita.
    Utiliza sempre a chave com menor valor numérico de prioridade (1 = mais prioritária).
    Só avança para a próxima caso a anterior entre em cooldown ou seja bloqueada.
    """

    def selecionar_chave(self, chaves_aptas: List[ChaveIA]) -> Optional[ChaveIA]:
        if not chaves_aptas:
            return None
        chaves_ordenadas = sorted(chaves_aptas, key=lambda c: (c.prioridade, c.id))
        return chaves_ordenadas[0]


# ==============================================================================
# 3. Padrão Adapter: Adaptadores de Provedores de IA Generativa
# ==============================================================================

class AdaptadorProvedorIA(ABC):
    """Interface abstrata para adaptadores de serviços de IA generativa."""

    @abstractmethod
    def traduzir(
        self,
        chave: str,
        modelo: str,
        texto_en: str,
        instrucoes_sistema: Optional[str] = None
    ) -> Dict[str, Any]:
        """Executa a chamada de tradução retornando dicionário padronizado."""
        pass

    @abstractmethod
    def testar_conexao(self, chave: str, modelo: str) -> Dict[str, Any]:
        """Testa se a chave informada conecta e responde com sucesso."""
        pass


class AdaptadorGemini(AdaptadorProvedorIA):
    """Adaptador de integração direta com a API do Google Gemini."""

    def __init__(
        self,
        timeout_padrao: float = 30.0,
        transportador_http: Optional[Callable] = None
    ):
        self.timeout_padrao = timeout_padrao
        self._transportador_http = transportador_http

    def traduzir(
        self,
        chave: str,
        modelo: str,
        texto_en: str,
        instrucoes_sistema: Optional[str] = None
    ) -> Dict[str, Any]:
        if not texto_en or not texto_en.strip():
            return {"sucesso": True, "traducao": "", "tempo_segundos": 0.0, "erro": ""}

        prompt_sistema = instrucoes_sistema or PROMPT_SISTEMA_WARTALES_PADRAO
        prompt_completo = f"{prompt_sistema}\n\nTexto a traduzir:\n{texto_en.strip()}"

        payload_bytes = json.dumps({
            "contents": [{"parts": [{"text": prompt_completo}]}],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json"
            }
        }).encode("utf-8")

        modelo_limpo = (modelo or "").strip()
        if modelo_limpo.startswith("models/"):
            modelo_limpo = modelo_limpo[7:]

        chave_limpa = (chave or "").strip()
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo_limpo}:generateContent?key={chave_limpa}"
        t0 = time.time()

        try:
            if self._transportador_http is not None:
                resposta_bytes, codigo_status = self._transportador_http(
                    url, payload_bytes, {"Content-Type": "application/json"}
                )
            else:
                requisicao = urllib.request.Request(
                    url,
                    data=payload_bytes,
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(requisicao, timeout=self.timeout_padrao) as resposta:
                    resposta_bytes = resposta.read()
                    codigo_status = resposta.status if hasattr(resposta, "status") else 200

            tempo_decorrido = round(time.time() - t0, 2)
            dados_resposta = json.loads(resposta_bytes.decode("utf-8"))

            candidatos = dados_resposta.get("candidates", [])
            if not candidatos:
                msg_feedback = ""
                feedback = dados_resposta.get("promptFeedback")
                if feedback and "blockReason" in feedback:
                    msg_feedback = f" (Bloqueado por segurança: {feedback['blockReason']})"
                return {
                    "sucesso": False,
                    "traducao": "",
                    "codigo_status": codigo_status,
                    "tipo_erro": "resposta_vazia",
                    "tempo_segundos": tempo_decorrido,
                    "erro": f"Nenhum candidato retornado pelo modelo Gemini.{msg_feedback}"
                }

            primeiro_candidato = candidatos[0]
            conteudo = primeiro_candidato.get("content", {})
            partes = conteudo.get("parts", [])
            if not partes:
                finish_reason = primeiro_candidato.get("finishReason", "DESCONHECIDO")
                return {
                    "sucesso": False,
                    "traducao": "",
                    "codigo_status": codigo_status,
                    "tipo_erro": "resposta_bloqueada",
                    "tempo_segundos": tempo_decorrido,
                    "erro": f"Resposta sem partes de texto do modelo Gemini (motivo: {finish_reason})."
                }

            texto_candidato = partes[0].get("text", "")
            texto_limpo = texto_candidato.strip()
            if texto_limpo.startswith("```"):
                linhas_md = texto_limpo.splitlines()
                if len(linhas_md) >= 2 and linhas_md[0].startswith("```"):
                    if linhas_md[-1].startswith("```"):
                        texto_limpo = "\n".join(linhas_md[1:-1]).strip()
                    else:
                        texto_limpo = "\n".join(linhas_md[1:]).strip()

            traducao = ""
            try:
                resposta_json = json.loads(texto_limpo)
                traducao = resposta_json.get("pt", "").strip()
            except Exception:
                match_json = re.search(r'"pt"\s*:\s*"((?:[^"\\]|\\.)*)"', texto_limpo)
                if match_json:
                    traducao = match_json.group(1).replace(r'\"', '"').replace(r'\n', '\n').strip()
                else:
                    traducao = texto_limpo

            return {
                "sucesso": True,
                "traducao": traducao,
                "codigo_status": codigo_status,
                "tempo_segundos": tempo_decorrido,
                "erro": ""
            }

        except urllib.error.HTTPError as erro_http:
            tempo_decorrido = round(time.time() - t0, 2)
            try:
                corpo_erro = erro_http.read().decode("utf-8", errors="replace") if hasattr(erro_http, "read") else str(erro_http)
            except Exception:
                corpo_erro = str(erro_http)
            codigo = getattr(erro_http, "code", 500)
            tipo_erro = "desconhecido"

            if codigo == 429 or "RESOURCE_EXHAUSTED" in corpo_erro:
                tipo_erro = "limite_taxa"
            elif codigo == 403 or "API_KEY_INVALID" in corpo_erro or "PERMISSION_DENIED" in corpo_erro:
                tipo_erro = "chave_invalida"
            elif codigo == 400 and ("API_KEY" in corpo_erro or "key not valid" in corpo_erro.lower()):
                tipo_erro = "chave_invalida"

            return {
                "sucesso": False,
                "traducao": "",
                "codigo_status": codigo,
                "tipo_erro": tipo_erro,
                "tempo_segundos": tempo_decorrido,
                "erro": f"HTTP {codigo}: {corpo_erro}"
            }
        except urllib.error.URLError as erro_url:
            tempo_decorrido = round(time.time() - t0, 2)
            codigo = getattr(erro_url, "code", None)
            return {
                "sucesso": False,
                "traducao": "",
                "codigo_status": codigo,
                "tipo_erro": "erro_conexao",
                "tempo_segundos": tempo_decorrido,
                "erro": f"Erro de conexão com o Gemini: {str(erro_url)}"
            }
        except Exception as erro_geral:
            tempo_decorrido = round(time.time() - t0, 2)
            msg_str = str(erro_geral)
            codigo = getattr(erro_geral, "code", None)
            tipo_erro = "erro_interno"
            if codigo == 429 or "429" in msg_str or "RESOURCE_EXHAUSTED" in msg_str:
                codigo = 429
                tipo_erro = "limite_taxa"
            elif codigo == 403 or "403" in msg_str or "API_KEY_INVALID" in msg_str or "PERMISSION_DENIED" in msg_str:
                codigo = 403
                tipo_erro = "chave_invalida"
            return {
                "sucesso": False,
                "traducao": "",
                "codigo_status": codigo,
                "tipo_erro": tipo_erro,
                "tempo_segundos": tempo_decorrido,
                "erro": f"Falha na execução da tradução: {msg_str}"
            }

    def testar_conexao(self, chave: str, modelo: str) -> Dict[str, Any]:
        """Testa se uma chave é capaz de obter resposta válida do Gemini."""
        resultado = self.traduzir(
            chave=chave,
            modelo=modelo,
            texto_en="Hello",
            instrucoes_sistema="Traduza para pt-BR em JSON: {\"pt\": \"...\"}"
        )
        if resultado["sucesso"]:
            return {
                "sucesso": True,
                "mensagem": "Chave da API validada e respondendo com sucesso!",
                "tempo_segundos": resultado.get("tempo_segundos", 0.0)
            }
        return {
            "sucesso": False,
            "codigo_status": resultado.get("codigo_status"),
            "tipo_erro": resultado.get("tipo_erro"),
            "erro": resultado.get("erro", "Falha de validação desconhecida.")
        }


class FabricaProvedoresIA:
    """Fábrica para instanciar adaptadores de provedores de IA."""

    @staticmethod
    def criar_adaptador(
        provedor: str,
        transportador_http: Optional[Callable] = None
    ) -> AdaptadorProvedorIA:
        nome = (provedor or "").strip().lower()
        if nome in ("gemini", "google"):
            return AdaptadorGemini(transportador_http=transportador_http)
        raise ValueError(f"Provedor de IA '{provedor}' não é suportado no momento.")


# ==============================================================================
# 4. Padrão Repository: Persistência SQLite de Chaves
# ==============================================================================

class RepositorioChavesIA:
    """Gerencia a persistência das chaves de API e configurações do Pool em SQLite."""

    def __init__(self, caminho_banco: str = CAMINHO_BANCO_POOL_PADRAO):
        self.caminho_banco = os.path.abspath(caminho_banco) if caminho_banco != ":memory:" else ":memory:"
        if self.caminho_banco != ":memory:":
            pasta = os.path.dirname(self.caminho_banco)
            if pasta:
                os.makedirs(pasta, exist_ok=True)
            self._conexao_memoria = None
        else:
            self._conexao_memoria = sqlite3.connect(":memory:", check_same_thread=False)
            self._conexao_memoria.row_factory = sqlite3.Row
            self._conexao_memoria.execute("PRAGMA foreign_keys = ON;")
        self.inicializar_tabelas()

    @contextmanager
    def obter_conexao(self) -> Generator[sqlite3.Connection, None, None]:
        """Abre conexão com WAL e timeout seguro para concorrência multithread."""
        if self._conexao_memoria is not None:
            yield self._conexao_memoria
        else:
            conexao = sqlite3.connect(self.caminho_banco, timeout=30.0)
            conexao.row_factory = sqlite3.Row
            conexao.execute("PRAGMA journal_mode = WAL;")
            conexao.execute("PRAGMA synchronous = NORMAL;")
            conexao.execute("PRAGMA foreign_keys = ON;")
            try:
                yield conexao
            finally:
                conexao.close()

    def inicializar_tabelas(self) -> None:
        """Cria as tabelas estruturais de chaves e configurações caso não existam."""
        with self.obter_conexao() as conexao:
            cursor = conexao.cursor()

            # Tabela de Chaves
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pool_chaves_ia (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chave TEXT NOT NULL UNIQUE,
                    rotulo TEXT NOT NULL,
                    provedor TEXT NOT NULL DEFAULT 'gemini',
                    modelo TEXT NOT NULL DEFAULT 'gemini-flash-lite-latest',
                    prioridade INTEGER NOT NULL DEFAULT 1,
                    ativo INTEGER NOT NULL DEFAULT 1,
                    em_cooldown_ate REAL DEFAULT 0.0,
                    motivo_cooldown TEXT DEFAULT '',
                    bloqueada_permanentemente INTEGER DEFAULT 0,
                    total_requisicoes INTEGER DEFAULT 0,
                    total_sucessos INTEGER DEFAULT 0,
                    total_falhas INTEGER DEFAULT 0,
                    ultimo_erro TEXT DEFAULT '',
                    ultima_utilizacao REAL DEFAULT 0.0,
                    data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_pool_ativo ON pool_chaves_ia(ativo);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_pool_prioridade ON pool_chaves_ia(prioridade);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_pool_cooldown ON pool_chaves_ia(em_cooldown_ate);")

            # Tabela de Configurações do Pool
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS configuracao_pool_ia (
                    chave TEXT PRIMARY KEY,
                    valor TEXT NOT NULL
                );
            """)

            conexao.commit()

    def _linha_para_chave(self, linha: sqlite3.Row) -> ChaveIA:
        return ChaveIA(
            id=linha["id"],
            chave=linha["chave"],
            rotulo=linha["rotulo"],
            provedor=linha["provedor"],
            modelo=linha["modelo"],
            prioridade=linha["prioridade"],
            ativo=bool(linha["ativo"]),
            em_cooldown_ate=float(linha["em_cooldown_ate"] or 0.0),
            motivo_cooldown=linha["motivo_cooldown"] or "",
            bloqueada_permanentemente=bool(linha["bloqueada_permanentemente"]),
            total_requisicoes=int(linha["total_requisicoes"] or 0),
            total_sucessos=int(linha["total_sucessos"] or 0),
            total_falhas=int(linha["total_falhas"] or 0),
            ultimo_erro=linha["ultimo_erro"] or "",
            ultima_utilizacao=float(linha["ultima_utilizacao"] or 0.0),
            data_criacao=str(linha["data_criacao"] or "")
        )

    def inserir_chave(self, chave: ChaveIA) -> int:
        """Insere uma nova chave no banco de dados e retorna o ID gerado."""
        with self.obter_conexao() as conexao:
            cursor = conexao.cursor()
            cursor.execute("""
                INSERT INTO pool_chaves_ia (
                    chave, rotulo, provedor, modelo, prioridade, ativo,
                    em_cooldown_ate, motivo_cooldown, bloqueada_permanentemente
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                chave.chave.strip(),
                chave.rotulo.strip(),
                chave.provedor.strip().lower(),
                chave.modelo.strip(),
                chave.prioridade,
                1 if chave.ativo else 0,
                chave.em_cooldown_ate,
                chave.motivo_cooldown,
                1 if chave.bloqueada_permanentemente else 0
            ))
            novo_id = cursor.lastrowid
            conexao.commit()
            return novo_id

    def atualizar_chave(
        self,
        id_chave: int,
        rotulo: Optional[str] = None,
        modelo: Optional[str] = None,
        prioridade: Optional[int] = None,
        ativo: Optional[bool] = None,
        chave: Optional[str] = None
    ) -> bool:
        """Atualiza metadados cadastrais de uma chave existente."""
        clausulas = []
        valores = []

        if chave is not None and chave.strip():
            clausulas.append("chave = ?")
            valores.append(chave.strip())
        if rotulo is not None:
            clausulas.append("rotulo = ?")
            valores.append(rotulo.strip())
        if modelo is not None:
            clausulas.append("modelo = ?")
            valores.append(modelo.strip())
        if prioridade is not None:
            clausulas.append("prioridade = ?")
            valores.append(int(prioridade))
        if ativo is not None:
            clausulas.append("ativo = ?")
            valores.append(1 if ativo else 0)

        if not clausulas:
            return False

        valores.append(id_chave)
        with self.obter_conexao() as conexao:
            cursor = conexao.cursor()
            cursor.execute(f"UPDATE pool_chaves_ia SET {', '.join(clausulas)} WHERE id = ?", valores)
            conexao.commit()
            return cursor.rowcount > 0

    def atualizar_credencial_chave(self, id_chave: int, nova_chave: str) -> bool:
        """Atualiza o segredo de uma chave existente no banco de dados e reseta erros anteriores."""
        nova_chave_limpa = (nova_chave or "").strip()
        if not nova_chave_limpa:
            raise ValueError("O segredo da chave não pode ser vazio.")
        with self.obter_conexao() as conexao:
            cursor = conexao.cursor()
            cursor.execute("""
                UPDATE pool_chaves_ia
                SET chave = ?,
                    em_cooldown_ate = 0.0,
                    motivo_cooldown = '',
                    bloqueada_permanentemente = 0,
                    ativo = 1,
                    ultimo_erro = ''
                WHERE id = ?
            """, (nova_chave_limpa, id_chave))
            conexao.commit()
            return cursor.rowcount > 0

    def remover_chave(self, id_chave: int) -> bool:
        """Exclui permanentemente uma chave do pool pelo seu ID."""
        with self.obter_conexao() as conexao:
            cursor = conexao.cursor()
            cursor.execute("DELETE FROM pool_chaves_ia WHERE id = ?", (id_chave,))
            conexao.commit()
            return cursor.rowcount > 0

    def alternar_status(self, id_chave: int, ativo: Optional[bool] = None) -> bool:
        """Ativa ou desativa uma chave. Se ativo for None, inverte o estado atual."""
        with self.obter_conexao() as conexao:
            cursor = conexao.cursor()
            if ativo is None:
                cursor.execute("UPDATE pool_chaves_ia SET ativo = 1 - ativo WHERE id = ?", (id_chave,))
            else:
                cursor.execute("UPDATE pool_chaves_ia SET ativo = ? WHERE id = ?", (1 if ativo else 0, id_chave))
            conexao.commit()
            return cursor.rowcount > 0

    def obter_chave_por_id(self, id_chave: int) -> Optional[ChaveIA]:
        """Busca uma chave específica por seu identificador numérico."""
        with self.obter_conexao() as conexao:
            cursor = conexao.cursor()
            cursor.execute("SELECT * FROM pool_chaves_ia WHERE id = ?", (id_chave,))
            linha = cursor.fetchone()
            if linha:
                return self._linha_para_chave(linha)
            return None

    def obter_chave_por_valor(self, chave_str: str) -> Optional[ChaveIA]:
        """Busca uma chave pelo valor exato da credencial."""
        with self.obter_conexao() as conexao:
            cursor = conexao.cursor()
            cursor.execute("SELECT * FROM pool_chaves_ia WHERE chave = ?", (chave_str.strip(),))
            linha = cursor.fetchone()
            if linha:
                return self._linha_para_chave(linha)
            return None

    def listar_todas_chaves(self) -> List[ChaveIA]:
        """Retorna todas as chaves cadastradas ordenadas por prioridade e id."""
        with self.obter_conexao() as conexao:
            cursor = conexao.cursor()
            cursor.execute("SELECT * FROM pool_chaves_ia ORDER BY prioridade ASC, id ASC")
            return [self._linha_para_chave(linha) for linha in cursor.fetchall()]

    def registrar_sucesso(self, id_chave: int) -> None:
        """Registra uma requisição bem-sucedida, atualizando contadores e resetando cooldowns/erros anteriores."""
        with self.obter_conexao() as conexao:
            cursor = conexao.cursor()
            agora = time.time()
            cursor.execute("""
                UPDATE pool_chaves_ia
                SET total_requisicoes = total_requisicoes + 1,
                    total_sucessos = total_sucessos + 1,
                    em_cooldown_ate = 0.0,
                    motivo_cooldown = '',
                    ultimo_erro = '',
                    ultima_utilizacao = ?
                WHERE id = ?
            """, (agora, id_chave))
            conexao.commit()

    def registrar_cooldown(self, id_chave: int, tempo_cooldown_segundos: float, motivo: str) -> None:
        """Ativa o circuito de cooldown temporário para uma chave (ex: HTTP 429)."""
        em_cooldown_ate = time.time() + float(tempo_cooldown_segundos)
        with self.obter_conexao() as conexao:
            cursor = conexao.cursor()
            cursor.execute("""
                UPDATE pool_chaves_ia
                SET total_requisicoes = total_requisicoes + 1,
                    total_falhas = total_falhas + 1,
                    em_cooldown_ate = ?,
                    motivo_cooldown = ?,
                    ultimo_erro = ?
                WHERE id = ?
            """, (em_cooldown_ate, motivo, motivo, id_chave))
            conexao.commit()

    def registrar_bloqueio_permanente(self, id_chave: int, motivo: str) -> None:
        """Desativa e bloqueia permanentemente a chave após erro crítico (ex: HTTP 403 / revoked)."""
        with self.obter_conexao() as conexao:
            cursor = conexao.cursor()
            cursor.execute("""
                UPDATE pool_chaves_ia
                SET total_requisicoes = total_requisicoes + 1,
                    total_falhas = total_falhas + 1,
                    ativo = 0,
                    bloqueada_permanentemente = 1,
                    ultimo_erro = ?
                WHERE id = ?
            """, (motivo, id_chave))
            conexao.commit()

    def registrar_falha_geral(self, id_chave: int, motivo: str) -> None:
        """Registra uma falha não crítica (ex: timeout de rede passageiro)."""
        with self.obter_conexao() as conexao:
            cursor = conexao.cursor()
            cursor.execute("""
                UPDATE pool_chaves_ia
                SET total_requisicoes = total_requisicoes + 1,
                    total_falhas = total_falhas + 1,
                    ultimo_erro = ?
                WHERE id = ?
            """, (motivo, id_chave))
            conexao.commit()

    def redefinir_cooldown_e_erros(self, id_chave: int) -> bool:
        """Zera o cooldown e desfaz bloqueio permanente de uma chave."""
        with self.obter_conexao() as conexao:
            cursor = conexao.cursor()
            cursor.execute("""
                UPDATE pool_chaves_ia
                SET em_cooldown_ate = 0.0,
                    motivo_cooldown = '',
                    bloqueada_permanentemente = 0,
                    ativo = 1,
                    ultimo_erro = ''
                WHERE id = ?
            """, (id_chave,))
            conexao.commit()
            return cursor.rowcount > 0

    def obter_configuracao(self, chave: str, valor_padrao: str = "") -> str:
        """Recupera um valor de configuração textual do pool."""
        with self.obter_conexao() as conexao:
            cursor = conexao.cursor()
            cursor.execute("SELECT valor FROM configuracao_pool_ia WHERE chave = ?", (chave,))
            linha = cursor.fetchone()
            if linha:
                return str(linha["valor"])
            return valor_padrao

    def salvar_configuracao(self, chave: str, valor: str) -> None:
        """Salva ou atualiza um valor de configuração do pool."""
        with self.obter_conexao() as conexao:
            cursor = conexao.cursor()
            cursor.execute("""
                INSERT INTO configuracao_pool_ia (chave, valor)
                VALUES (?, ?)
                ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor
            """, (chave, str(valor)))
            conexao.commit()


# ==============================================================================
# 5. Gerenciador Central: GerenciadorPoolIA
# ==============================================================================

class GerenciadorPoolIA:
    """
    Orquestrador central do Pool de Chaves de IA com Circuit Breaker e
    balanceamento inteligente entre múltiplos modelos e contas.
    """

    def __init__(
        self,
        caminho_banco: Optional[str] = None,
        repositorio: Optional[RepositorioChavesIA] = None,
        transportador_http: Optional[Callable] = None,
        caminho_env: Optional[str] = None
    ):
        if repositorio is not None:
            self.repositorio = repositorio
        else:
            banco = caminho_banco or CAMINHO_BANCO_POOL_PADRAO
            self.repositorio = RepositorioChavesIA(banco)

        self.caminho_env = caminho_env or CAMINHO_ENV_PADRAO
        self._transportador_http = transportador_http

        self._estrategia_round_robin = EstrategiaRoundRobin()
        self._estrategia_fallback = EstrategiaFallback()

        self._lock = threading.Lock()
        self.migrar_chave_env_se_necessario()

    # --------------------------------------------------------------------------
    # Configurações do Pool
    # --------------------------------------------------------------------------

    def obter_modo_selecao(self) -> str:
        """Retorna o modo de seleção configurado ('round_robin' ou 'fallback')."""
        return self.repositorio.obter_configuracao("modo_selecao", "round_robin")

    def definir_modo_selecao(self, modo: str) -> None:
        """Define a estratégia de seleção do pool ('round_robin' ou 'fallback')."""
        modo_normalizado = (modo or "").strip().lower()
        if modo_normalizado not in ("round_robin", "fallback"):
            raise ValueError(f"Modo de seleção inválido: '{modo}'. Use 'round_robin' ou 'fallback'.")
        self.repositorio.salvar_configuracao("modo_selecao", modo_normalizado)
        if modo_normalizado == "round_robin":
            self._estrategia_round_robin.redefinir_indice()

    def obter_tempo_cooldown_padrao(self) -> int:
        """Retorna o tempo de cooldown padrão em segundos (padrão: 60s)."""
        valor = self.repositorio.obter_configuracao("tempo_cooldown_padrao", "60")
        try:
            return max(5, int(valor))
        except ValueError:
            return 60

    def definir_tempo_cooldown_padrao(self, segundos: int) -> None:
        """Define o tempo em segundos que uma chave aguardará após erro HTTP 429."""
        if segundos < 5:
            raise ValueError("O tempo de cooldown deve ser de no mínimo 5 segundos.")
        self.repositorio.salvar_configuracao("tempo_cooldown_padrao", str(segundos))

    # --------------------------------------------------------------------------
    # Gerenciamento de Chaves
    # --------------------------------------------------------------------------

    def adicionar_chave(
        self,
        chave: str,
        rotulo: str,
        provedor: str = "gemini",
        modelo: str = "gemini-flash-lite-latest",
        prioridade: int = 1,
        ativo: bool = True
    ) -> ChaveIA:
        """Cadastra uma nova chave no pool e persiste com segurança."""
        chave_limpa = (chave or "").strip()
        rotulo_limpo = (rotulo or "").strip()

        if not chave_limpa:
            raise ValueError("O segredo da chave da API não pode ser vazio.")
        if not rotulo_limpo:
            rotulo_limpo = f"Chave {provedor.capitalize()}"

        existente = self.repositorio.obter_chave_por_valor(chave_limpa)
        if existente:
            raise ValueError(f"Esta chave de API já está cadastrada sob o rótulo '{existente.rotulo}'.")

        chave_entidade = ChaveIA(
            id=0,
            chave=chave_limpa,
            rotulo=rotulo_limpo,
            provedor=(provedor or "gemini").strip().lower(),
            modelo=(modelo or "gemini-flash-lite-latest").strip(),
            prioridade=max(1, int(prioridade)),
            ativo=bool(ativo)
        )

        novo_id = self.repositorio.inserir_chave(chave_entidade)
        chave_entidade.id = novo_id
        logger.info(f"Nova chave de IA cadastrada com sucesso: ID={novo_id}, Rótulo='{rotulo_limpo}'.")
        return chave_entidade

    def sincronizar_ou_adicionar_chave(
        self,
        chave: str,
        rotulo: str = "Chave Principal Gemini (.env)",
        provedor: str = "gemini"
    ) -> ChaveIA:
        """Adiciona a chave se não existir, ou atualiza o registro existente sob o mesmo rótulo."""
        chave_limpa = (chave or "").strip()
        if not chave_limpa:
            raise ValueError("Chave vazia.")

        existente = self.repositorio.obter_chave_por_valor(chave_limpa)
        if existente:
            return existente

        # Se não existe pelo valor, verifica se já existe uma chave cadastrada sob este mesmo rótulo (ex: do .env)
        todas = self.repositorio.listar_todas_chaves()
        chave_com_rotulo = next((c for c in todas if c.rotulo == rotulo), None)
        if chave_com_rotulo is not None:
            self.repositorio.atualizar_credencial_chave(chave_com_rotulo.id, chave_limpa)
            logger.info(f"Credencial da chave '{rotulo}' (ID={chave_com_rotulo.id}) sincronizada e atualizada no pool.")
            chave_atualizada = self.repositorio.obter_chave_por_id(chave_com_rotulo.id)
            if chave_atualizada:
                return chave_atualizada

        return self.adicionar_chave(
            chave=chave_limpa,
            rotulo=rotulo,
            provedor=provedor,
            prioridade=1,
            ativo=True
        )

    def atualizar_chave(
        self,
        id_chave: int,
        rotulo: Optional[str] = None,
        modelo: Optional[str] = None,
        prioridade: Optional[int] = None,
        ativo: Optional[bool] = None,
        chave: Optional[str] = None
    ) -> bool:
        """Atualiza metadados cadastrais de uma chave do pool."""
        return self.repositorio.atualizar_chave(
            id_chave=id_chave,
            rotulo=rotulo,
            modelo=modelo,
            prioridade=prioridade,
            ativo=ativo,
            chave=chave
        )

    def remover_chave(self, id_chave: int) -> bool:
        """Remove uma chave do pool."""
        return self.repositorio.remover_chave(id_chave)

    def alternar_status_chave(self, id_chave: int, ativo: Optional[bool] = None) -> bool:
        """Ativa ou desativa uma chave no pool."""
        return self.repositorio.alternar_status(id_chave, ativo=ativo)

    def redefinir_cooldown_chave(self, id_chave: int) -> bool:
        """Zera o cooldown e desfaz bloqueio de erro para uma chave."""
        return self.repositorio.redefinir_cooldown_e_erros(id_chave)

    def listar_chaves(self, mascarar: bool = True) -> List[Dict[str, Any]]:
        """Lista todas as chaves cadastradas com métricas e status de cooldown."""
        chaves = self.repositorio.listar_todas_chaves()
        return [c.para_dicionario(incluir_chave_completa=not mascarar) for c in chaves]

    def obter_chave_por_id(self, id_chave: int) -> Optional[ChaveIA]:
        """Recupera uma chave por ID."""
        return self.repositorio.obter_chave_por_id(id_chave)

    def possui_chaves_cadastradas(self) -> bool:
        """Indica se há ao menos uma chave cadastrada no pool."""
        chaves = self.repositorio.listar_todas_chaves()
        return len(chaves) > 0

    def obter_chaves_aptas(self) -> List[ChaveIA]:
        """Retorna todas as chaves ativas, não bloqueadas e fora de cooldown."""
        todas = self.repositorio.listar_todas_chaves()
        return [c for c in todas if c.esta_apta()]

    # --------------------------------------------------------------------------
    # Algoritmo de Seleção e Circuit Breaker
    # --------------------------------------------------------------------------

    def selecionar_proxima_chave(self, chaves_ja_tentadas: Optional[Set[int]] = None) -> Optional[ChaveIA]:
        """
        Seleciona a próxima chave apta de acordo com o modo configurado,
        excluindo as chaves já tentadas nesta mesma requisição.
        """
        chaves_aptas = self.obter_chaves_aptas()
        if chaves_ja_tentadas:
            chaves_aptas = [c for c in chaves_aptas if c.id not in chaves_ja_tentadas]

        if not chaves_aptas:
            return None

        modo = self.obter_modo_selecao()
        if modo == "fallback":
            return self._estrategia_fallback.selecionar_chave(chaves_aptas)
        return self._estrategia_round_robin.selecionar_chave(chaves_aptas)

    # --------------------------------------------------------------------------
    # Execução de Tradução com Failover Automático
    # --------------------------------------------------------------------------

    def executar_traducao(
        self,
        texto_en: str,
        instrucoes_sistema: Optional[str] = None,
        modelo_override: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executa a tradução de um texto utilizando o pool de chaves.
        Aplica isolamento automático de falhas (Circuit Breaker):
        - Se uma chave retornar HTTP 429, entra em cooldown de 60s e a requisição
          é imediatamente retentada na próxima chave apta do pool.
        - Se retornar HTTP 403 (revogada/leaked), a chave é desativada permanentemente
          e a requisição também é imediatamente retentada na próxima chave.
        """
        if not texto_en or not texto_en.strip():
            return {"sucesso": True, "traducao": "", "tempo_segundos": 0.0, "erro": ""}

        chaves_tentadas: Set[int] = set()
        ultimo_resultado: Dict[str, Any] = {
            "sucesso": False,
            "traducao": "",
            "erro": "Nenhuma chave disponível no pool de IA."
        }

        while True:
            chave_selecionada = self.selecionar_proxima_chave(chaves_ja_tentadas=chaves_tentadas)

            # Se não houver mais chaves aptas disponíveis para esta requisição
            if chave_selecionada is None:
                # Verificar motivo da indisponibilidade para diagnóstico preciso
                todas = self.repositorio.listar_todas_chaves()
                if not todas:
                    return {
                        "sucesso": False,
                        "traducao": "",
                        "erro": "Nenhuma chave de IA cadastrada no sistema. Cadastre uma chave no Gerenciador de IA."
                    }

                ativas = [c for c in todas if c.ativo and not c.bloqueada_permanentemente]
                if not ativas:
                    return {
                        "sucesso": False,
                        "traducao": "",
                        "erro": "Todas as chaves de IA cadastradas estão desativadas ou bloqueadas por erro crítico."
                    }

                em_cooldown = [c for c in ativas if c.esta_em_cooldown()]
                if len(em_cooldown) == len(ativas):
                    menor_espera = min(c.segundos_cooldown_restantes() for c in em_cooldown)
                    return {
                        "sucesso": False,
                        "traducao": "",
                        "erro": f"Todas as chaves ativas estão em tempo de espera (HTTP 429). Tente novamente em {menor_espera}s.",
                        "em_cooldown": True,
                        "segundos_espera": menor_espera
                    }

                # Se chegamos aqui, todas as aptas foram tentadas nesta requisição e falharam
                return ultimo_resultado

            chaves_tentadas.add(chave_selecionada.id)
            try:
                adaptador = FabricaProvedoresIA.criar_adaptador(
                    chave_selecionada.provedor,
                    transportador_http=self._transportador_http
                )
                modelo_uso = modelo_override or chave_selecionada.modelo
                logger.info(
                    f"Executando tradução com chave '{chave_selecionada.rotulo}' "
                    f"({chave_selecionada.mascarar_chave()}) via {chave_selecionada.provedor}."
                )
                resultado = adaptador.traduzir(
                    chave=chave_selecionada.chave,
                    modelo=modelo_uso,
                    texto_en=texto_en,
                    instrucoes_sistema=instrucoes_sistema
                )
            except Exception as erro_exec:
                resultado = {
                    "sucesso": False,
                    "traducao": "",
                    "codigo_status": 500,
                    "tipo_erro": "erro_interno",
                    "erro": f"Exceção durante tradução: {str(erro_exec)}"
                }

            if resultado.get("sucesso"):
                self.repositorio.registrar_sucesso(chave_selecionada.id)
                resultado["id_chave"] = chave_selecionada.id
                resultado["rotulo_chave"] = chave_selecionada.rotulo
                resultado["provedor"] = chave_selecionada.provedor
                return resultado

            # Tratar falhas detectadas
            codigo_status = resultado.get("codigo_status")
            tipo_erro = resultado.get("tipo_erro")
            erro_msg = resultado.get("erro", "Falha na chamada de IA")
            ultimo_resultado = resultado

            # Caso 1: HTTP 429 ou esgotamento de quota temporário -> Cooldown automático
            if codigo_status == 429 or tipo_erro == "limite_taxa":
                tempo_cooldown = self.obter_tempo_cooldown_padrao()
                motivo = f"HTTP 429 - Limite de taxa excedido (cooldown de {tempo_cooldown}s)"
                self.repositorio.registrar_cooldown(chave_selecionada.id, tempo_cooldown, motivo)
                logger.warning(
                    f"Chave '{chave_selecionada.rotulo}' entrou em cooldown por {tempo_cooldown}s. "
                    f"Acionando failover para próxima chave..."
                )
                continue

            # Caso 2: HTTP 403 / Chave revogada ou inválida -> Bloqueio permanente
            if codigo_status == 403 or tipo_erro == "chave_invalida":
                motivo = f"HTTP {codigo_status} - Credencial inválida, revogada ou sem permissão"
                self.repositorio.registrar_bloqueio_permanente(chave_selecionada.id, motivo)
                logger.error(
                    f"Chave '{chave_selecionada.rotulo}' foi desativada permanentemente por erro de autenticação. "
                    f"Acionando failover para próxima chave..."
                )
                continue

            # Caso 3: Outros erros transitórios (rede, 500 passageiro)
            self.repositorio.registrar_falha_geral(chave_selecionada.id, erro_msg)
            logger.warning(
                f"Falha na chave '{chave_selecionada.rotulo}': {erro_msg}. "
                f"Tentando próxima chave disponível no pool..."
            )

    # --------------------------------------------------------------------------
    # Teste de Conexão de Chave
    # --------------------------------------------------------------------------

    def testar_chave(
        self,
        id_chave: Optional[int] = None,
        chave_direta: Optional[str] = None,
        provedor: str = "gemini",
        modelo: str = "gemini-flash-lite-latest"
    ) -> Dict[str, Any]:
        """Testa se uma chave cadastrada ou um valor avulso responde corretamente."""
        if id_chave is not None:
            chave_entidade = self.repositorio.obter_chave_por_id(id_chave)
            if not chave_entidade:
                return {"sucesso": False, "erro": f"Chave com ID {id_chave} não encontrada."}
            chave_valor = chave_entidade.chave
            provedor = chave_entidade.provedor
            modelo = chave_entidade.modelo
        elif chave_direta:
            chave_valor = chave_direta.strip()
        else:
            return {"sucesso": False, "erro": "ID da chave ou valor da chave deve ser fornecido."}

        try:
            adaptador = FabricaProvedoresIA.criar_adaptador(
                provedor,
                transportador_http=self._transportador_http
            )
            resultado = adaptador.testar_conexao(chave_valor, modelo)
            if id_chave is not None:
                if resultado.get("sucesso"):
                    self.repositorio.redefinir_cooldown_e_erros(id_chave)
                    self.repositorio.registrar_sucesso(id_chave)
                else:
                    cod = resultado.get("codigo_status")
                    tipo = resultado.get("tipo_erro")
                    msg_err = resultado.get("erro", "Falha de validação.")
                    if cod == 403 or tipo == "chave_invalida":
                        self.repositorio.registrar_bloqueio_permanente(id_chave, f"Teste: {msg_err}")
                    elif cod == 429 or tipo == "limite_taxa":
                        self.repositorio.registrar_cooldown(id_chave, self.obter_tempo_cooldown_padrao(), f"Teste: {msg_err}")
                    else:
                        self.repositorio.registrar_falha_geral(id_chave, f"Teste: {msg_err}")
            return resultado
        except Exception as e:
            msg_erro = str(e)
            if id_chave is not None:
                self.repositorio.registrar_falha_geral(id_chave, f"Teste: {msg_erro}")
            return {"sucesso": False, "erro": msg_erro}

    # --------------------------------------------------------------------------
    # Estatísticas e Métricas do Pool
    # --------------------------------------------------------------------------

    def obter_informacoes_completas(self) -> Dict[str, Any]:
        """Retorna visão consolidada com status do pool, configurações e lista de chaves."""
        chaves = self.repositorio.listar_todas_chaves()
        total = len(chaves)
        ativas = sum(1 for c in chaves if c.ativo and not c.bloqueada_permanentemente)
        em_cooldown = sum(1 for c in chaves if c.esta_em_cooldown())
        aptas = sum(1 for c in chaves if c.esta_apta())
        bloqueadas = sum(1 for c in chaves if c.bloqueada_permanentemente)

        total_req = sum(c.total_requisicoes for c in chaves)
        total_suc = sum(c.total_sucessos for c in chaves)
        total_fal = sum(c.total_falhas for c in chaves)

        return {
            "sucesso": True,
            "modo_selecao": self.obter_modo_selecao(),
            "tempo_cooldown_padrao": self.obter_tempo_cooldown_padrao(),
            "total_chaves": total,
            "chaves_ativas": ativas,
            "chaves_aptas": aptas,
            "chaves_em_cooldown": em_cooldown,
            "chaves_bloqueadas": bloqueadas,
            "metricas_globais": {
                "total_requisicoes": total_req,
                "total_sucessos": total_suc,
                "total_falhas": total_fal,
                "taxa_sucesso_percentual": round(total_suc / total_req * 100, 1) if total_req > 0 else 100.0
            },
            "chaves": [c.para_dicionario(incluir_chave_completa=False) for c in chaves]
        }

    # --------------------------------------------------------------------------
    # Migração e Sincronização com .env
    # --------------------------------------------------------------------------

    def migrar_chave_env_se_necessario(self) -> None:
        """
        Verifica se há chave no arquivo .env existente. Se o pool estiver vazio
        ou a chave ainda não estiver cadastrada, realiza a migração automática.
        """
        chave_env = self._ler_chave_env()
        if not chave_env:
            return

        existente = self.repositorio.obter_chave_por_valor(chave_env)
        if not existente:
            try:
                self.adicionar_chave(
                    chave=chave_env,
                    rotulo="Chave Principal Gemini (.env)",
                    provedor="gemini",
                    modelo="gemini-flash-lite-latest",
                    prioridade=1,
                    ativo=True
                )
                logger.info("Chave existente no .env migrada automaticamente para o Pool de IA.")
            except Exception as erro:
                logger.warning(f"Não foi possível migrar automaticamente a chave do .env: {erro}")

    def _ler_chave_env(self) -> str:
        """Lê o valor de CHAVE_API_GEMINI do arquivo .env ou variáveis de ambiente."""
        if os.path.exists(self.caminho_env):
            try:
                with open(self.caminho_env, "r", encoding="utf-8") as f:
                    for linha in f:
                        linha = linha.strip()
                        if linha.startswith("CHAVE_API_GEMINI="):
                            val = linha.split("=", 1)[1].strip().strip('"\'')
                            return val
            except Exception as erro_leitura:
                logger.debug(f"Erro ao ler arquivo .env em '{self.caminho_env}': {erro_leitura}")
        return os.environ.get("CHAVE_API_GEMINI", "").strip().strip('"\'')


# ==============================================================================
# Instância Singleton / Compartilhada
# ==============================================================================

_INSTANCIA_POOL_GLOBAL: Optional[GerenciadorPoolIA] = None
_LOCK_SINGLETON = threading.Lock()


def obter_instancia_pool_ia(caminho_banco: Optional[str] = None) -> GerenciadorPoolIA:
    """Retorna a instância compartilhada (Singleton) do GerenciadorPoolIA."""
    global _INSTANCIA_POOL_GLOBAL
    with _LOCK_SINGLETON:
        if _INSTANCIA_POOL_GLOBAL is None:
            _INSTANCIA_POOL_GLOBAL = GerenciadorPoolIA(caminho_banco=caminho_banco)
        return _INSTANCIA_POOL_GLOBAL


def redefinir_instancia_pool_ia(nova_instancia: Optional[GerenciadorPoolIA] = None) -> None:
    """Permite redefinir a instância global (útil em suítes de testes)."""
    global _INSTANCIA_POOL_GLOBAL
    with _LOCK_SINGLETON:
        _INSTANCIA_POOL_GLOBAL = nova_instancia
