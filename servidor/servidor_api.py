"""
Servidor REST API e servidor de arquivos estáticos para o Wartales CAT Studio.
Desenvolvido com a biblioteca padrão do Python (http.server.ThreadingHTTPServer),
sem necessidade de dependências externas como Flask ou FastAPI.
"""

import json
import logging
import mimetypes
import os
import sys
import urllib.parse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict

# Adicionar diretório raiz ao sys.path para importações relativas
DIRETORIO_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if DIRETORIO_RAIZ not in sys.path:
    sys.path.insert(0, DIRETORIO_RAIZ)

from nucleo.banco_dados import GerenciadorBancoDados
from nucleo.servico_qa import ServicoGarantiaQualidade
from nucleo.servico_glossario import ServicoGlossario
from nucleo.servico_propagacao import ServicoAutoPropagacao
from nucleo.sincronizador import SincronizadorXml
from nucleo.empacotador_pak import EmpacotadorPakHeaps
from nucleo.gerenciador_projetos import GerenciadorProjetos
from nucleo.memoria_global import MemoriaTraducaoGlobal
from nucleo.tradutor_lote_ia import MotorTraducaoLoteIA
from nucleo.gerenciador_pool_ia import GerenciadorPoolIA, obter_instancia_pool_ia, CatalogoModelosIA
from nucleo.aplicador_glossario_ia import AplicadorGlossarioIA
from nucleo.servico_ia import ServicoIA, CHAVE_PADRAO_GEMINI
from exportadores.gerador_distribuicao import GeradorDistribuicao
from nucleo.servico_relatorio import ServicoRelatorio

GERENCIADOR_PROJETOS = GerenciadorProjetos()
PROJETO_ATIVO = GERENCIADOR_PROJETOS.obter_projeto_ativo()
CAMINHO_BANCO = GERENCIADOR_PROJETOS.obter_caminho_absoluto(PROJETO_ATIVO.get("caminho_banco", "dados/banco/wartales_cat.db"))
GERENCIADOR_BANCO = GerenciadorBancoDados(CAMINHO_BANCO)
SERVICO_GLOSSARIO = ServicoGlossario(GERENCIADOR_BANCO)
SERVICO_PROPAGACAO = ServicoAutoPropagacao(GERENCIADOR_BANCO)
SERVICO_SINCRONIZADOR = SincronizadorXml(GERENCIADOR_BANCO)
MEMORIA_GLOBAL = MemoriaTraducaoGlobal()
GERENCIADOR_POOL_IA = obter_instancia_pool_ia()
CATALOGO_MODELOS_IA = CatalogoModelosIA()
APLICADOR_GLOSSARIO_IA = AplicadorGlossarioIA(lambda: GERENCIADOR_BANCO.listar_glossario())
MOTOR_IA_LOTE = MotorTraducaoLoteIA(MEMORIA_GLOBAL, gerenciador_pool=GERENCIADOR_POOL_IA, aplicador_glossario=APLICADOR_GLOSSARIO_IA)
SERVICO_RELATORIO = ServicoRelatorio()

CHAVE_CONFIGURADA = GERENCIADOR_PROJETOS.config.get("chave_api_gemini", "")
if CHAVE_CONFIGURADA:
    try:
        GERENCIADOR_POOL_IA.sincronizar_ou_adicionar_chave(
            chave=CHAVE_CONFIGURADA,
            rotulo="Chave Principal Gemini (.env)"
        )
    except Exception as _e_sync:
        print(f"[AVISO] Falha ao sincronizar chave de IA inicial com o pool: {_e_sync}")
SERVICO_IA = ServicoIA(gerenciador_pool=GERENCIADOR_POOL_IA, aplicador_glossario=APLICADOR_GLOSSARIO_IA)
GERADOR_DISTRIBUICAO = GeradorDistribuicao(GERENCIADOR_BANCO)

# Inicializar glossário padrão caso esteja vazio
SERVICO_GLOSSARIO.inicializar_glossario_padrao()

# Carregar cache histórico na Memória Global se ainda vazia
try:
    if MEMORIA_GLOBAL.obter_estatisticas()["total_pares"] == 0:
        caminho_cache = os.path.join(DIRETORIO_RAIZ, "dados", "memoria_traducao", "traducoes_cache.json")
        if os.path.exists(caminho_cache):
            MEMORIA_GLOBAL.migrar_cache_historico(caminho_cache, "Wartales Remastered v7.40")
except Exception as erro_tm:
    print(f"[AVISO] Não foi possível migrar cache histórico para a Memória Global: {erro_tm}")

def alternar_projeto_ativo(slug: str) -> Dict[str, Any]:
    global PROJETO_ATIVO, CAMINHO_BANCO, GERENCIADOR_BANCO, SERVICO_GLOSSARIO, SERVICO_PROPAGACAO, SERVICO_SINCRONIZADOR, GERADOR_DISTRIBUICAO
    projeto = GERENCIADOR_PROJETOS.definir_projeto_ativo(slug)
    caminho_banco = GERENCIADOR_PROJETOS.obter_caminho_absoluto(projeto["caminho_banco"])
    CAMINHO_BANCO = caminho_banco
    GERENCIADOR_BANCO = GerenciadorBancoDados(caminho_banco)
    SERVICO_GLOSSARIO = ServicoGlossario(GERENCIADOR_BANCO)
    SERVICO_PROPAGACAO = ServicoAutoPropagacao(GERENCIADOR_BANCO)
    SERVICO_SINCRONIZADOR = SincronizadorXml(GERENCIADOR_BANCO)
    GERADOR_DISTRIBUICAO = GeradorDistribuicao(GERENCIADOR_BANCO)
    PROJETO_ATIVO = projeto
    return projeto


