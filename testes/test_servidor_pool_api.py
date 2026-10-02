# -*- coding: utf-8 -*-
"""
================================================================================
 Suíte de Testes de Integração de Endpoints REST: Pool de IA
================================================================================
 Valida os manipuladores de requisição HTTP (SimpleHTTPRequestHandler) para:
 - GET /api/ia/pool
 - GET /api/ia/pool/chaves
 - POST /api/ia/pool/chaves
 - POST /api/ia/pool/chaves/toggle
 - POST /api/ia/pool/chaves/remover
 - POST /api/ia/pool/chaves/redefinir_cooldown
 - POST /api/ia/pool/chaves/testar
 - POST /api/ia/pool/configuracao
 - DELETE /api/ia/pool/chaves/<id>
 Nomenclatura 100% em Português do Brasil (pt-BR).
================================================================================
"""

import io
import json
import unittest
from typing import Tuple, Dict, Any, Optional
from unittest.mock import MagicMock

from servidor import servidor_api
from servidor.servidor_api import ManipuladorRequisicaoCat
from nucleo.gerenciador_pool_ia import GerenciadorPoolIA, RepositorioChavesIA


class RequisicaoFalsa:
    """Simula o socket da requisição HTTP para o SimpleHTTPRequestHandler."""
    def __init__(self, corpo_bytes: bytes = b""):
        self._arquivo = io.BytesIO(corpo_bytes)

    def makefile(self, *args, **kwargs):
        return self._arquivo


def simular_requisicao_http(metodo: str, caminho: str, payload: dict = None) -> Tuple[int, dict]:
    """Cria uma instância de ManipuladorRequisicaoCat e executa a requisição."""
    corpo = json.dumps(payload).encode("utf-8") if payload is not None else b""
    socket_falso = RequisicaoFalsa(corpo)

    # Mock do cliente
    handler = ManipuladorRequisicaoCat.__new__(ManipuladorRequisicaoCat)
    handler.rfile = socket_falso.makefile()
    handler.wfile = io.BytesIO()
    handler.headers = {
        "Content-Length": str(len(corpo)),
        "Content-Type": "application/json"
    }
    handler.command = metodo
    handler.path = caminho
    handler.request_version = "HTTP/1.1"
    handler.client_address = ("127.0.0.1", 12345)
    handler.server = MagicMock()

    # Interceptar send_response e send_header
    status_capturado = [200]

    def fake_send_response(code, message=None):
        status_capturado[0] = code

    handler.send_response = fake_send_response
    handler.send_header = lambda k, v: None
    handler.end_headers = lambda: None

    if metodo == "GET":
        handler.do_GET()
    elif metodo == "POST":
        handler.do_POST()
    elif metodo == "DELETE":
        handler.do_DELETE()

    resposta_bytes = handler.wfile.getvalue()
    try:
        dados_resposta = json.loads(resposta_bytes.decode("utf-8"))
    except Exception:
        dados_resposta = {"raw": resposta_bytes.decode("utf-8", errors="replace")}

    return status_capturado[0], dados_resposta


