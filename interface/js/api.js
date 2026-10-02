/**
 * Cliente REST API para o Wartales CAT Studio v2.0.
 * Suporta estatísticas, árvore hierárquica, navegação contextual, busca FTS5,
 * persistência de segmentos, memória de tradução, IA e termbase.
 */
const ApiCat = {
  baseUrl: "",

  async requisicao(endpoint, opcoes = {}) {
    const cabecalhos = {
      "Content-Type": "application/json",
      ...(opcoes.headers || {})
    };

    const resposta = await fetch(`${this.baseUrl}${endpoint}`, {
      ...opcoes,
      headers: cabecalhos
    });

    if (!resposta.ok) {
      const erro = await resposta.json().catch(() => ({ erro: "Falha na requisição" }));
      throw new Error(erro.erro || `Erro HTTP ${resposta.status}`);
    }

    return await resposta.json();
  },

  async obterEstatisticas() {
    return await this.requisicao("/api/estatisticas");
  },

  async obterArvore() {
    return await this.requisicao("/api/arvore");
  },

  async buscarSegmentos(filtros = {}) {
    const params = new URLSearchParams();
    if (filtros.termo) params.append("q", filtros.termo);
    if (filtros.status) params.append("status", filtros.status);
    if (filtros.origem) params.append("origem", filtros.origem);
    if (filtros.arquivo) params.append("arquivo", filtros.arquivo);
    if (filtros.categoria) params.append("categoria", filtros.categoria);
    if (filtros.inconsistencias) params.append("inconsistencias", "1");
    if (filtros.sem_ia) params.append("sem_ia", "1");
    if (filtros.pagina) params.append("pagina", filtros.pagina);
    if (filtros.limite) params.append("limite", filtros.limite);

    return await this.requisicao(`/api/segmentos?${params.toString()}`);
  },

  async obterPrimeiroSegmento(filtros = {}) {
    const params = new URLSearchParams();
    if (filtros.termo) params.append("termo", filtros.termo);
    if (filtros.status) params.append("status", filtros.status);
    if (filtros.origem) params.append("origem", filtros.origem);
    if (filtros.arquivo) params.append("arquivo", filtros.arquivo);
    if (filtros.categoria) params.append("categoria", filtros.categoria);
    if (filtros.inconsistencias) params.append("inconsistencias", "1");
    if (filtros.sem_ia) params.append("sem_ia", "1");
    const qs = params.toString() ? `?${params.toString()}` : "";
    return await this.requisicao(`/api/segmento/primeiro${qs}`);
  },

  async obterSegmento(id, filtros = {}) {
    const params = new URLSearchParams();
    if (filtros.termo) params.append("q", filtros.termo);
    if (filtros.status) params.append("status", filtros.status);
    if (filtros.origem) params.append("origem", filtros.origem);
    if (filtros.arquivo) params.append("arquivo", filtros.arquivo);
    if (filtros.categoria) params.append("categoria", filtros.categoria);
    if (filtros.inconsistencias) params.append("inconsistencias", "1");
    if (filtros.sem_ia) params.append("sem_ia", "1");
    const qs = params.toString() ? `?${params.toString()}` : "";
    return await this.requisicao(`/api/segmento/${id}${qs}`);
  },

  async navegarSegmento(idAtual, direcao = "proximo", filtros = {}) {
    const params = new URLSearchParams();
    params.append("direcao", direcao);
    if (filtros.termo) params.append("q", filtros.termo);
    if (filtros.status) params.append("status", filtros.status);
    if (filtros.origem) params.append("origem", filtros.origem);
    if (filtros.arquivo) params.append("arquivo", filtros.arquivo);
    if (filtros.categoria) params.append("categoria", filtros.categoria);
    if (filtros.inconsistencias) params.append("inconsistencias", "1");
    if (filtros.sem_ia) params.append("sem_ia", "1");
    return await this.requisicao(`/api/navegacao/${idAtual}?${params.toString()}`);
  },

  async salvarSegmento(id, traducaoRevisada, status = "revisado", autoPropagar = false) {
    return await this.requisicao(`/api/segmento/${id}`, {
      method: "POST",
      body: JSON.stringify({
        traducao_revisada: traducaoRevisada,
        status: status,
        auto_propagar: autoPropagar
      })
    });
  },

  async traduzirIa(textoEn) {
    return await this.requisicao("/api/traduzir_ia", {
      method: "POST",
      body: JSON.stringify({ texto_en: textoEn })
    });
  },

  async propagarTraducao(hashConteudo, novaTraducao) {
    return await this.requisicao("/api/propagar", {
      method: "POST",
      body: JSON.stringify({
        hash_conteudo: hashConteudo,
        nova_traducao: novaTraducao
      })
    });
  },

  async listarGlossario() {
    return await this.requisicao("/api/glossario");
  },

  async salvarTermoGlossario(termo) {
    return await this.requisicao("/api/glossario", {
      method: "POST",
      body: JSON.stringify(termo)
    });
  },

  async removerTermoGlossario(id) {
    return await this.requisicao(`/api/glossario/${id}`, {
      method: "DELETE"
    });
  },

  async substituirSinonimoLote(sinonimo, termoPadrao, apenasPendentes = false) {
    return await this.requisicao("/api/glossario/substituir_lote", {
      method: "POST",
      body: JSON.stringify({
        sinonimo_proibido: sinonimo,
        termo_padrao: termoPadrao,
        apenas_pendentes: apenasPendentes
      })
    });
  },

  async auditarInconsistencias() {
    return await this.requisicao("/api/glossario/auditar", {
      method: "POST"
    });
  },

  async compilarProjeto() {
    return await this.requisicao("/api/compilar", {
      method: "POST"
    });
  },

  // =========================================================================
  // Gerenciador de Projetos e Mod-Agnostic
  // =========================================================================

  async obterProjetos() {
    return await this.requisicao("/api/projetos");
  },

  async obterInfoVanilla() {
    return await this.requisicao("/api/projetos/vanilla");
  },

  async autodetectarSteam() {
    return await this.requisicao("/api/ferramentas/autodetectar_steam");
  },

  async criarProjeto(nome, versao = "1.0", descricao = "") {
    return await this.requisicao("/api/projetos/criar", {
      method: "POST",
      body: JSON.stringify({ nome, versao, descricao })
    });
  },

  async ativarProjeto(slug) {
    return await this.requisicao("/api/projetos/ativar", {
      method: "POST",
      body: JSON.stringify({ slug })
    });
  },

  async sincronizarBancoProjeto(limparAntes = true) {
    return await this.requisicao("/api/projetos/sincronizar_banco", {
      method: "POST",
      body: JSON.stringify({ limpar_antes: limparAntes })
    });
  },

  async extrairPak(caminhoPak, destino = "") {
    return await this.requisicao("/api/ferramentas/extrair_pak", {
      method: "POST",
      body: JSON.stringify({ caminho_pak: caminhoPak, destino: destino })
    });
  },

  async salvarCaminhoSteam(caminhoSteam) {
    return await this.requisicao("/api/ferramentas/salvar_caminho_steam", {
      method: "POST",
      body: JSON.stringify({ caminho_steam: caminhoSteam })
    });
  },

  async obterChaveGemini() {
    return await this.requisicao("/api/ia/obter_chave");
  },

  async salvarChaveGemini(chaveApi) {
    return await this.requisicao("/api/ia/salvar_chave", {
      method: "POST",
      body: JSON.stringify({ chave_api: chaveApi })
    });
  },

  async obterPoolIa() {
    return await this.requisicao("/api/ia/pool");
  },

  async listarChavesPoolIa() {
    return await this.requisicao("/api/ia/pool/chaves");
  },

  async cadastrarChavePoolIa(dadosChave) {
    return await this.requisicao("/api/ia/pool/chaves", {
      method: "POST",
      body: JSON.stringify(dadosChave)
    });
  },

  async atualizarChavePoolIa(dadosChave) {
    return await this.requisicao("/api/ia/pool/chaves/atualizar", {
      method: "POST",
      body: JSON.stringify(dadosChave)
    });
  },

  async alternarStatusChavePoolIa(id, ativo = null) {
    return await this.requisicao("/api/ia/pool/chaves/toggle", {
      method: "POST",
      body: JSON.stringify({ id, ativo })
    });
  },

  async removerChavePoolIa(id) {
    return await this.requisicao("/api/ia/pool/chaves/remover", {
      method: "POST",
      body: JSON.stringify({ id })
    });
  },

  async redefinirCooldownChavePoolIa(id) {
    return await this.requisicao("/api/ia/pool/chaves/redefinir_cooldown", {
      method: "POST",
      body: JSON.stringify({ id })
    });
  },

  async revelarChavePoolIa(id) {
    return await this.requisicao("/api/ia/pool/chaves/revelar", {
      method: "POST",
      body: JSON.stringify({ id })
    });
  },

  async testarChavePoolIa(dados) {
    return await this.requisicao("/api/ia/pool/chaves/testar", {
      method: "POST",
      body: JSON.stringify(dados)
    });
  },

  async obterConfigPoolIa() {
    return await this.requisicao("/api/ia/pool/configuracao");
  },

  async atualizarConfigPoolIa(configuracao) {
    return await this.requisicao("/api/ia/pool/configuracao", {
      method: "POST",
      body: JSON.stringify(configuracao)
    });
  },

  async salvarConfiguracaoPoolIa(configuracao) {
    return await this.atualizarConfigPoolIa(configuracao);
  },

  async analisarDeltasIa() {
    return await this.requisicao("/api/ia/analisar_deltas", {
      method: "POST"
    });
  },

  async iniciarTraducaoLoteIa() {
    return await this.requisicao("/api/ia/iniciar_lote", {
      method: "POST"
    });
  },

  async obterStatusLoteIa() {
    return await this.requisicao("/api/ia/status_lote");
  },

  async obterEstatisticasMemoriaGlobal() {
    return await this.requisicao("/api/memoria_global/estatisticas");
  },

  async obterRelatorio() {
    return await this.requisicao("/api/relatorio");
  },

  async gerarTextoNexus(opcoes = {}) {
    return await this.requisicao("/api/relatorio/nexus", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(opcoes)
    });
  },

  async salvarTextoNexus(opcoes = {}) {
    return await this.requisicao("/api/relatorio/salvar_nexus", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(opcoes)
    });
  }
};
