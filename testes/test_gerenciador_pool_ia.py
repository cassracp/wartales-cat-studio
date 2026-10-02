# -*- coding: utf-8 -*-
"""
================================================================================
 Suíte de Testes Unitários e de Integração: GerenciadorPoolIA
================================================================================
 Valida:
 1. Repositório SQLite (CRUD de chaves, integridade, métricas e configurações).
 2. Estratégias de seleção (Round-Robin circular e Fallback por prioridade).
 3. Circuit Breaker (cooldown automático para 429, bloqueio permanente para 403).
 4. Recuperação automática de chaves pós-cooldown e redefinição manual.
 5. Diagnóstico claro quando todas as chaves estão em cooldown.
 6. Padrão Adapter e FabricaProvedoresIA para Gemini.
 7. Migração e sincronização com arquivo .env.
 8. Mascaramento seguro de credenciais para prevenção de vazamento.
 9. Integração com ServicoIA e MotorTraducaoLoteIA.
 10. Endpoints REST da API do servidor (/api/ia/pool/...).
 Nomenclatura 100% em Português do Brasil (pt-BR).
================================================================================
"""

import os
import io
import json
import time
import tempfile
import unittest
import urllib.error
from typing import Dict, Any, Tuple

from nucleo.gerenciador_pool_ia import (
    ChaveIA,
    GerenciadorPoolIA,
    RepositorioChavesIA,
    EstrategiaRoundRobin,
    EstrategiaFallback,
    AdaptadorGemini,
    FabricaProvedoresIA,
    redefinir_instancia_pool_ia
)
from nucleo.servico_ia import ServicoIA
from nucleo.tradutor_lote_ia import MotorTraducaoLoteIA
from servidor.servidor_api import ManipuladorRequisicaoCat