class ManipuladorRequisicaoCat(SimpleHTTPRequestHandler):
    """Tratador de requisições HTTP REST e entrega da interface SPA."""

    def __init__(self, *args, **kwargs):
        self.diretorio_interface = os.path.join(DIRETORIO_RAIZ, "interface")
        super().__init__(*args, directory=self.diretorio_interface, **kwargs)

    def _responder_json(self, dados: Any, status: int = 200) -> None:
        try:
            conteudo = json.dumps(dados, ensure_ascii=False, indent=2).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(conteudo)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()
            self.wfile.write(conteudo)
        except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError):
            pass
        except Exception as erro:
            print(f"[ERRO] Falha ao enviar resposta JSON: {erro}")

    def _ler_payload_json(self) -> Dict[str, Any]:
        comprimento = int(self.headers.get("Content-Length", 0))
        if comprimento == 0:
            return {}
        corpo = self.rfile.read(comprimento).decode("utf-8")
        try:
            return json.loads(corpo)
        except Exception:
            return {}

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        url_analisada = urllib.parse.urlparse(self.path)
        caminho = url_analisada.path
        parametros = urllib.parse.parse_qs(url_analisada.query)

        try:
            # Rotas da API REST
            if caminho == "/api/estatisticas":
                stats = GERENCIADOR_BANCO.obter_estatisticas()
                self._responder_json(stats)
                return

            if caminho == "/api/relatorio":
                relatorio = SERVICO_RELATORIO.obter_relatorio_completo(GERENCIADOR_BANCO, PROJETO_ATIVO)
                self._responder_json(relatorio)
                return

            if caminho == "/api/arvore":
                arvore = GERENCIADOR_BANCO.obter_arvore_hierarquica()
                self._responder_json(arvore)
                return

            if caminho == "/api/segmentos":
                termo = parametros.get("q", [""])[0]
                if not termo:
                    termo = parametros.get("termo", [""])[0]
                status = parametros.get("status", [""])[0]
                origem = parametros.get("origem", [""])[0]
                arquivo = parametros.get("arquivo", [""])[0]
                categoria = parametros.get("categoria", [""])[0]
                inconsistencias = parametros.get("inconsistencias", ["0"])[0] == "1"
                sem_ia = parametros.get("sem_ia", ["0"])[0] == "1"
                pagina = int(parametros.get("pagina", ["1"])[0])
                limite = int(parametros.get("limite", ["50"])[0])

                resultado = GERENCIADOR_BANCO.buscar_segmentos(
                    termo_busca=termo,
                    filtro_status=status,
                    filtro_origem=origem,
                    filtro_arquivo=arquivo,
                    filtro_categoria=categoria,
                    apenas_inconsistencias=inconsistencias,
                    apenas_sem_ia=sem_ia,
                    pagina=pagina,
                    itens_por_pagina=limite
                )
                self._responder_json(resultado)
                return

            if caminho == "/api/segmento/primeiro":
                status = parametros.get("status", [""])[0]
                origem = parametros.get("origem", [""])[0]
                arquivo = parametros.get("arquivo", [""])[0]
                categoria = parametros.get("categoria", [""])[0]
                inconsistencias = parametros.get("inconsistencias", ["0"])[0] == "1"
                sem_ia = parametros.get("sem_ia", ["0"])[0] == "1"
                termo = parametros.get("termo", [""])[0]
                if not termo:
                    termo = parametros.get("q", [""])[0]

                seg_id = GERENCIADOR_BANCO.obter_primeiro_segmento_id(
                    filtro_status=status,
                    filtro_origem=origem,
                    filtro_arquivo=arquivo,
                    filtro_categoria=categoria,
                    apenas_inconsistencias=inconsistencias,
                    apenas_sem_ia=sem_ia,
                    termo_busca=termo
                )
                if not seg_id:
                    self._responder_json({"erro": "Nenhum segmento encontrado para os filtros selecionados."}, 404)
                    return

                seg = GERENCIADOR_BANCO.obter_segmento_por_id(seg_id)
                if not seg:
                    self._responder_json({"erro": "Segmento não encontrado"}, 404)
                    return

                rep_info = SERVICO_PROPAGACAO.obter_estatisticas_repeticao(seg["mod_en"], seg_id)
                seg["repeticoes_totais"] = rep_info["total_repeticoes"]
                seg["itens_repetidos"] = rep_info["itens_repetidos"]

                pos_info = GERENCIADOR_BANCO.obter_posicao_no_filtro(
                    id_segmento=seg_id,
                    filtro_status=status,
                    filtro_origem=origem,
                    filtro_arquivo=arquivo,
                    filtro_categoria=categoria,
                    apenas_inconsistencias=inconsistencias,
                    apenas_sem_ia=sem_ia,
                    termo_busca=termo
                )
                seg["posicao_filtrada"] = pos_info["posicao_filtrada"]
                seg["total_filtrados"] = pos_info["total_filtrados"]
                seg["total_geral"] = pos_info["total_geral"]

                termos_glossario = GERENCIADOR_BANCO.listar_glossario()
                qa_res = ServicoGarantiaQualidade.validar_segmento(seg["mod_en"], seg.get("traducao_revisada") or seg.get("traducao_atual") or "", termos_glossario)
                seg["qa"] = qa_res

                self._responder_json(seg)
                return

            if caminho.startswith("/api/navegacao/"):
                id_atual = int(caminho.split("/")[-1])
                direcao = parametros.get("direcao", ["proximo"])[0]
                status = parametros.get("status", [""])[0]
                origem = parametros.get("origem", [""])[0]
                arquivo = parametros.get("arquivo", [""])[0]
                categoria = parametros.get("categoria", [""])[0]
                inconsistencias = parametros.get("inconsistencias", ["0"])[0] == "1"
                sem_ia = parametros.get("sem_ia", ["0"])[0] == "1"
                termo = parametros.get("termo", [""])[0]
                if not termo:
                    termo = parametros.get("q", [""])[0]

                novo_id = GERENCIADOR_BANCO.navegar_segmento(
                    id_atual=id_atual,
                    direcao=direcao,
                    filtro_status=status,
                    filtro_origem=origem,
                    filtro_arquivo=arquivo,
                    filtro_categoria=categoria,
                    apenas_inconsistencias=inconsistencias,
                    apenas_sem_ia=sem_ia,
                    termo_busca=termo
                )

                if novo_id is None:
                    self._responder_json({"erro": "Nenhum segmento encontrado para os filtros selecionados."}, 404)
                    return

                pos_info = GERENCIADOR_BANCO.obter_posicao_no_filtro(
                    id_segmento=novo_id,
                    filtro_status=status,
                    filtro_origem=origem,
                    filtro_arquivo=arquivo,
                    filtro_categoria=categoria,
                    apenas_inconsistencias=inconsistencias,
                    apenas_sem_ia=sem_ia,
                    termo_busca=termo
                )

                self._responder_json({
                    "id_segmento": novo_id,
                    "direcao": direcao,
                    "posicao_filtrada": pos_info["posicao_filtrada"],
                    "total_filtrados": pos_info["total_filtrados"],
                    "total_geral": pos_info["total_geral"],
                    "inicio_alcancado": pos_info["posicao_filtrada"] == 1,
                    "fim_alcancado": pos_info["posicao_filtrada"] == pos_info["total_filtrados"]
                })
                return

            if caminho.startswith("/api/segmento/"):
                segmento_id = int(caminho.split("/")[-1])
                seg = GERENCIADOR_BANCO.obter_segmento_por_id(segmento_id)
                if not seg:
                    self._responder_json({"erro": "Segmento não encontrado"}, 404)
                    return

                # Análise em tempo real de repetições
                rep_info = SERVICO_PROPAGACAO.obter_estatisticas_repeticao(seg["mod_en"], segmento_id)
                seg["repeticoes_totais"] = rep_info["total_repeticoes"]
                seg["itens_repetidos"] = rep_info["itens_repetidos"]

                # Posição no filtro ativo
                status = parametros.get("status", [""])[0]
                origem = parametros.get("origem", [""])[0]
                arquivo = parametros.get("arquivo", [""])[0]
                categoria = parametros.get("categoria", [""])[0]
                inconsistencias = parametros.get("inconsistencias", ["0"])[0] == "1"
                sem_ia = parametros.get("sem_ia", ["0"])[0] == "1"
                termo = parametros.get("termo", [""])[0]
                if not termo:
                    termo = parametros.get("q", [""])[0]

                pos_info = GERENCIADOR_BANCO.obter_posicao_no_filtro(
                    id_segmento=segmento_id,
                    filtro_status=status,
                    filtro_origem=origem,
                    filtro_arquivo=arquivo,
                    filtro_categoria=categoria,
                    apenas_inconsistencias=inconsistencias,
                    apenas_sem_ia=sem_ia,
                    termo_busca=termo
                )
                seg["posicao_filtrada"] = pos_info["posicao_filtrada"]
                seg["total_filtrados"] = pos_info["total_filtrados"]
                seg["total_geral"] = pos_info["total_geral"]

                # Validação em tempo real de tags
                termos_glossario = GERENCIADOR_BANCO.listar_glossario()
                qa_res = ServicoGarantiaQualidade.validar_segmento(seg["mod_en"], seg.get("traducao_revisada") or seg.get("traducao_atual") or "", termos_glossario)
                seg["qa"] = qa_res

                self._responder_json(seg)
                return

            if caminho == "/api/glossario":
                termos = GERENCIADOR_BANCO.listar_glossario()
                self._responder_json(termos)
                return

            # =========================================================================
            # Novas Rotas: Gerenciador de Projetos e Mod-Agnostic
            # =========================================================================
            if caminho == "/api/projetos":
                projetos = GERENCIADOR_PROJETOS.listar_projetos()
                ativo = GERENCIADOR_PROJETOS.obter_projeto_ativo()
                self._responder_json({"projetos": projetos, "projeto_ativo": ativo})
                return

            if caminho == "/api/projetos/vanilla":
                info_vanilla = GERENCIADOR_PROJETOS.verificar_arquivos_vanilla()
                self._responder_json(info_vanilla)
                return

            if caminho == "/api/ferramentas/autodetectar_steam":
                caminho_steam = GERENCIADOR_PROJETOS.autodetectar_caminho_steam()
                self._responder_json({"caminho_steam": caminho_steam or "", "detectado": bool(caminho_steam)})
                return

            if caminho == "/api/ia/status_lote":
                status_ia = MOTOR_IA_LOTE.obter_status()
                self._responder_json(status_ia)
                return

            if caminho == "/api/ia/pool":
                info_pool = GERENCIADOR_POOL_IA.obter_informacoes_completas()
                self._responder_json(info_pool)
                return

            if caminho == "/api/ia/pool/chaves":
                chaves = GERENCIADOR_POOL_IA.listar_chaves(mascarar=True)
                self._responder_json({"sucesso": True, "chaves": chaves})
                return

            if caminho == "/api/ia/pool/configuracao":
                self._responder_json({
                    "sucesso": True,
                    "modo_selecao": GERENCIADOR_POOL_IA.obter_modo_selecao(),
                    "tempo_cooldown_padrao": GERENCIADOR_POOL_IA.obter_tempo_cooldown_padrao()
                })
                return

            if caminho == "/api/ia/obter_chave":
                chave = GERENCIADOR_PROJETOS.config.get("chave_api_gemini", "")
                chaves_pool = GERENCIADOR_POOL_IA.listar_chaves(mascarar=False)
                if not chave and chaves_pool:
                    chave = chaves_pool[0]["chave"]
                self._responder_json({
                    "possui_chave": bool(chave or chaves_pool),
                    "chave_api": chave,
                    "total_chaves_pool": len(chaves_pool)
                })
                return

            if caminho == "/api/memoria_global/estatisticas":
                stats_mg = MEMORIA_GLOBAL.obter_estatisticas()
                self._responder_json(stats_mg)
                return

            # Caso não seja rota da API, entrega arquivo estático da interface
            if caminho == "/" or caminho == "":
                self.path = "/index.html"
            super().do_GET()
        except ValueError:
            self._responder_json({"erro": "Parâmetro ou ID numérico inválido."}, 400)
        except Exception as erro_geral:
            self._responder_json({"erro": f"Erro interno no servidor: {str(erro_geral)}"}, 500)

    def do_POST(self) -> None:
        url_analisada = urllib.parse.urlparse(self.path)
        caminho = url_analisada.path
        payload = self._ler_payload_json()

        if caminho.startswith("/api/segmento/"):
            try:
                segmento_id = int(caminho.split("/")[-1])
                seg = GERENCIADOR_BANCO.obter_segmento_por_id(segmento_id)
                if not seg:
                    self._responder_json({"erro": "Segmento não encontrado"}, 404)
                    return

                traducao_revisada = payload.get("traducao_revisada", "")
                status = payload.get("status", "revisado")

                # Validação de QA
                termos_glossario = GERENCIADOR_BANCO.listar_glossario()
                qa_res = ServicoGarantiaQualidade.validar_segmento(seg["mod_en"], traducao_revisada, termos_glossario)
                tem_inconsistencia = 1 if qa_res["tem_inconsistencia"] else 0
                aviso_qa = "\n".join(qa_res["avisos"])

                GERENCIADOR_BANCO.atualizar_traducao_segmento(
                    segmento_id=segmento_id,
                    traducao_revisada=traducao_revisada,
                    status=status,
                    aviso_qa=aviso_qa,
                    tem_inconsistencia=tem_inconsistencia
                )

                # Alimentar ou remover da Memória Global de acordo com o status
                if status == "revisado":
                    MEMORIA_GLOBAL.salvar_traducao(
                        seg["mod_en"],
                        traducao_revisada,
                        origem_mod=PROJETO_ATIVO.get("nome", ""),
                        autor="humano"
                    )
                elif status == "pendente" and seg.get("status") == "revisado":
                    MEMORIA_GLOBAL.remover_traducao(seg["mod_en"])

                # Se solicitado auto-propagar
                total_propagados = 0
                if payload.get("auto_propagar", False):
                    res_prop = SERVICO_PROPAGACAO.executar_propagacao(
                        hash_conteudo=seg["hash_conteudo"],
                        nova_traducao=traducao_revisada,
                        status=status
                    )
                    total_propagados = res_prop["total_propagados"]
                    # Salvar na Memória Global também as propagações aprovadas
                    if status == "revisado":
                        MEMORIA_GLOBAL.salvar_traducao(
                            seg["mod_en"],
                            traducao_revisada,
                            origem_mod=PROJETO_ATIVO.get("nome", ""),
                            autor="humano"
                        )

                self._responder_json({
                    "sucesso": True,
                    "id": segmento_id,
                    "qa": qa_res,
                    "total_propagados": total_propagados
                })
                return
            except Exception as erro:
                self._responder_json({"erro": str(erro)}, 500)
                return

        # =========================================================================
        # Novas Rotas POST: Gerenciamento de Projetos, PAK e IA
        # =========================================================================
        if caminho == "/api/projetos/criar":
            nome = payload.get("nome", "").strip()
            versao = payload.get("versao", "1.0").strip()
            descricao = payload.get("descricao", "").strip()
            if not nome:
                self._responder_json({"erro": "Nome do mod é obrigatório."}, 400)
                return
            try:
                novo = GERENCIADOR_PROJETOS.criar_projeto(nome, versao, descricao)
                alternar_projeto_ativo(novo["slug"])
                self._responder_json({"sucesso": True, "projeto": novo})
            except Exception as e:
                self._responder_json({"erro": str(e)}, 400)
            return

        if caminho == "/api/projetos/ativar":
            slug = payload.get("slug", "").strip()
            try:
                proj = alternar_projeto_ativo(slug)
                self._responder_json({"sucesso": True, "projeto": proj})
            except Exception as e:
                self._responder_json({"erro": str(e)}, 400)
            return

        if caminho == "/api/projetos/sincronizar_banco":
            dir_v = GERENCIADOR_PROJETOS.obter_caminho_absoluto(GERENCIADOR_PROJETOS.config.get("diretorio_referencia_vanilla", "dados/referencia_vanilla"))
            dir_m = GERENCIADOR_PROJETOS.obter_caminho_absoluto(PROJETO_ATIVO["diretorio_mod_en"])
            limpar = payload.get("limpar_antes", True)
            try:
                res = SERVICO_SINCRONIZADOR.importar_projeto_completo(dir_v, dir_m, limpar_antes=limpar)
                self._responder_json({"sucesso": True, "resultado": res})
            except Exception as erro:
                self._responder_json({"erro": str(erro)}, 500)
            return

        if caminho == "/api/ferramentas/extrair_pak":
            caminho_pak = payload.get("caminho_pak", "").strip()
            destino = payload.get("destino", "").strip()
            if not caminho_pak or not os.path.exists(caminho_pak):
                self._responder_json({"erro": f"Arquivo .PAK não encontrado: {caminho_pak}"}, 400)
                return
            if not destino:
                destino = GERENCIADOR_PROJETOS.obter_caminho_absoluto(GERENCIADOR_PROJETOS.config.get("diretorio_referencia_vanilla", "dados/referencia_vanilla"))
            else:
                destino = GERENCIADOR_PROJETOS.obter_caminho_absoluto(destino)
            try:
                resultado = EmpacotadorPakHeaps.extrair_arquivos_linguagem(caminho_pak, destino)
                self._responder_json({"sucesso": True, "resultado": resultado})
            except Exception as erro:
                self._responder_json({"erro": str(erro)}, 500)
            return

        if caminho == "/api/ferramentas/salvar_caminho_steam":
            caminho_steam = payload.get("caminho_steam", "").strip()
            GERENCIADOR_PROJETOS.atualizar_caminho_steam(caminho_steam)
            self._responder_json({"sucesso": True, "caminho_steam": caminho_steam})
            return

        if caminho == "/api/ia/salvar_chave":
            nova_chave = payload.get("chave_api", "").strip()
            GERENCIADOR_PROJETOS.atualizar_chave_gemini(nova_chave)
            if nova_chave:
                try:
                    GERENCIADOR_POOL_IA.sincronizar_ou_adicionar_chave(
                        chave=nova_chave,
                        rotulo="Chave Principal Gemini (.env)"
                    )
                except Exception as _e_sync:
                    print(f"[AVISO] Falha ao sincronizar chave com o pool: {_e_sync}")
            self._responder_json({"sucesso": True})
            return

        if caminho == "/api/ia/pool/chaves":
            chave_str = payload.get("chave", "").strip()
            rotulo = payload.get("rotulo", "").strip()
            provedor = payload.get("provedor", "gemini").strip()
            modelo = payload.get("modelo", "gemini-flash-lite-latest").strip()
            prioridade = int(payload.get("prioridade", 1))
            ativo = bool(payload.get("ativo", True))

            if not chave_str:
                self._responder_json({"erro": "O campo 'chave' é obrigatório."}, 400)
                return
            if not rotulo:
                rotulo = f"Chave {provedor.capitalize()}"

            try:
                nova_chave = GERENCIADOR_POOL_IA.adicionar_chave(
                    chave=chave_str,
                    rotulo=rotulo,
                    provedor=provedor,
                    modelo=modelo,
                    prioridade=prioridade,
                    ativo=ativo
                )
                self._responder_json({
                    "sucesso": True,
                    "mensagem": "Chave adicionada com sucesso ao pool.",
                    "chave": nova_chave.para_dicionario(incluir_chave_completa=False)
                })
            except ValueError as erro_val:
                self._responder_json({"erro": str(erro_val)}, 400)
            except Exception as erro_cad:
                self._responder_json({"erro": f"Falha ao cadastrar chave: {str(erro_cad)}"}, 500)
            return

        if caminho == "/api/ia/pool/chaves/atualizar":
            id_chave = int(payload.get("id", 0))
            if id_chave <= 0:
                self._responder_json({"erro": "ID de chave inválido."}, 400)
                return
            rotulo = payload.get("rotulo")
            modelo = payload.get("modelo")
            prioridade = payload.get("prioridade")
            ativo = payload.get("ativo")
            chave_segredo = payload.get("chave")

            sucesso = GERENCIADOR_POOL_IA.atualizar_chave(
                id_chave=id_chave,
                rotulo=rotulo,
                modelo=modelo,
                prioridade=int(prioridade) if prioridade is not None else None,
                ativo=ativo,
                chave=chave_segredo
            )
            if sucesso:
                chave_atualizada = GERENCIADOR_POOL_IA.obter_chave_por_id(id_chave)
                dado_chave = chave_atualizada.para_dicionario(incluir_chave_completa=False) if chave_atualizada else {}
                self._responder_json({"sucesso": True, "chave": dado_chave})
            else:
                self._responder_json({"erro": "Chave não encontrada ou nenhum campo alterado."}, 404)
            return

        if caminho == "/api/ia/pool/chaves/toggle":
            id_chave = int(payload.get("id", 0))
            if id_chave <= 0:
                self._responder_json({"erro": "ID de chave inválido."}, 400)
                return
            ativo_param = payload.get("ativo")
            sucesso = GERENCIADOR_POOL_IA.alternar_status_chave(id_chave, ativo=ativo_param)
            if sucesso:
                self._responder_json({"sucesso": True, "id": id_chave})
            else:
                self._responder_json({"erro": "Chave não encontrada."}, 404)
            return

        if caminho == "/api/ia/pool/chaves/remover":
            id_chave = int(payload.get("id", 0))
            if id_chave <= 0:
                self._responder_json({"erro": "ID de chave inválido."}, 400)
                return
            sucesso = GERENCIADOR_POOL_IA.remover_chave(id_chave)
            if sucesso:
                self._responder_json({"sucesso": True, "id": id_chave, "mensagem": "Chave removida do pool com sucesso."})
            else:
                self._responder_json({"erro": "Chave não encontrada."}, 404)
            return

        if caminho == "/api/ia/pool/chaves/redefinir_cooldown":
            id_chave = int(payload.get("id", 0))
            if id_chave <= 0:
                self._responder_json({"erro": "ID de chave inválido."}, 400)
                return
            sucesso = GERENCIADOR_POOL_IA.redefinir_cooldown_chave(id_chave)
            if sucesso:
                self._responder_json({"sucesso": True, "id": id_chave, "mensagem": "Cooldown e erros redefinidos com sucesso."})
            else:
                self._responder_json({"erro": "Chave não encontrada."}, 404)
            return

        if caminho == "/api/ia/pool/chaves/revelar":
            id_chave = int(payload.get("id", 0))
            if id_chave <= 0:
                self._responder_json({"erro": "ID de chave inválido."}, 400)
                return
            chave_entidade = GERENCIADOR_POOL_IA.obter_chave_por_id(id_chave)
            if not chave_entidade:
                self._responder_json({"erro": "Chave não encontrada no pool."}, 404)
                return
            self._responder_json({
                "sucesso": True,
                "id": id_chave,
                "chave": chave_entidade.chave,
                "rotulo": chave_entidade.rotulo
            })
            return

        if caminho == "/api/ia/pool/modelos":
            provedor = payload.get("provedor", "gemini").strip()
            chave_avulsa = payload.get("chave", "").strip()
            id_chave = payload.get("id")
            if not chave_avulsa and id_chave is not None:
                entidade = GERENCIADOR_POOL_IA.obter_chave_por_id(int(id_chave))
                if entidade:
                    chave_avulsa = entidade.chave
            try:
                modelos = CATALOGO_MODELOS_IA.listar_modelos(
                    provedor, chave_avulsa, bool(payload.get("forcar_atualizacao", False))
                )
                self._responder_json({"sucesso": True, "modelos": modelos})
            except ValueError as erro_valor:
                self._responder_json({"erro": str(erro_valor)}, 400)
            except Exception as erro_consulta:
                logging.getLogger(__name__).warning("Falha ao listar modelos de %s: %s", provedor, erro_consulta)
                self._responder_json({"erro": f"Não foi possível consultar os modelos do provedor: {erro_consulta}"}, 502)
            return

        if caminho == "/api/ia/pool/chaves/testar":
            id_chave = payload.get("id")
            chave_avulsa = payload.get("chave", "").strip()
            provedor = payload.get("provedor", "gemini").strip()
            modelo_param = payload.get("modelo")
            modelo = modelo_param.strip() if modelo_param else None

            if id_chave is not None:
                res_teste = GERENCIADOR_POOL_IA.testar_chave(id_chave=int(id_chave), modelo=modelo)
            elif chave_avulsa:
                res_teste = GERENCIADOR_POOL_IA.testar_chave(chave_direta=chave_avulsa, provedor=provedor, modelo=modelo or "gemini-flash-lite-latest")
            else:
                self._responder_json({"erro": "Informe o 'id' da chave ou o campo 'chave' para teste."}, 400)
                return

            self._responder_json(res_teste)
            return

        if caminho == "/api/ia/pool/configuracao":
            modo = payload.get("modo_selecao")
            cooldown = payload.get("tempo_cooldown_padrao")

            if modo:
                try:
                    GERENCIADOR_POOL_IA.definir_modo_selecao(modo)
                except ValueError as e_modo:
                    self._responder_json({"erro": str(e_modo)}, 400)
                    return

            if cooldown is not None:
                try:
                    GERENCIADOR_POOL_IA.definir_tempo_cooldown_padrao(int(cooldown))
                except ValueError as e_cool:
                    self._responder_json({"erro": str(e_cool)}, 400)
                    return

            self._responder_json({
                "sucesso": True,
                "modo_selecao": GERENCIADOR_POOL_IA.obter_modo_selecao(),
                "tempo_cooldown_padrao": GERENCIADOR_POOL_IA.obter_tempo_cooldown_padrao()
            })
            return

        if caminho == "/api/ia/analisar_deltas":
            dir_v = GERENCIADOR_PROJETOS.obter_caminho_absoluto(GERENCIADOR_PROJETOS.config.get("diretorio_referencia_vanilla", "dados/referencia_vanilla"))
            dir_m = GERENCIADOR_PROJETOS.obter_caminho_absoluto(PROJETO_ATIVO["diretorio_mod_en"])
            analise = MOTOR_IA_LOTE.analisar_deltas(dir_v, dir_m)
            self._responder_json(analise)
            return

        if caminho == "/api/ia/iniciar_lote":
            dir_v = GERENCIADOR_PROJETOS.obter_caminho_absoluto(GERENCIADOR_PROJETOS.config.get("diretorio_referencia_vanilla", "dados/referencia_vanilla"))
            dir_m = GERENCIADOR_PROJETOS.obter_caminho_absoluto(PROJETO_ATIVO["diretorio_mod_en"])
            dir_saida = GERENCIADOR_PROJETOS.obter_caminho_absoluto(PROJETO_ATIVO["diretorio_traducao_ia"])
            chave_override = (payload.get("chave_api") or "").strip() or None
            nome = PROJETO_ATIVO.get("nome", "Mod")
            iniciou = MOTOR_IA_LOTE.iniciar_traducao_assincrona(dir_v, dir_m, dir_saida, chave_override, nome)
            self._responder_json({
                "sucesso": iniciou,
                "mensagem": "Tradução iniciada com sucesso em segundo plano." if iniciou else "Já existe uma tradução em andamento."
            })
            return

        if caminho == "/api/propagar":
            hash_conteudo = payload.get("hash_conteudo", "")
            nova_traducao = payload.get("nova_traducao", "")
            if not hash_conteudo:
                self._responder_json({"erro": "Hash de conteúdo obrigatório"}, 400)
                return

            res = SERVICO_PROPAGACAO.executar_propagacao(hash_conteudo, nova_traducao)
            self._responder_json(res)
            return

        if caminho == "/api/glossario":
            termo_en = payload.get("termo_en", "")
            termo_pt_padrao = payload.get("termo_pt_padrao", "")
            sinonimos = payload.get("sinonimos_proibidos", "")
            categoria = payload.get("categoria", "Geral")
            notas = payload.get("notas", "")

            if not termo_en or not termo_pt_padrao:
                self._responder_json({"erro": "Termo EN e PT padrão são obrigatórios"}, 400)
                return

            termo_id = GERENCIADOR_BANCO.salvar_termo_glossario(
                termo_en=termo_en,
                termo_pt_padrao=termo_pt_padrao,
                sinonimos_proibidos=sinonimos,
                categoria=categoria,
                notas=notas
            )
            self._responder_json({"sucesso": True, "id": termo_id})
            return

        if caminho == "/api/glossario/substituir_lote":
            sinonimo = payload.get("sinonimo_proibido", "")
            termo_padrao = payload.get("termo_padrao", "")
            apenas_pendentes = payload.get("apenas_pendentes", False)

            total = SERVICO_GLOSSARIO.substituir_sinonimo_em_lote(sinonimo, termo_padrao, apenas_pendentes)
            self._responder_json({"sucesso": True, "total_substituidos": total})
            return

        if caminho == "/api/glossario/auditar":
            res = SERVICO_GLOSSARIO.auditar_todo_o_banco()
            self._responder_json({"sucesso": True, "auditoria": res})
            return

        if caminho == "/api/traduzir_ia":
            texto_en = payload.get("texto_en", "")
            if not texto_en:
                self._responder_json({"erro": "Texto em inglês é obrigatório"}, 400)
                return

            res_ia = SERVICO_IA.traduzir_texto(texto_en)
            self._responder_json(res_ia)
            return

        if caminho == "/api/sincronizar":
            dir_v = GERENCIADOR_PROJETOS.obter_caminho_absoluto(GERENCIADOR_PROJETOS.config.get("diretorio_referencia_vanilla", "dados/referencia_vanilla"))
            dir_m = GERENCIADOR_PROJETOS.obter_caminho_absoluto(PROJETO_ATIVO.get("diretorio_mod_en", "dados/mod_atual"))
            try:
                res = SERVICO_SINCRONIZADOR.importar_projeto_completo(dir_v, dir_m)
                self._responder_json({"sucesso": True, "resultado": res})
            except Exception as erro:
                self._responder_json({"erro": str(erro)}, 500)
            return

        if caminho == "/api/compilar":
            dir_m = GERENCIADOR_PROJETOS.obter_caminho_absoluto(PROJETO_ATIVO.get("diretorio_mod_en", "dados/mod_atual"))
            dir_comp = GERENCIADOR_PROJETOS.obter_caminho_absoluto(GERENCIADOR_PROJETOS.config.get("diretorio_saida_compilados", "saida/compilados"))
            dir_dist = GERENCIADOR_PROJETOS.obter_caminho_absoluto(GERENCIADOR_PROJETOS.config.get("diretorio_distribuicao_nexus", "saida/distribuicao_nexus"))
            versao = PROJETO_ATIVO.get("versao", "1.0")
            steam = GERENCIADOR_PROJETOS.config.get("caminho_steam_wartales")

            try:
                res = GERADOR_DISTRIBUICAO.gerar_pacote_completo(
                    diretorio_mod=dir_m,
                    diretorio_saida_compilados=dir_comp,
                    diretorio_distribuicao=dir_dist,
                    versao_mod=versao,
                    caminho_steam=steam
                )
                self._responder_json(res)
            except Exception as erro:
                self._responder_json({"erro": str(erro)}, 500)
            return

        if caminho == "/api/relatorio/nexus":
            try:
                dados_relatorio = SERVICO_RELATORIO.obter_relatorio_completo(GERENCIADOR_BANCO, PROJETO_ATIVO)
                resultado_nexus = SERVICO_RELATORIO.gerar_texto_nexus(dados_relatorio, payload)
                self._responder_json({"sucesso": True, "resultado": resultado_nexus})
            except Exception as erro:
                self._responder_json({"erro": str(erro)}, 500)
            return

        if caminho == "/api/relatorio/salvar_nexus":
            try:
                dados_relatorio = SERVICO_RELATORIO.obter_relatorio_completo(GERENCIADOR_BANCO, PROJETO_ATIVO)
                resultado_nexus = SERVICO_RELATORIO.gerar_texto_nexus(dados_relatorio, payload)
                dir_dist = GERENCIADOR_PROJETOS.obter_caminho_absoluto(
                    GERENCIADOR_PROJETOS.config.get("diretorio_distribuicao_nexus", "saida/distribuicao_nexus")
                )
                os.makedirs(dir_dist, exist_ok=True)
                caminho_arquivo = os.path.join(dir_dist, "STATUS_TRADUCAO_NEXUS.txt")
                with open(caminho_arquivo, "w", encoding="utf-8") as f_nexus:
                    f_nexus.write(resultado_nexus["bbcode"])
                self._responder_json({
                    "sucesso": True,
                    "caminho_arquivo": caminho_arquivo,
                    "resultado": resultado_nexus
                })
            except Exception as erro:
                self._responder_json({"erro": str(erro)}, 500)
            return

        self._responder_json({"erro": "Rota POST não encontrada"}, 404)

    def do_DELETE(self) -> None:
        url_analisada = urllib.parse.urlparse(self.path)
        caminho = url_analisada.path

        if caminho.startswith("/api/glossario/"):
            try:
                termo_id = int(caminho.split("/")[-1])
                sucesso = GERENCIADOR_BANCO.remover_termo_glossario(termo_id)
                self._responder_json({"sucesso": sucesso})
                return
            except ValueError:
                self._responder_json({"erro": "ID inválido"}, 400)
                return

        if caminho.startswith("/api/ia/pool/chaves/"):
            try:
                id_chave = int(caminho.split("/")[-1])
                sucesso = GERENCIADOR_POOL_IA.remover_chave(id_chave)
                if sucesso:
                    self._responder_json({"sucesso": True, "id": id_chave})
                else:
                    self._responder_json({"erro": "Chave não encontrada no pool."}, 404)
                return
            except ValueError:
                self._responder_json({"erro": "ID inválido"}, 400)
                return

        self._responder_json({"erro": "Rota DELETE não encontrada"}, 404)


def iniciar_servidor() -> None:
    porta = int(GERENCIADOR_PROJETOS.config.get("porta_servidor", 5000))
    host = str(GERENCIADOR_PROJETOS.config.get("host_servidor", "127.0.0.1"))
    ThreadingHTTPServer.allow_reuse_address = True
    servidor = ThreadingHTTPServer((host, porta), ManipuladorRequisicaoCat)
    print("=" * 65)
    print(f"  WARTALES CAT STUDIO - SERVIDOR INICIADO COM SUCESSO")
    print(f"  URL Local: http://{host}:{porta}/")
    print(f"  Banco de Dados: {CAMINHO_BANCO}")
    print("=" * 65)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor encerrado pelo usuário.")
    finally:
        servidor.server_close()


if __name__ == "__main__":
    iniciar_servidor()