class TesteEndpointsPoolIA(unittest.TestCase):
    """Testa diretamente o comportamento das rotas REST de gerenciamento do pool."""

    def setUp(self):
        # Configurar repositório isolado em memória para o pool da API durante os testes
        self.repositorio_temp = RepositorioChavesIA(":memory:")
        self.pool_temp = GerenciadorPoolIA(
            repositorio=self.repositorio_temp,
            caminho_env="inexistente.env"
        )
        self.pool_original = servidor_api.GERENCIADOR_POOL_IA
        servidor_api.GERENCIADOR_POOL_IA = self.pool_temp

    def tearDown(self):
        servidor_api.GERENCIADOR_POOL_IA = self.pool_original

    def teste_fluxo_completo_endpoints_pool(self):
        """Testa o ciclo de vida: listagem inicial, cadastro, toggle, config, teste e remoção."""
        # 1. GET /api/ia/pool inicial
        status, dados = simular_requisicao_http("GET", "/api/ia/pool")
        self.assertEqual(status, 200)
        self.assertTrue(dados["sucesso"])
        self.assertEqual(dados["total_chaves"], 0)

        # 2. POST /api/ia/pool/chaves (cadastrar chave)
        status, res_cad = simular_requisicao_http("POST", "/api/ia/pool/chaves", {
            "chave": "AIzaSyChaveApiHttpEndpoint123456",
            "rotulo": "Chave Endpoint Teste",
            "provedor": "gemini",
            "modelo": "gemini-flash-lite-latest",
            "prioridade": 1,
            "ativo": True
        })
        self.assertEqual(status, 200)
        self.assertTrue(res_cad["sucesso"])
        id_chave = res_cad["chave"]["id"]
        self.assertGreater(id_chave, 0)
        self.assertEqual(res_cad["chave"]["chave_mascarada"], "AIza...3456")

        # 3. GET /api/ia/pool/chaves
        status, res_list = simular_requisicao_http("GET", "/api/ia/pool/chaves")
        self.assertEqual(status, 200)
        self.assertEqual(len(res_list["chaves"]), 1)
        self.assertEqual(res_list["chaves"][0]["rotulo"], "Chave Endpoint Teste")

        # 4. POST /api/ia/pool/chaves/toggle (desativar)
        status, res_tog = simular_requisicao_http("POST", "/api/ia/pool/chaves/toggle", {
            "id": id_chave,
            "ativo": False
        })
        self.assertEqual(status, 200)
        self.assertTrue(res_tog["sucesso"])
        chave_atualizada = self.pool_temp.obter_chave_por_id(id_chave)
        self.assertFalse(chave_atualizada.ativo)

        # 5. POST /api/ia/pool/chaves/redefinir_cooldown
        status, res_reset = simular_requisicao_http("POST", "/api/ia/pool/chaves/redefinir_cooldown", {
            "id": id_chave
        })
        self.assertEqual(status, 200)
        self.assertTrue(res_reset["sucesso"])
        self.assertTrue(self.pool_temp.obter_chave_por_id(id_chave).ativo)

        # 6. POST /api/ia/pool/configuracao
        status, res_cfg = simular_requisicao_http("POST", "/api/ia/pool/configuracao", {
            "modo_selecao": "fallback",
            "tempo_cooldown_padrao": 90
        })
        self.assertEqual(status, 200)
        self.assertEqual(res_cfg["modo_selecao"], "fallback")
        self.assertEqual(res_cfg["tempo_cooldown_padrao"], 90)

        # 7. POST /api/ia/pool/chaves/testar (com mock)
        def mock_transp(url, payload, headers):
            resp = {"candidates": [{"content": {"parts": [{"text": json.dumps({"pt": "Teste"})}]}}]}
            return json.dumps(resp).encode("utf-8"), 200

        self.pool_temp._transportador_http = mock_transp
        status, res_teste = simular_requisicao_http("POST", "/api/ia/pool/chaves/testar", {
            "id": id_chave
        })
        self.assertEqual(status, 200)
        self.assertTrue(res_teste["sucesso"])

        # 8. POST /api/ia/pool/chaves/atualizar
        status, res_up = simular_requisicao_http("POST", "/api/ia/pool/chaves/atualizar", {
            "id": id_chave,
            "rotulo": "Chave Atualizada REST",
            "prioridade": 3
        })
        self.assertEqual(status, 200)
        self.assertTrue(res_up["sucesso"])
        self.assertEqual(res_up["chave"]["rotulo"], "Chave Atualizada REST")
        self.assertEqual(res_up["chave"]["prioridade"], 3)

        # 9. DELETE /api/ia/pool/chaves/<id>
        status, res_del = simular_requisicao_http("DELETE", f"/api/ia/pool/chaves/{id_chave}")
        self.assertEqual(status, 200)
        self.assertTrue(res_del["sucesso"])
        self.assertIsNone(self.pool_temp.obter_chave_por_id(id_chave))

    def teste_validacoes_e_erros_endpoints(self):
        """Testa o tratamento elegante de erros e validações em endpoints do pool."""
        # 1. Cadastro sem chave (deve retornar 400)
        status, res = simular_requisicao_http("POST", "/api/ia/pool/chaves", {
            "chave": "",
            "rotulo": "Sem Chave"
        })
        self.assertEqual(status, 400)
        self.assertIn("erro", res)

        # 2. Cadastro com chave válida
        status, res_ok = simular_requisicao_http("POST", "/api/ia/pool/chaves", {
            "chave": "AIzaSyChaveUnicaParaErro400",
            "rotulo": "Chave Unica"
        })
        self.assertEqual(status, 200)
        id_chave = res_ok["chave"]["id"]

        # 3. Cadastro duplicado da mesma chave (deve retornar 400)
        status, res_dup = simular_requisicao_http("POST", "/api/ia/pool/chaves", {
            "chave": "AIzaSyChaveUnicaParaErro400",
            "rotulo": "Chave Duplicada"
        })
        self.assertEqual(status, 400)
        self.assertIn("já está cadastrada", res_dup.get("erro", ""))

        # 4. Configuração com modo inválido (deve retornar 400)
        status, res_modo = simular_requisicao_http("POST", "/api/ia/pool/configuracao", {
            "modo_selecao": "modo_invalido_xyz"
        })
        self.assertEqual(status, 400)

        # 5. Configuração com cooldown menor que 5s (deve retornar 400)
        status, res_cool = simular_requisicao_http("POST", "/api/ia/pool/configuracao", {
            "tempo_cooldown_padrao": 2
        })
        self.assertEqual(status, 400)

        # 6. Atualização de chave inexistente (deve retornar 404)
        status, res_inex = simular_requisicao_http("POST", "/api/ia/pool/chaves/atualizar", {
            "id": 999999,
            "rotulo": "Fantasma"
        })
        self.assertEqual(status, 404)

        # 7. Toggle com ID inválido <= 0 (deve retornar 400)
        status, res_tog = simular_requisicao_http("POST", "/api/ia/pool/chaves/toggle", {
            "id": 0
        })
        self.assertEqual(status, 400)

        # 8. Remover chave com ID inexistente (deve retornar 404)
        status, res_rem = simular_requisicao_http("POST", "/api/ia/pool/chaves/remover", {
            "id": 999999
        })
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main(verbosity=2)