class TesteGerenciadorPoolIA(unittest.TestCase):
    """Testes completos da arquitetura do GerenciadorPoolIA."""

    def setUp(self):
        self.diretorio_temporario = tempfile.TemporaryDirectory()
        self.pasta_temp = self.diretorio_temporario.name

        self.caminho_banco = os.path.join(self.pasta_temp, "chaves_teste.db")
        self.caminho_env = os.path.join(self.pasta_temp, ".env")

        # Criar .env limpo por padrão
        with open(self.caminho_env, "w", encoding="utf-8") as f:
            f.write("CHAVE_API_GEMINI=chave_gemini_env_inicial_123456\n")

        self.repositorio = RepositorioChavesIA(self.caminho_banco)
        self.pool = GerenciadorPoolIA(
            repositorio=self.repositorio,
            caminho_env=self.caminho_env
        )

    def tearDown(self):
        redefinir_instancia_pool_ia(None)
        del self.pool
        del self.repositorio
        self.diretorio_temporario.cleanup()

    # --------------------------------------------------------------------------
    # 1. Repositório e Migração .env
    # --------------------------------------------------------------------------

    def teste_inicializacao_repositorio_e_migracao_env(self):
        """Valida que a inicialização do pool importa automaticamente a chave do .env."""
        chaves = self.pool.listar_chaves(mascarar=False)
        self.assertEqual(len(chaves), 1)
        primeira = chaves[0]
        self.assertEqual(primeira["chave"], "chave_gemini_env_inicial_123456")
        self.assertEqual(primeira["rotulo"], "Chave Principal Gemini (.env)")
        self.assertEqual(primeira["prioridade"], 1)
        self.assertTrue(primeira["ativo"])
        self.assertEqual(primeira["chave_mascarada"], "chav...3456")

    def teste_adicionar_e_listar_chaves_com_mascaramento(self):
        """Testa adição de múltiplas chaves e mascaramento seguro de credenciais."""
        chave2 = self.pool.adicionar_chave(
            chave="AIzaSyNovaChaveSegura987654321",
            rotulo="Chave Backup 2",
            provedor="gemini",
            modelo="gemini-flash-lite-latest",
            prioridade=2
        )
        self.assertGreater(chave2.id, 0)

        # Listagem mascarada (padrão de segurança)
        chaves_mascaradas = self.pool.listar_chaves(mascarar=True)
        self.assertEqual(len(chaves_mascaradas), 2)
        c2 = next(c for c in chaves_mascaradas if c["id"] == chave2.id)
        self.assertEqual(c2["chave"], "AIza...4321")
        self.assertEqual(c2["chave_mascarada"], "AIza...4321")

        # Validação de duplicidade
        with self.assertRaises(ValueError):
            self.pool.adicionar_chave(
                chave="AIzaSyNovaChaveSegura987654321",
                rotulo="Chave Duplicada"
            )

        # Validação de chave vazia
        with self.assertRaises(ValueError):
            self.pool.adicionar_chave(chave="", rotulo="Chave Vazia")

    def teste_atualizar_e_alternar_status_chave(self):
        """Testa atualização de metadados e desativação/ativação de chaves."""
        chave = self.pool.adicionar_chave(
            chave="chave_para_teste_atualizacao_999",
            rotulo="Chave Temporária",
            prioridade=3
        )
        id_chave = chave.id

        # Atualizar metadados
        sucesso_up = self.pool.atualizar_chave(
            id_chave=id_chave,
            rotulo="Chave Atualizada",
            prioridade=5,
            modelo="gemini-1.5-pro"
        )
        self.assertTrue(sucesso_up)

        chave_obtida = self.pool.obter_chave_por_id(id_chave)
        self.assertIsNotNone(chave_obtida)
        self.assertEqual(chave_obtida.rotulo, "Chave Atualizada")
        self.assertEqual(chave_obtida.prioridade, 5)
        self.assertEqual(chave_obtida.modelo, "gemini-1.5-pro")

        # Alternar status (toggle ativo -> inativo)
        self.pool.alternar_status_chave(id_chave, ativo=False)
        chave_inativa = self.pool.obter_chave_por_id(id_chave)
        self.assertFalse(chave_inativa.ativo)
        self.assertFalse(chave_inativa.esta_apta())

        # Remover chave
        removido = self.pool.remover_chave(id_chave)
        self.assertTrue(removido)
        self.assertIsNone(self.pool.obter_chave_por_id(id_chave))

    # --------------------------------------------------------------------------
    # 2. Estratégias de Seleção (Round-Robin e Fallback)
    # --------------------------------------------------------------------------

    def teste_estrategia_round_robin_balanceamento(self):
        """Valida que o modo Round-Robin distribui de forma circular perfeita entre chaves aptas."""
        # Limpar pool existente
        for c in self.pool.listar_chaves(mascarar=False):
            self.pool.remover_chave(c["id"])

        c1 = self.pool.adicionar_chave(chave="chave_rr_1", rotulo="Chave 1", prioridade=1)
        c2 = self.pool.adicionar_chave(chave="chave_rr_2", rotulo="Chave 2", prioridade=2)
        c3 = self.pool.adicionar_chave(chave="chave_rr_3", rotulo="Chave 3", prioridade=3)

        self.pool.definir_modo_selecao("round_robin")
        self.assertEqual(self.pool.obter_modo_selecao(), "round_robin")

        # Sequência circular: 1 -> 2 -> 3 -> 1 -> 2 -> 3
        ids_esperados = [c1.id, c2.id, c3.id, c1.id, c2.id, c3.id]
        ids_obtidos = []
        for _ in range(6):
            escolhida = self.pool.selecionar_proxima_chave()
            self.assertIsNotNone(escolhida)
            ids_obtidos.append(escolhida.id)

        self.assertEqual(ids_obtidos, ids_esperados)

        # Se a chave 2 for desativada, a rotação deve pular para 3 e 1
        self.pool.alternar_status_chave(c2.id, ativo=False)
        escolhida_a = self.pool.selecionar_proxima_chave()
        escolhida_b = self.pool.selecionar_proxima_chave()
        self.assertIn(escolhida_a.id, [c1.id, c3.id])
        self.assertIn(escolhida_b.id, [c1.id, c3.id])
        self.assertNotEqual(escolhida_a.id, c2.id)
        self.assertNotEqual(escolhida_b.id, c2.id)

    def teste_estrategia_fallback_prioridade(self):
        """Valida que o modo Fallback respeita estritamente a ordem de prioridade."""
        for c in self.pool.listar_chaves(mascarar=False):
            self.pool.remover_chave(c["id"])

        c_pri1 = self.pool.adicionar_chave(chave="chave_fb_1", rotulo="Primária", prioridade=1)
        c_pri2 = self.pool.adicionar_chave(chave="chave_fb_2", rotulo="Secundária", prioridade=2)
        c_pri3 = self.pool.adicionar_chave(chave="chave_fb_3", rotulo="Terciária", prioridade=3)

        self.pool.definir_modo_selecao("fallback")
        self.assertEqual(self.pool.obter_modo_selecao(), "fallback")

        # Deve escolher repetidamente a prioridade 1 enquanto estiver apta
        for _ in range(4):
            escolhida = self.pool.selecionar_proxima_chave()
            self.assertEqual(escolhida.id, c_pri1.id)

        # Simula que a prioridade 1 entrou em cooldown
        self.repositorio.registrar_cooldown(c_pri1.id, tempo_cooldown_segundos=120, motivo="Teste 429")

        # Agora deve escolher a prioridade 2
        escolhida_p2 = self.pool.selecionar_proxima_chave()
        self.assertEqual(escolhida_p2.id, c_pri2.id)

        # Se a prioridade 2 for desativada, cai para prioridade 3
        self.pool.alternar_status_chave(c_pri2.id, ativo=False)
        escolhida_p3 = self.pool.selecionar_proxima_chave()
        self.assertEqual(escolhida_p3.id, c_pri3.id)

    # --------------------------------------------------------------------------
    # 3. Circuit Breaker e Failover Automático
    # --------------------------------------------------------------------------

    def teste_circuit_breaker_cooldown_429_e_failover(self):
        """
        Valida que se uma chave retornar HTTP 429 (Rate Limit):
        1. A chave entra em cooldown automático (ex: 60s).
        2. A requisição é imediatamente repassada à próxima chave disponível.
        3. A tradução é concluída com sucesso sem repassar erro ao usuário.
        """
        for c in self.pool.listar_chaves(mascarar=False):
            self.pool.remover_chave(c["id"])

        c_falha = self.pool.adicionar_chave(chave="chave_limite_429", rotulo="Chave Sobrecarregada", prioridade=1)
        c_reserva = self.pool.adicionar_chave(chave="chave_reserva_ok", rotulo="Chave Reserva", prioridade=2)

        self.pool.definir_modo_selecao("fallback")
        self.pool.definir_tempo_cooldown_padrao(60)

        # Mock de transportador HTTP
        def transportador_mock(url: str, payload_bytes: bytes, headers: Dict[str, str]) -> Tuple[bytes, int]:
            if "chave_limite_429" in url:
                fp = io.BytesIO(b'{"error": {"code": 429, "message": "RESOURCE_EXHAUSTED"}}')
                raise urllib.error.HTTPError(url, 429, "Too Many Requests", hdrs={}, fp=fp)
            elif "chave_reserva_ok" in url:
                resposta_gemini = {
                    "candidates": [{
                        "content": {
                            "parts": [{"text": json.dumps({"pt": "Espada de Ferro"})}]
                        }
                    }]
                }
                return json.dumps(resposta_gemini).encode("utf-8"), 200
            raise ValueError(f"URL não esperada: {url}")

        self.pool._transportador_http = transportador_mock

        resultado = self.pool.executar_traducao("Iron Sword")

        # 1. Tradução deve ter sucesso graças ao failover automático
        self.assertTrue(resultado["sucesso"], f"Esperava sucesso mas obteve: {resultado.get('erro')}")
        self.assertEqual(resultado["traducao"], "Espada de Ferro")
        self.assertEqual(resultado["id_chave"], c_reserva.id)

        # 2. Primeira chave deve estar devidamente em cooldown
        chave_1_banco = self.pool.obter_chave_por_id(c_falha.id)
        self.assertTrue(chave_1_banco.esta_em_cooldown())
        self.assertGreater(chave_1_banco.segundos_cooldown_restantes(), 50)
        self.assertIn("HTTP 429", chave_1_banco.motivo_cooldown)
        self.assertEqual(chave_1_banco.total_falhas, 1)

        # 3. Segunda chave deve registrar sucesso
        chave_2_banco = self.pool.obter_chave_por_id(c_reserva.id)
        self.assertEqual(chave_2_banco.total_sucessos, 1)

    def teste_circuit_breaker_bloqueio_permanente_403(self):
        """
        Valida que se uma chave retornar HTTP 403 (revogada ou vazada):
        1. A chave é bloqueada permanentemente e desativada.
        2. A requisição faz failover para a próxima chave.
        """
        for c in self.pool.listar_chaves(mascarar=False):
            self.pool.remover_chave(c["id"])

        c_revogada = self.pool.adicionar_chave(chave="chave_revogada_403", rotulo="Chave Revogada", prioridade=1)
        c_reserva = self.pool.adicionar_chave(chave="chave_reserva_2", rotulo="Chave Reserva", prioridade=2)

        def transportador_mock(url: str, payload_bytes: bytes, headers: Dict[str, str]) -> Tuple[bytes, int]:
            if "chave_revogada_403" in url:
                fp = io.BytesIO(b'{"error": {"code": 403, "message": "API_KEY_INVALID"}}')
                raise urllib.error.HTTPError(url, 403, "Forbidden", hdrs={}, fp=fp)
            elif "chave_reserva_2" in url:
                resposta_gemini = {
                    "candidates": [{
                        "content": {
                            "parts": [{"text": json.dumps({"pt": "Escudo de Madeira"})}]
                        }
                    }]
                }
                return json.dumps(resposta_gemini).encode("utf-8"), 200
            raise ValueError(f"URL não esperada: {url}")

        self.pool._transportador_http = transportador_mock
        resultado = self.pool.executar_traducao("Wooden Shield")

        self.assertTrue(resultado["sucesso"])
        self.assertEqual(resultado["traducao"], "Escudo de Madeira")

        chave_bloqueada = self.pool.obter_chave_por_id(c_revogada.id)
        self.assertTrue(chave_bloqueada.bloqueada_permanentemente)
        self.assertFalse(chave_bloqueada.ativo)
        self.assertFalse(chave_bloqueada.esta_apta())

    def teste_todas_chaves_em_cooldown_retorna_diagnostico(self):
        """Valida a mensagem explicativa quando todas as chaves estão em cooldown."""
        for c in self.pool.listar_chaves(mascarar=False):
            self.pool.remover_chave(c["id"])

        c1 = self.pool.adicionar_chave(chave="k1", rotulo="K1")
        c2 = self.pool.adicionar_chave(chave="k2", rotulo="K2")

        self.repositorio.registrar_cooldown(c1.id, 45, "Rate limit")
        self.repositorio.registrar_cooldown(c2.id, 30, "Rate limit")

        resultado = self.pool.executar_traducao("Armor")
        self.assertFalse(resultado["sucesso"])
        self.assertTrue(resultado.get("em_cooldown"))
        self.assertIn("tempo de espera (HTTP 429)", resultado.get("erro", ""))
        self.assertGreaterEqual(resultado.get("segundos_espera", 0), 25)

    def teste_recuperacao_apos_cooldown_e_redefinicao_manual(self):
        """Valida que o cooldown expira pelo tempo e que a redefinição manual funciona."""
        for c in self.pool.listar_chaves(mascarar=False):
            self.pool.remover_chave(c["id"])

        c1 = self.pool.adicionar_chave(chave="k_recuperar", rotulo="K Recuperar")
        # Coloca em cooldown no passado
        with self.repositorio.obter_conexao() as conn:
            conn.execute(
                "UPDATE pool_chaves_ia SET em_cooldown_ate = ?, motivo_cooldown = 'Teste Antigo' WHERE id = ?",
                (time.time() - 10, c1.id)
            )
            conn.commit()

        chave_passada = self.pool.obter_chave_por_id(c1.id)
        self.assertFalse(chave_passada.esta_em_cooldown())
        self.assertTrue(chave_passada.esta_apta())

        # Testar redefinição manual para chave com bloqueio
        self.repositorio.registrar_bloqueio_permanente(c1.id, "Erro teste")
        self.assertFalse(self.pool.obter_chave_por_id(c1.id).esta_apta())

        sucesso_reset = self.pool.redefinir_cooldown_chave(c1.id)
        self.assertTrue(sucesso_reset)
        chave_resetada = self.pool.obter_chave_por_id(c1.id)
        self.assertTrue(chave_resetada.ativo)
        self.assertFalse(chave_resetada.bloqueada_permanentemente)
        self.assertTrue(chave_resetada.esta_apta())

    # --------------------------------------------------------------------------
    # 4. Padrão Adapter e Integração ServicoIA
    # --------------------------------------------------------------------------

    def teste_adaptador_gemini_sucesso_e_teste_conexao(self):
        """Testa o AdaptadorGemini com mock simulando validação de conexão."""
        def transportador_ok(url: str, payload_bytes: bytes, headers: Dict[str, str]) -> Tuple[bytes, int]:
            resp = {
                "candidates": [{
                    "content": {
                        "parts": [{"text": json.dumps({"pt": "Olá"})}]
                    }
                }]
            }
            return json.dumps(resp).encode("utf-8"), 200

        adaptador = FabricaProvedoresIA.criar_adaptador("gemini", transportador_http=transportador_ok)
        res_teste = adaptador.testar_conexao("chave_valida", "gemini-flash-lite-latest")
        self.assertTrue(res_teste["sucesso"])
        self.assertIn("sucesso", res_teste["mensagem"])

    def teste_integracao_servico_ia_com_pool(self):
        """Valida que o ServicoIA delega traduções para o GerenciadorPoolIA de forma transparente."""
        for c in self.pool.listar_chaves(mascarar=False):
            self.pool.remover_chave(c["id"])

        self.pool.adicionar_chave(chave="chave_pool_servico", rotulo="Chave Pool", prioridade=1)

        def transportador_mock(url: str, payload_bytes: bytes, headers: Dict[str, str]) -> Tuple[bytes, int]:
            resp = {
                "candidates": [{
                    "content": {
                        "parts": [{"text": json.dumps({"pt": "Arco Curto"})}]
                    }
                }]
            }
            return json.dumps(resp).encode("utf-8"), 200

        self.pool._transportador_http = transportador_mock

        servico = ServicoIA(gerenciador_pool=self.pool)
        resultado = servico.traduzir_texto("Short Bow")

        self.assertTrue(resultado["sucesso"])
        self.assertEqual(resultado["traducao"], "Arco Curto")
        self.assertEqual(resultado.get("rotulo_chave"), "Chave Pool")

    def teste_motor_traducao_lote_ia_aceita_pool(self):
        """Valida que o MotorTraducaoLoteIA aceita e preserva o pool injetado."""
        motor = MotorTraducaoLoteIA(gerenciador_pool=self.pool)
        self.assertEqual(motor.gerenciador_pool, self.pool)

    # --------------------------------------------------------------------------
    # 5. Métricas e Estatísticas Completas
    # --------------------------------------------------------------------------

    def teste_obter_informacoes_completas(self):
        """Valida a consolidação de métricas globais e status do pool."""
        info = self.pool.obter_informacoes_completas()
        self.assertTrue(info["sucesso"])
        self.assertIn("modo_selecao", info)
        self.assertIn("chaves", info)
        self.assertIn("metricas_globais", info)
        self.assertGreaterEqual(info["total_chaves"], 1)

    # --------------------------------------------------------------------------
    # 6. Casos de Borda e Robustez Adicionais
    # --------------------------------------------------------------------------

    def teste_sincronizacao_chave_env_atualiza_existente_sem_duplicata(self):
        """Valida que atualizar a credencial do .env atualiza a chave existente sem gerar registros duplicados."""
        # Inicialmente há 1 chave do .env
        chaves_iniciais = self.pool.listar_chaves(mascarar=False)
        self.assertEqual(len(chaves_iniciais), 1)
        id_chave_original = chaves_iniciais[0]["id"]

        # Nova chave no .env com mesmo rótulo
        chave_atualizada = self.pool.sincronizar_ou_adicionar_chave(
            chave="nova_chave_gemini_rotacionada_99999",
            rotulo="Chave Principal Gemini (.env)"
        )
        self.assertEqual(chave_atualizada.id, id_chave_original)
        self.assertEqual(chave_atualizada.chave, "nova_chave_gemini_rotacionada_99999")

        # Não deve haver duplicata no banco
        todas = self.pool.listar_chaves(mascarar=False)
        self.assertEqual(len(todas), 1)
        self.assertEqual(todas[0]["chave"], "nova_chave_gemini_rotacionada_99999")

    def teste_atualizar_chave_com_nova_credencial(self):
        """Testa atualização cadastral incluindo o segredo da chave da API."""
        chave = self.pool.adicionar_chave(
            chave="chave_antiga_111",
            rotulo="Chave Teste Atualizacao",
            prioridade=2
        )
        sucesso = self.pool.atualizar_chave(
            id_chave=chave.id,
            chave="chave_renovada_222",
            rotulo="Chave Teste Renovada",
            prioridade=1
        )
        self.assertTrue(sucesso)
        obtida = self.pool.obter_chave_por_id(chave.id)
        self.assertEqual(obtida.chave, "chave_renovada_222")
        self.assertEqual(obtida.rotulo, "Chave Teste Renovada")
        self.assertEqual(obtida.prioridade, 1)

    def teste_testar_chave_atualiza_estado_no_banco(self):
        """Valida que executar testar_chave com id_chave persiste o resultado no banco."""
        chave_bloquear = self.pool.adicionar_chave(
            chave="chave_para_bloquear",
            rotulo="Chave Para Bloquear"
        )

        def mock_403(url, payload, headers):
            fp = io.BytesIO(b'{"error": {"code": 403, "message": "API_KEY_INVALID"}}')
            raise urllib.error.HTTPError(url, 403, "Forbidden", hdrs={}, fp=fp)

        self.pool._transportador_http = mock_403
        res = self.pool.testar_chave(id_chave=chave_bloquear.id)
        self.assertFalse(res["sucesso"])

        banco_bloqueada = self.pool.obter_chave_por_id(chave_bloquear.id)
        self.assertTrue(banco_bloqueada.bloqueada_permanentemente)
        self.assertFalse(banco_bloqueada.ativo)

        # Agora mock de sucesso para reverter e limpar erros
        def mock_200(url, payload, headers):
            resp = {"candidates": [{"content": {"parts": [{"text": json.dumps({"pt": "Teste OK"})}]}}]}
            return json.dumps(resp).encode("utf-8"), 200

        self.pool._transportador_http = mock_200
        res_ok = self.pool.testar_chave(id_chave=chave_bloquear.id)
        self.assertTrue(res_ok["sucesso"])

        banco_restaurada = self.pool.obter_chave_por_id(chave_bloquear.id)
        self.assertTrue(banco_restaurada.ativo)
        self.assertFalse(banco_restaurada.bloqueada_permanentemente)
        self.assertFalse(banco_restaurada.esta_em_cooldown())

    def teste_adaptador_gemini_limpeza_markdown_e_safety(self):
        """Valida a extração de JSON envolvido em blocos markdown e tratamento de resposta bloqueada."""
        # 1. Resposta com cercas de código ```json ... ```
        def mock_md(url, payload, headers):
            resp = {
                "candidates": [{
                    "content": {
                        "parts": [{"text": "```json\n{\"pt\": \"Adaga de Aço\"}\n```"}]
                    }
                }]
            }
            return json.dumps(resp).encode("utf-8"), 200

        adaptador = FabricaProvedoresIA.criar_adaptador("google", transportador_http=mock_md)
        res_md = adaptador.traduzir(chave="k", modelo="models/gemini-flash-lite-latest", texto_en="Steel Dagger")
        self.assertTrue(res_md["sucesso"])
        self.assertEqual(res_md["traducao"], "Adaga de Aço")

        # 2. Resposta com bloqueio de segurança (finishReason: SAFETY)
        def mock_safety(url, payload, headers):
            resp = {
                "candidates": [{
                    "finishReason": "SAFETY"
                }]
            }
            return json.dumps(resp).encode("utf-8"), 200

        adaptador_safety = FabricaProvedoresIA.criar_adaptador("gemini", transportador_http=mock_safety)
        res_safe = adaptador_safety.traduzir(chave="k", modelo="gemini-flash-lite-latest", texto_en="Dangerous text")
        self.assertFalse(res_safe["sucesso"])
        self.assertEqual(res_safe["tipo_erro"], "resposta_bloqueada")

    def teste_leitura_env_com_aspas_e_espacos(self):
        """Valida que chaves envolvidas por aspas duplas ou simples no .env são sanitizadas."""
        caminho_env_aspas = os.path.join(self.pasta_temp, "env_aspas.env")
        with open(caminho_env_aspas, "w", encoding="utf-8") as f:
            f.write('CHAVE_API_GEMINI="AIzaSyChaveComAspas12345"\n')

        pool_aspas = GerenciadorPoolIA(
            caminho_banco=os.path.join(self.pasta_temp, "db_aspas.db"),
            caminho_env=caminho_env_aspas
        )
        chaves = pool_aspas.listar_chaves(mascarar=False)
        self.assertEqual(len(chaves), 1)
        self.assertEqual(chaves[0]["chave"], "AIzaSyChaveComAspas12345")

    def teste_motor_lote_grava_export_com_traducoes(self):
        """Valida que MotorTraducaoLoteIA._gravar_arquivo_export grava as traduções do mapa no XML."""
        caminho_en = os.path.join(self.pasta_temp, "export_en_amostra.xml")
        caminho_pt = os.path.join(self.pasta_temp, "export_pt_amostra.xml")

        conteudo_xml = """<cdb project="Wartales" version="1" lang="en">
    <sheet name="ui">
        <btn_confirm>
            <text>Confirm</text>
        </btn_confirm>
    </sheet>
</cdb>"""
        with open(caminho_en, "w", encoding="utf-8") as f:
            f.write(conteudo_xml)

        mapa = {"ui/btn_confirm/text": "Confirmar"}
        MotorTraducaoLoteIA._gravar_arquivo_export(caminho_en, caminho_pt, mapa)

        self.assertTrue(os.path.exists(caminho_pt))
        with open(caminho_pt, "r", encoding="utf-8") as f:
            conteudo_pt = f.read()

        self.assertIn("lang=\"pt-BR\"", conteudo_pt)
        self.assertIn("<text>Confirmar</text>", conteudo_pt)


if __name__ == "__main__":
    unittest.main(verbosity=2)
