/**
 * ============================================================================
 * Módulo Gerenciador de Mod & Fontes de Dados (Setup Mod-Agnostic)
 * ============================================================================
 * Controla o Wizard de 4 etapas:
 * 1. Jogo Base Vanilla (Shiro Games) & Extração de res.pak
 * 2. Mod Selecionado & Extração de res1.pak
 * 3. Tradução em Lote por IA com Deep TM
 * 4. Sincronização e Carga no CAT Studio
 * ============================================================================
 */

const ModuloGerenciadorMod = {
  abaAtiva: "vanilla",
  projetoAtivo: null,
  timerPollingIa: null,
  chavesPoolCache: [],
  timerTickerCooldown: null,

  async inicializar() {
    this.registrarEventos();
    await this.carregarEstadoGeral();
  },

  registrarEventos() {
    // Alternância de Abas
    document.querySelectorAll(".tab-botao-setup").forEach(btn => {
      btn.addEventListener("click", (e) => {
        const tab = btn.dataset.tab;
        this.trocarAba(tab);
      });
    });

    // Aba 1: Vanilla
    const btnDetectarSteam = document.getElementById("btn-detectar-steam");
    if (btnDetectarSteam) {
      btnDetectarSteam.addEventListener("click", () => this.detectarSteam());
    }

    const btnExtrairVanilla = document.getElementById("btn-extrair-vanilla");
    if (btnExtrairVanilla) {
      btnExtrairVanilla.addEventListener("click", () => this.extrairVanilla());
    }

    // Aba 2: Mod
    const selectProjetos = document.getElementById("select-projetos-mod");
    if (selectProjetos) {
      selectProjetos.addEventListener("change", (e) => this.trocarProjetoAtivo(e.target.value));
    }

    const formNovoMod = document.getElementById("form-criar-novo-mod");
    if (formNovoMod) {
      formNovoMod.addEventListener("submit", (e) => {
        e.preventDefault();
        this.criarNovoMod(formNovoMod);
      });
    }

    const btnExtrairModPak = document.getElementById("btn-extrair-mod-pak");
    if (btnExtrairModPak) {
      btnExtrairModPak.addEventListener("click", () => this.extrairModPak());
    }

    // Aba 3: IA & Pool
    const btnSalvarChave = document.getElementById("btn-salvar-chave-ia");
    if (btnSalvarChave) {
      btnSalvarChave.addEventListener("click", () => this.salvarChaveGemini());
    }

    const btnAnalisarDeltas = document.getElementById("btn-analisar-deltas-ia");
    if (btnAnalisarDeltas) {
      btnAnalisarDeltas.addEventListener("click", () => this.analisarDeltasIa());
    }

    const btnIniciarIaLote = document.getElementById("btn-iniciar-ia-lote");
    if (btnIniciarIaLote) {
      btnIniciarIaLote.addEventListener("click", () => this.iniciarIaLote());
    }

    // Pool de Chaves de IA
    const btnSalvarConfigPool = document.getElementById("btn-salvar-config-pool");
    if (btnSalvarConfigPool) {
      btnSalvarConfigPool.addEventListener("click", () => this.salvarConfiguracaoPool());
    }

    const btnAtualizarPool = document.getElementById("btn-atualizar-pool-chaves");
    if (btnAtualizarPool) {
      btnAtualizarPool.addEventListener("click", () => this.carregarPoolIa());
    }

    const btnAbrirCadastroChave = document.getElementById("btn-abrir-modal-cadastro-chave");
    if (btnAbrirCadastroChave) {
      btnAbrirCadastroChave.addEventListener("click", () => this.abrirModalChave(null));
    }

    const btnFecharModalChave = document.getElementById("btn-fechar-modal-chave-pool");
    if (btnFecharModalChave) {
      btnFecharModalChave.addEventListener("click", () => this.fecharModalChave());
    }

    const btnCancelarModalChave = document.getElementById("btn-cancelar-modal-chave-pool");
    if (btnCancelarModalChave) {
      btnCancelarModalChave.addEventListener("click", () => this.fecharModalChave());
    }

    const formChavePool = document.getElementById("form-chave-pool");
    if (formChavePool) {
      formChavePool.addEventListener("submit", (e) => {
        e.preventDefault();
        this.salvarChaveModal();
      });
    }

    const btnSalvarChavePool = document.getElementById("btn-salvar-chave-pool");
    if (btnSalvarChavePool) {
      btnSalvarChavePool.addEventListener("click", () => this.salvarChaveModal());
    }

    const btnTestarConexaoModal = document.getElementById("btn-testar-conexao-modal");
    if (btnTestarConexaoModal) {
      btnTestarConexaoModal.addEventListener("click", () => this.testarConexaoModal());
    }

    const btnToggleVerChave = document.getElementById("btn-toggle-ver-chave-pool");
    if (btnToggleVerChave) {
      btnToggleVerChave.addEventListener("click", () => this.alternarVisibilidadeChaveSegredo());
    }

    const selectModoPool = document.getElementById("select-pool-modo-selecao");
    if (selectModoPool) {
      selectModoPool.addEventListener("change", (e) => {
        this.atualizarDicaModoSelecao(e.target.value);
        this.salvarConfiguracaoPool();
      });
    }

    const checkAtivoPool = document.getElementById("check-chave-pool-ativo");
    if (checkAtivoPool) {
      checkAtivoPool.addEventListener("change", (e) => {
        const labelAtivo = document.getElementById("label-chave-pool-ativo-texto");
        if (labelAtivo) labelAtivo.textContent = e.target.checked ? "Chave Ativa" : "Chave Desativada";
      });
    }

    const modalChavePool = document.getElementById("modal-chave-pool");
    if (modalChavePool) {
      modalChavePool.addEventListener("click", (e) => {
        if (e.target === modalChavePool) this.fecharModalChave();
      });
    }

    // Aba 4: Sincronização
    const btnSincronizarBanco = document.getElementById("btn-sincronizar-banco-mod");
    if (btnSincronizarBanco) {
      btnSincronizarBanco.addEventListener("click", () => this.sincronizarBanco());
    }
  },

  trocarAba(tabId) {
    this.abaAtiva = tabId;
    document.querySelectorAll(".tab-botao-setup").forEach(b => {
      b.classList.toggle("ativo", b.dataset.tab === tabId);
    });
    document.querySelectorAll(".painel-tab-setup").forEach(p => {
      p.classList.toggle("oculto", p.id !== `tab-conteudo-${tabId}`);
    });

    if (tabId === "vanilla") this.carregarInfoVanilla();
    if (tabId === "mod") this.carregarProjetos();
    if (tabId === "ia") {
      this.carregarStatusIa();
      this.carregarPoolIa();
    }
    if (tabId === "sincronizacao") this.carregarResumoVias();
  },

  async carregarEstadoGeral() {
    try {
      const infoProjetos = await ApiCat.obterProjetos();
      this.projetoAtivo = infoProjetos.projeto_ativo;
      this.atualizarHeaderModAtivo();
    } catch (e) {
      console.warn("Erro ao carregar estado geral de projetos:", e);
    }
  },

  atualizarHeaderModAtivo() {
    const label = document.getElementById("label-mod-ativo-nome");
    if (label && this.projetoAtivo) {
      label.textContent = `${this.projetoAtivo.nome || "Mod"} (v${this.projetoAtivo.versao || "1.0"})`;
    }
  },

  // --------------------------------------------------------------------------
  // Aba 1: Jogo Base Vanilla
  // --------------------------------------------------------------------------
  async carregarInfoVanilla() {
    try {
      const info = await ApiCat.obterInfoVanilla();
      const statusContainer = document.getElementById("status-arquivos-vanilla");
      if (statusContainer && info.arquivos) {
        statusContainer.innerHTML = Object.entries(info.arquivos).map(([nome, dados]) => `
          <div class="card-status-arquivo ${dados.presente ? 'arquivo-ok' : 'arquivo-ausente'}">
            <span class="icone-status">${dados.presente ? '✓' : '⚠️'}</span>
            <div class="detalhes-status">
              <strong>${nome}</strong>
              <small>${dados.presente ? (dados.tamanho_bytes / 1024).toFixed(1) + ' KB' : 'Não encontrado'}</small>
            </div>
          </div>
        `).join("");
      }

      const inputSteam = document.getElementById("input-caminho-steam");
      if (inputSteam && info.caminho_steam) {
        inputSteam.value = info.caminho_steam;
      }
    } catch (e) {
      console.error("Erro ao carregar info vanilla:", e);
    }
  },

  async detectarSteam() {
    try {
      const res = await ApiCat.autodetectarSteam();
      const inputSteam = document.getElementById("input-caminho-steam");
      if (res.detectado && inputSteam) {
        inputSteam.value = res.caminho_steam;
        window.AppCat?.mostrarToast("Pasta da Steam detectada com sucesso!", "✓");
        await ApiCat.salvarCaminhoSteam(res.caminho_steam);
      } else {
        window.AppCat?.mostrarToast("Não foi possível detectar a pasta automaticamente. Digite o caminho manualmente.", "ℹ️");
      }
    } catch (e) {
      window.AppCat?.mostrarToast("Falha na detecção da Steam: " + e.message, "✕");
    }
  },

  async extrairVanilla() {
    const inputSteam = document.getElementById("input-caminho-steam");
    const caminhoBase = inputSteam?.value?.trim();
    if (!caminhoBase) {
      window.AppCat?.mostrarToast("Informe o caminho da pasta de Wartales ou do arquivo res.pak!", "⚠️");
      return;
    }

    let caminhoPak = caminhoBase;
    if (!caminhoPak.toLowerCase().endsWith(".pak")) {
      caminhoPak = caminhoPak.replace(/[\\/]+$/, "") + "/res.pak";
    }

    const btn = document.getElementById("btn-extrair-vanilla");
    if (btn) btn.disabled = true;
    window.AppCat?.mostrarToast("Extraindo arquivos XML do jogo base...", "⏳");

    try {
      const res = await ApiCat.extrairPak(caminhoPak, "dados/referencia_vanilla");
      if (res.sucesso) {
        window.AppCat?.mostrarToast(`Extração concluída! ${res.resultado.total_extraidos} arquivos salvos em dados/referencia_vanilla.`, "✓");
        await this.carregarInfoVanilla();
      } else {
        window.AppCat?.mostrarToast("Erro na extração: " + (res.erro || "Falha desconhecida"), "✕");
      }
    } catch (e) {
      window.AppCat?.mostrarToast("Erro ao extrair: " + e.message, "✕");
    } finally {
      if (btn) btn.disabled = false;
    }
  },

  // --------------------------------------------------------------------------
  // Aba 2: Mod Selecionado
  // --------------------------------------------------------------------------
  async carregarProjetos() {
    try {
      const dados = await ApiCat.obterProjetos();
      const select = document.getElementById("select-projetos-mod");
      if (select && dados.projetos) {
        select.innerHTML = dados.projetos.map(p => `
          <option value="${p.slug}" ${p.ativo ? 'selected' : ''}>
            ${p.nome} (v${p.versao}) ${p.ativo ? '★ Ativo' : ''}
          </option>
        `).join("");
      }
      this.projetoAtivo = dados.projeto_ativo;
      this.atualizarHeaderModAtivo();
    } catch (e) {
      console.error("Erro ao carregar projetos:", e);
    }
  },

  async trocarProjetoAtivo(slug) {
    if (!slug) return;
    try {
      window.AppCat?.mostrarToast("Alternando projeto de mod...", "⏳");
      const res = await ApiCat.ativarProjeto(slug);
      if (res.sucesso) {
        this.projetoAtivo = res.projeto;
        this.atualizarHeaderModAtivo();
        window.AppCat?.mostrarToast(`Mod ativo alterado para: ${res.projeto.nome}`, "✓");
        await this.carregarProjetos();
        // Recarregar dados do estúdio
        if (window.AppCat?.carregarDados) {
          window.AppCat.carregarDados();
        }
      }
    } catch (e) {
      window.AppCat?.mostrarToast("Erro ao trocar projeto: " + e.message, "✕");
    }
  },

  async criarNovoMod(form) {
    const nome = form.nome_mod?.value?.trim();
    const versao = form.versao_mod?.value?.trim() || "1.0";
    const descricao = form.descricao_mod?.value?.trim() || "";

    if (!nome) {
      window.AppCat?.mostrarToast("Informe o nome do Mod!", "⚠️");
      return;
    }

    try {
      const res = await ApiCat.criarProjeto(nome, versao, descricao);
      if (res.sucesso) {
        window.AppCat?.mostrarToast(`Projeto '${res.projeto.nome}' criado com sucesso!`, "✓");
        form.reset();
        await this.carregarProjetos();
      }
    } catch (e) {
      window.AppCat?.mostrarToast("Erro ao criar mod: " + e.message, "✕");
    }
  },

  async extrairModPak() {
    const inputPak = document.getElementById("input-caminho-mod-pak");
    const caminhoPak = inputPak?.value?.trim();
    if (!caminhoPak) {
      window.AppCat?.mostrarToast("Informe o caminho do arquivo .pak do mod (ex: res1.pak)!", "⚠️");
      return;
    }

    if (!this.projetoAtivo) {
      window.AppCat?.mostrarToast("Nenhum projeto de mod ativo selecionado.", "⚠️");
      return;
    }

    const destino = this.projetoAtivo.diretorio_mod_en;
    window.AppCat?.mostrarToast("Extraindo arquivos XML do Mod...", "⏳");

    try {
      const res = await ApiCat.extrairPak(caminhoPak, destino);
      if (res.sucesso) {
        window.AppCat?.mostrarToast(`Extração concluída! ${res.resultado.total_extraidos} arquivos salvos no projeto.`, "✓");
      }
    } catch (e) {
      window.AppCat?.mostrarToast("Falha na extração do mod: " + e.message, "✕");
    }
  },

  // --------------------------------------------------------------------------
  // Aba 3: Tradução em Lote por IA
  // --------------------------------------------------------------------------
  async carregarStatusIa() {
    try {
      const chaveInfo = await ApiCat.obterChaveGemini();
      const inputChave = document.getElementById("input-chave-gemini-modal");
      if (inputChave) {
        inputChave.value = chaveInfo.chave_api || "";
      }

      const tmStats = await ApiCat.obterEstatisticasMemoriaGlobal();
      const spanTm = document.getElementById("span-total-tm-global");
      if (spanTm) {
        spanTm.textContent = `${(tmStats.total_pares || 0).toLocaleString()} pares cadastrados`;
      }
    } catch (e) {
      console.warn("Erro ao carregar status IA:", e);
    }
  },

  async salvarChaveGemini() {
    const inputChave = document.getElementById("input-chave-gemini-modal");
    const chave = inputChave?.value?.trim() || "";

    try {
      await ApiCat.salvarChaveGemini(chave);
      if (chave) {
        window.AppCat?.mostrarToast("Chave da API do Gemini salva com sucesso!", "✓");
      } else {
        window.AppCat?.mostrarToast("Chave da API do Gemini removida com sucesso!", "✓");
      }
      await this.carregarStatusIa();
      await this.carregarPoolIa();
    } catch (e) {
      window.AppCat?.mostrarToast("Erro ao salvar chave: " + e.message, "✕");
    }
  },

  // --------------------------------------------------------------------------
  // Gerenciador do Pool de Chaves de IA & Estratégias
  // --------------------------------------------------------------------------
  async carregarPoolIa() {
    try {
      const dados = await ApiCat.obterPoolIa();
      this.chavesPoolCache = dados.chaves || [];

      // 1. Atualizar cards de estatísticas
      const elTotalChaves = document.getElementById("stat-pool-total-chaves");
      const elChavesAtivas = document.getElementById("stat-pool-chaves-ativas");
      const elChavesCooldown = document.getElementById("stat-pool-chaves-cooldown");
      const elTotalReqs = document.getElementById("stat-pool-total-requisicoes");

      if (elTotalChaves) elTotalChaves.textContent = String(dados.total_chaves || 0);
      if (elChavesAtivas) {
        if (dados.chaves_aptas !== undefined && dados.chaves_aptas !== dados.chaves_ativas) {
          elChavesAtivas.textContent = `${dados.chaves_aptas} aptas (${dados.chaves_ativas} ativas)`;
        } else {
          elChavesAtivas.textContent = String(dados.chaves_ativas || 0);
        }
      }
      if (elChavesCooldown) elChavesCooldown.textContent = String(dados.chaves_em_cooldown || 0);

      const stats = dados.metricas_globais || {};
      const reqs = stats.total_requisicoes || 0;
      const taxa = stats.taxa_sucesso_percentual !== undefined ? stats.taxa_sucesso_percentual : 100;
      if (elTotalReqs) {
        elTotalReqs.textContent = reqs > 0 ? `${reqs} (${taxa}% OK)` : "0";
      }

      // 2. Atualizar controles de estratégia
      const selectModo = document.getElementById("select-pool-modo-selecao");
      const inputCooldown = document.getElementById("input-pool-tempo-cooldown");

      if (selectModo && dados.modo_selecao) {
        selectModo.value = dados.modo_selecao;
        this.atualizarDicaModoSelecao(dados.modo_selecao);
      }
      if (inputCooldown && dados.tempo_cooldown_padrao) {
        inputCooldown.value = dados.tempo_cooldown_padrao;
      }

      // 3. Renderizar tabela de chaves
      this.renderizarTabelaChaves(this.chavesPoolCache);

      // 4. Iniciar ou atualizar ticker de cooldown
      this.iniciarTickerCooldown();
    } catch (e) {
      console.warn("Erro ao carregar dados do pool de IA:", e);
    }
  },

  atualizarDicaModoSelecao(modo) {
    const dica = document.getElementById("dica-modo-selecao");
    if (!dica) return;
    if (modo === "fallback") {
      dica.textContent = "Usa estritamente a chave de menor prioridade (1); avança para a próxima apenas em caso de falha ou HTTP 429.";
    } else {
      dica.textContent = "Distribui requisições uniformemente em rodízio entre todas as chaves aptas do pool.";
    }
  },

  async salvarConfiguracaoPool() {
    const selectModo = document.getElementById("select-pool-modo-selecao");
    const inputCooldown = document.getElementById("input-pool-tempo-cooldown");
    const btnSalvar = document.getElementById("btn-salvar-config-pool");

    const modo = selectModo?.value || "round_robin";
    const cooldown = parseInt(inputCooldown?.value, 10);

    if (isNaN(cooldown) || cooldown < 5) {
      window.AppCat?.mostrarToast("O tempo de cooldown deve ser de no mínimo 5 segundos.", "⚠️");
      return;
    }

    if (btnSalvar) btnSalvar.disabled = true;
    try {
      const res = await ApiCat.atualizarConfigPoolIa({
        modo_selecao: modo,
        tempo_cooldown_padrao: cooldown
      });
      if (res.sucesso) {
        window.AppCat?.mostrarToast("Estratégia e Circuit Breaker atualizados com sucesso!", "✓");
      }
      await this.carregarPoolIa();
    } catch (e) {
      window.AppCat?.mostrarToast("Erro ao salvar estratégia: " + e.message, "✕");
    } finally {
      if (btnSalvar) btnSalvar.disabled = false;
    }
  },

  renderizarTabelaChaves(chaves) {
    const corpoTabela = document.getElementById("corpo-tabela-pool-chaves");
    const containerVazio = document.getElementById("pool-tabela-vazia");

    if (!corpoTabela) return;

    if (!chaves || chaves.length === 0) {
      corpoTabela.innerHTML = "";
      if (containerVazio) containerVazio.classList.remove("oculto");
      return;
    }

    if (containerVazio) containerVazio.classList.add("oculto");

    corpoTabela.innerHTML = chaves.map(c => {
      const eEnv = c.rotulo && c.rotulo.toLowerCase().includes(".env");
      let statusHtml = "";

      if (c.bloqueada_permanentemente) {
        statusHtml = `<span class="badge-status-pool status-bloqueada" title="${c.ultimo_erro || 'Bloqueada por erro HTTP 403'}"><span aria-hidden="true">⛔</span> Bloqueada</span>`;
      } else if (c.esta_em_cooldown) {
        const seg = c.segundos_cooldown_restantes || 0;
        statusHtml = `<span class="badge-status-pool status-cooldown" data-id="${c.id}" data-segundos="${seg}" title="${c.motivo_cooldown || 'Em espera temporária'}"><span aria-hidden="true">⏳</span> Cooldown (${seg}s)</span>`;
      } else if (c.ativo) {
        statusHtml = `<span class="badge-status-pool status-ativa"><span aria-hidden="true">✓</span> Ativa</span>`;
      } else {
        statusHtml = `<span class="badge-status-pool status-inativa"><span aria-hidden="true">⚪</span> Inativa</span>`;
      }

      const chaveMascarada = c.chave_mascarada || (c.chave ? c.chave : "****");

      return `
        <tr data-id="${c.id}">
          <td>
            <div class="nome-chave-celula">
              <span class="rotulo-chave-texto">${c.rotulo}</span>
              ${eEnv ? '<span class="badge-pool-env">.env</span>' : ''}
            </div>
          </td>
          <td>
            <div class="provedor-modelo-celula">
              <span class="provedor-texto">${c.provedor}</span>
              <span class="modelo-texto">${c.modelo}</span>
            </div>
          </td>
          <td>
            <div class="chave-mascarada-linha">
              <code id="codigo-chave-${c.id}" data-mascarada="${chaveMascarada}" data-revelada="">${chaveMascarada}</code>
              <button type="button" class="btn-ver-chave-linha" data-id="${c.id}" title="Visualizar chave de API" aria-label="Visualizar chave de API da credencial ${c.rotulo}">👁️</button>
              <button type="button" class="btn-copiar-chave-linha" data-id="${c.id}" data-chave="${chaveMascarada}" title="Copiar chave de API" aria-label="Copiar identificador da chave ${c.rotulo}">📋</button>
            </div>
          </td>
          <td style="text-align: center;">
            <span class="badge-prioridade-pool" title="Prioridade ${c.prioridade}">${c.prioridade}</span>
          </td>
          <td style="text-align: center;">
            ${statusHtml}
          </td>
          <td>
            <div class="celula-acoes-pool">
              <button type="button" class="btn-icone-pool btn-testar-linha" data-id="${c.id}" title="Testar conexão com esta chave" aria-label="Testar conexão da chave ${c.rotulo}">⚡</button>
              <label class="switch-linha" title="${c.ativo ? 'Desativar chave' : 'Ativar chave'}">
                <input type="checkbox" class="check-toggle-linha" data-id="${c.id}" ${c.ativo ? 'checked' : ''} aria-label="Alternar ativação da chave ${c.rotulo}">
                <span class="switch-slider"></span>
              </label>
              <button type="button" class="btn-icone-pool btn-editar-linha" data-id="${c.id}" title="Editar chave" aria-label="Editar chave ${c.rotulo}">✏️</button>
              ${(c.esta_em_cooldown || c.total_falhas > 0) ? `<button type="button" class="btn-icone-pool btn-resetar-cooldown-linha" data-id="${c.id}" title="Redefinir cooldown e falhas" aria-label="Redefinir cooldown da chave ${c.rotulo}">🔄</button>` : ''}
              <button type="button" class="btn-icone-pool btn-remover-linha btn-perigo" data-id="${c.id}" data-rotulo="${c.rotulo}" title="Remover chave do pool" aria-label="Remover chave ${c.rotulo}">🗑️</button>
            </div>
          </td>
        </tr>
      `;
    }).join("");

    // Vincular eventos nas linhas da tabela
    corpoTabela.querySelectorAll(".btn-ver-chave-linha").forEach(btn => {
      btn.addEventListener("click", () => this.alternarVisualizacaoChaveLinha(btn.dataset.id, btn));
    });

    corpoTabela.querySelectorAll(".btn-testar-linha").forEach(btn => {
      btn.addEventListener("click", () => this.testarChaveLinha(btn.dataset.id, btn));
    });

    corpoTabela.querySelectorAll(".check-toggle-linha").forEach(chk => {
      chk.addEventListener("change", (e) => this.alternarStatusChave(chk.dataset.id, e.target.checked));
    });

    corpoTabela.querySelectorAll(".btn-editar-linha").forEach(btn => {
      btn.addEventListener("click", () => this.abrirModalChave(btn.dataset.id));
    });

    corpoTabela.querySelectorAll(".btn-resetar-cooldown-linha").forEach(btn => {
      btn.addEventListener("click", () => this.redefinirCooldownChave(btn.dataset.id));
    });

    corpoTabela.querySelectorAll(".btn-remover-linha").forEach(btn => {
      btn.addEventListener("click", () => this.removerChave(btn.dataset.id, btn.dataset.rotulo));
    });

    corpoTabela.querySelectorAll(".btn-copiar-chave-linha").forEach(btn => {
      btn.addEventListener("click", () => this.copiarTextoParaAreaTransferencia(btn.dataset.chave));
    });
  },

  async alternarVisualizacaoChaveLinha(id, btn) {
    const elCodigo = document.getElementById(`codigo-chave-${id}`);
    const btnCopiar = document.querySelector(`.btn-copiar-chave-linha[data-id="${id}"]`);
    if (!elCodigo) return;

    if (elCodigo.dataset.revelada && elCodigo.textContent === elCodigo.dataset.revelada) {
      elCodigo.textContent = elCodigo.dataset.mascarada;
      if (btn) {
        btn.textContent = "👁️";
        btn.title = "Visualizar chave de API";
      }
      if (btnCopiar) {
        btnCopiar.dataset.chave = elCodigo.dataset.mascarada;
      }
      return;
    }

    if (elCodigo.dataset.revelada) {
      elCodigo.textContent = elCodigo.dataset.revelada;
      if (btn) {
        btn.textContent = "🙈";
        btn.title = "Ocultar chave de API";
      }
      if (btnCopiar) {
        btnCopiar.dataset.chave = elCodigo.dataset.revelada;
      }
      return;
    }

    if (btn) btn.textContent = "⏳";
    try {
      const res = await ApiCat.revelarChavePoolIa(Number(id));
      if (res.sucesso && res.chave) {
        elCodigo.dataset.revelada = res.chave;
        elCodigo.textContent = res.chave;
        if (btn) {
          btn.textContent = "🙈";
          btn.title = "Ocultar chave de API";
        }
        if (btnCopiar) {
          btnCopiar.dataset.chave = res.chave;
        }
      } else {
        window.AppCat?.mostrarToast("Não foi possível revelar a chave.", "✕");
        if (btn) btn.textContent = "👁️";
      }
    } catch (e) {
      window.AppCat?.mostrarToast("Erro ao obter chave: " + e.message, "✕");
      if (btn) btn.textContent = "👁️";
    }
  },

  iniciarTickerCooldown() {
    clearInterval(this.timerTickerCooldown);
    const badgesCooldown = document.querySelectorAll(".badge-status-pool.status-cooldown");
    if (!badgesCooldown || badgesCooldown.length === 0) return;

    this.timerTickerCooldown = setInterval(() => {
      let aindaTemCooldown = false;
      let precisaRecarregar = false;
      document.querySelectorAll(".badge-status-pool.status-cooldown").forEach(badge => {
        let seg = parseInt(badge.dataset.segundos || "0", 10);
        if (seg > 1) {
          seg -= 1;
          badge.dataset.segundos = String(seg);
          badge.innerHTML = `<span aria-hidden="true">⏳</span> Cooldown (${seg}s)`;
          aindaTemCooldown = true;
        } else {
          precisaRecarregar = true;
        }
      });
      if (precisaRecarregar) {
        clearInterval(this.timerTickerCooldown);
        this.carregarPoolIa();
      } else if (!aindaTemCooldown) {
        clearInterval(this.timerTickerCooldown);
      }
    }, 1000);
  },

  abrirModalChave(idChave = null) {
    this.ultimoElementoFocado = document.activeElement;
    const modal = document.getElementById("modal-chave-pool");
    const titulo = document.getElementById("titulo-modal-chave-pool");
    const inputId = document.getElementById("input-chave-pool-id");
    const inputRotulo = document.getElementById("input-chave-pool-rotulo");
    const selectProvedor = document.getElementById("select-chave-pool-provedor");
    const selectModelo = document.getElementById("select-chave-pool-modelo");
    const inputSegredo = document.getElementById("input-chave-pool-segredo");
    const btnVer = document.getElementById("btn-toggle-ver-chave-pool");
    const inputPrioridade = document.getElementById("input-chave-pool-prioridade");
    const checkAtivo = document.getElementById("check-chave-pool-ativo");
    const labelAtivo = document.getElementById("label-chave-pool-ativo-texto");
    const feedbackCaixa = document.getElementById("caixa-feedback-teste-chave");

    if (!modal) return;

    if (feedbackCaixa) feedbackCaixa.classList.add("oculto");
    if (btnVer) btnVer.textContent = "👁️";

    if (idChave) {
      const chaveExistente = (this.chavesPoolCache || []).find(c => c.id === Number(idChave));
      if (titulo) titulo.textContent = "✏️ Editar Chave de IA";
      if (inputId) inputId.value = idChave;
      if (inputRotulo) inputRotulo.value = chaveExistente?.rotulo || "";
      if (selectProvedor) {
        selectProvedor.value = chaveExistente?.provedor || "gemini";
        selectProvedor.disabled = true;
      }
      if (selectModelo && chaveExistente?.modelo) {
        const opcaoExiste = Array.from(selectModelo.options).some(o => o.value === chaveExistente.modelo);
        if (!opcaoExiste) {
          const novaOpcao = document.createElement("option");
          novaOpcao.value = chaveExistente.modelo;
          novaOpcao.textContent = `${chaveExistente.modelo} (Customizado)`;
          selectModelo.appendChild(novaOpcao);
        }
        selectModelo.value = chaveExistente.modelo;
      }
      if (inputSegredo) {
        inputSegredo.value = "";
        inputSegredo.placeholder = "(Mantendo chave mascarada atual)";
        inputSegredo.type = "password";
      }
      if (inputPrioridade) inputPrioridade.value = chaveExistente?.prioridade || 1;
      if (checkAtivo) {
        checkAtivo.checked = chaveExistente ? Boolean(chaveExistente.ativo) : true;
        if (labelAtivo) labelAtivo.textContent = checkAtivo.checked ? "Chave Ativa" : "Chave Desativada";
      }
    } else {
      if (titulo) titulo.textContent = "🔑 Cadastrar Chave de IA";
      if (inputId) inputId.value = "";
      if (inputRotulo) inputRotulo.value = "";
      if (selectProvedor) {
        selectProvedor.value = "gemini";
        selectProvedor.disabled = false;
      }
      if (selectModelo) {
        Array.from(selectModelo.options).forEach(o => {
          if (o.textContent.includes("(Customizado)")) o.remove();
        });
        selectModelo.value = "gemini-flash-lite-latest";
      }
      if (inputSegredo) {
        inputSegredo.value = "";
        inputSegredo.placeholder = "Cole sua chave de API (ex: AIzaSy...)";
        inputSegredo.type = "password";
      }
      if (inputPrioridade) inputPrioridade.value = 1;
      if (checkAtivo) {
        checkAtivo.checked = true;
        if (labelAtivo) labelAtivo.textContent = "Chave Ativa";
      }
    }

    modal.classList.remove("oculto");
    modal.setAttribute("aria-hidden", "false");
    document.body.classList.add("modal-aberto");
    if (inputRotulo) inputRotulo.focus();
  },

  fecharModalChave() {
    const modal = document.getElementById("modal-chave-pool");
    if (modal) {
      modal.classList.add("oculto");
      modal.setAttribute("aria-hidden", "true");
    }
    const algumModalAberto = document.querySelector(".modal-overlay:not(.oculto)");
    if (!algumModalAberto) {
      document.body.classList.remove("modal-aberto");
    }
    if (this.ultimoElementoFocado && typeof this.ultimoElementoFocado.focus === "function") {
      try {
        this.ultimoElementoFocado.focus();
      } catch (_e) {}
    }
  },

  async alternarVisibilidadeChaveSegredo() {
    const inputSegredo = document.getElementById("input-chave-pool-segredo");
    const inputId = document.getElementById("input-chave-pool-id");
    const btnVer = document.getElementById("btn-toggle-ver-chave-pool");
    if (!inputSegredo) return;

    if (inputSegredo.type === "password") {
      if (inputId?.value && !inputSegredo.value.trim()) {
        try {
          if (btnVer) btnVer.textContent = "⏳";
          const res = await ApiCat.revelarChavePoolIa(Number(inputId.value));
          if (res.sucesso && res.chave) {
            inputSegredo.value = res.chave;
          }
        } catch (_e) {}
      }
      inputSegredo.type = "text";
      if (btnVer) btnVer.textContent = "🙈";
    } else {
      inputSegredo.type = "password";
      if (btnVer) btnVer.textContent = "👁️";
    }
  },

  async testarConexaoModal() {
    const inputId = document.getElementById("input-chave-pool-id");
    const inputSegredo = document.getElementById("input-chave-pool-segredo");
    const selectProvedor = document.getElementById("select-chave-pool-provedor");
    const selectModelo = document.getElementById("select-chave-pool-modelo");

    const feedbackCaixa = document.getElementById("caixa-feedback-teste-chave");
    const iconeFeedback = document.getElementById("icone-feedback-teste-chave");
    const tituloFeedback = document.getElementById("titulo-feedback-teste-chave");
    const mensagemFeedback = document.getElementById("mensagem-feedback-teste-chave");
    const tempoFeedback = document.getElementById("tempo-feedback-teste-chave");
    const btnTestar = document.getElementById("btn-testar-conexao-modal");

    const id = inputId?.value ? Number(inputId.value) : null;
    const chave = inputSegredo?.value?.trim() || "";
    const provedor = selectProvedor?.value || "gemini";
    const modelo = selectModelo?.value || "gemini-flash-lite-latest";

    if (!id && !chave) {
      window.AppCat?.mostrarToast("Insira uma chave de API para realizar o teste de conexão.", "⚠️");
      return;
    }

    if (feedbackCaixa) {
      feedbackCaixa.className = "feedback-teste-chave teste-carregando";
      feedbackCaixa.classList.remove("oculto");
    }
    if (iconeFeedback) iconeFeedback.textContent = "⏳";
    if (tituloFeedback) tituloFeedback.textContent = "Testando conexão...";
    if (mensagemFeedback) mensagemFeedback.textContent = "Enviando requisição de validação para a API...";
    if (tempoFeedback) tempoFeedback.textContent = "";
    if (btnTestar) btnTestar.disabled = true;

    const payload = id && !chave ? { id, modelo } : { chave, provedor, modelo };
    const inicio = performance.now();

    try {
      const res = await ApiCat.testarChavePoolIa(payload);
      const latenciaMs = Math.round(performance.now() - inicio);

      if (res.sucesso) {
        if (feedbackCaixa) feedbackCaixa.className = "feedback-teste-chave teste-sucesso";
        if (iconeFeedback) iconeFeedback.textContent = "✓";
        if (tituloFeedback) tituloFeedback.textContent = "Conexão Estabelecida com Sucesso!";
        if (mensagemFeedback) mensagemFeedback.textContent = res.mensagem || "O modelo respondeu com êxito.";
        if (tempoFeedback) tempoFeedback.textContent = `Latência: ${latenciaMs}ms`;
        window.AppCat?.mostrarToast(`✓ Conexão validada em ${latenciaMs}ms!`, "✓");
      } else {
        if (feedbackCaixa) feedbackCaixa.className = "feedback-teste-chave teste-erro";
        if (iconeFeedback) iconeFeedback.textContent = "✕";
        if (tituloFeedback) tituloFeedback.textContent = "Falha na Validação da Conexão";
        if (mensagemFeedback) mensagemFeedback.textContent = res.erro || "Não foi possível validar a chave.";
        if (tempoFeedback) tempoFeedback.textContent = `Tempo: ${latenciaMs}ms`;
        window.AppCat?.mostrarToast(`✕ Falha no teste: ${res.erro || "Erro de validação"}`, "✕");
      }
    } catch (e) {
      const latenciaMs = Math.round(performance.now() - inicio);
      if (feedbackCaixa) feedbackCaixa.className = "feedback-teste-chave teste-erro";
      if (iconeFeedback) iconeFeedback.textContent = "✕";
      if (tituloFeedback) tituloFeedback.textContent = "Erro na Comunicação";
      if (mensagemFeedback) mensagemFeedback.textContent = e.message;
      if (tempoFeedback) tempoFeedback.textContent = `Tempo: ${latenciaMs}ms`;
      window.AppCat?.mostrarToast("Erro ao testar chave: " + e.message, "✕");
    } finally {
      if (btnTestar) btnTestar.disabled = false;
    }
  },

  async salvarChaveModal() {
    const inputId = document.getElementById("input-chave-pool-id");
    const inputRotulo = document.getElementById("input-chave-pool-rotulo");
    const selectProvedor = document.getElementById("select-chave-pool-provedor");
    const selectModelo = document.getElementById("select-chave-pool-modelo");
    const inputSegredo = document.getElementById("input-chave-pool-segredo");
    const inputPrioridade = document.getElementById("input-chave-pool-prioridade");
    const checkAtivo = document.getElementById("check-chave-pool-ativo");
    const btnSalvar = document.getElementById("btn-salvar-chave-pool");

    const id = inputId?.value ? Number(inputId.value) : null;
    const rotulo = inputRotulo?.value?.trim() || "";
    const provedor = selectProvedor?.value || "gemini";
    const modelo = selectModelo?.value || "gemini-flash-lite-latest";
    const chave = inputSegredo?.value?.trim() || "";
    const prioridade = parseInt(inputPrioridade?.value, 10) || 1;
    const ativo = checkAtivo ? checkAtivo.checked : true;

    if (!rotulo) {
      window.AppCat?.mostrarToast("Informe o rótulo identificador da chave.", "⚠️");
      if (inputRotulo) inputRotulo.focus();
      return;
    }

    if (!id && !chave) {
      window.AppCat?.mostrarToast("A chave de API é obrigatória para cadastro.", "⚠️");
      if (inputSegredo) inputSegredo.focus();
      return;
    }

    if (prioridade < 1 || prioridade > 10) {
      window.AppCat?.mostrarToast("A prioridade deve ser um valor entre 1 e 10.", "⚠️");
      if (inputPrioridade) inputPrioridade.focus();
      return;
    }

    if (btnSalvar) btnSalvar.disabled = true;

    try {
      if (id) {
        const dadosAtualizacao = {
          id: id,
          rotulo: rotulo,
          modelo: modelo,
          prioridade: prioridade,
          ativo: ativo
        };
        if (chave) dadosAtualizacao.chave = chave;
        const res = await ApiCat.atualizarChavePoolIa(dadosAtualizacao);
        if (res.sucesso) {
          window.AppCat?.mostrarToast(`Chave "${rotulo}" atualizada com sucesso!`, "✓");
        }
      } else {
        const dadosCadastro = {
          chave: chave,
          rotulo: rotulo,
          provedor: provedor,
          modelo: modelo,
          prioridade: prioridade,
          ativo: ativo
        };
        const res = await ApiCat.cadastrarChavePoolIa(dadosCadastro);
        if (res.sucesso) {
          window.AppCat?.mostrarToast(`Chave "${rotulo}" adicionada ao pool com sucesso!`, "✓");
        }
      }

      this.fecharModalChave();
      await this.carregarPoolIa();
    } catch (e) {
      window.AppCat?.mostrarToast("Erro ao salvar chave: " + e.message, "✕");
    } finally {
      if (btnSalvar) btnSalvar.disabled = false;
    }
  },

  async testarChaveLinha(id, btn) {
    if (!id) return;
    if (btn) {
      btn.disabled = true;
      btn.textContent = "⏳";
    }
    window.AppCat?.mostrarToast("Testando conexão da chave com o provedor...", "⏳");
    const inicio = performance.now();

    try {
      const res = await ApiCat.testarChavePoolIa({ id: Number(id) });
      const latenciaMs = Math.round(performance.now() - inicio);
      if (res.sucesso) {
        window.AppCat?.mostrarToast(`✓ Conexão bem-sucedida (${latenciaMs}ms)!`, "✓");
      } else {
        window.AppCat?.mostrarToast(`✕ Falha no teste (${latenciaMs}ms): ${res.erro || "Erro de validação"}`, "✕");
      }
      await this.carregarPoolIa();
    } catch (e) {
      const latenciaMs = Math.round(performance.now() - inicio);
      window.AppCat?.mostrarToast(`✕ Erro na requisição (${latenciaMs}ms): ${e.message}`, "✕");
      await this.carregarPoolIa();
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.textContent = "⚡";
      }
    }
  },

  async alternarStatusChave(id, ativo) {
    try {
      const res = await ApiCat.alternarStatusChavePoolIa(Number(id), Boolean(ativo));
      if (res.sucesso) {
        window.AppCat?.mostrarToast(ativo ? "Chave ativada no pool com sucesso!" : "Chave desativada do pool.", "✓");
      }
      await this.carregarPoolIa();
    } catch (e) {
      window.AppCat?.mostrarToast("Erro ao alternar status: " + e.message, "✕");
      await this.carregarPoolIa();
    }
  },

  async removerChave(id, rotulo) {
    if (!confirm(`Deseja realmente remover a chave "${rotulo}" do pool de IA?`)) {
      return;
    }
    try {
      const res = await ApiCat.removerChavePoolIa(Number(id));
      if (res.sucesso) {
        window.AppCat?.mostrarToast(`Chave "${rotulo}" removida com sucesso.`, "✓");
      }
      await this.carregarPoolIa();
    } catch (e) {
      window.AppCat?.mostrarToast("Erro ao remover chave: " + e.message, "✕");
    }
  },

  async redefinirCooldownChave(id) {
    try {
      const res = await ApiCat.redefinirCooldownChavePoolIa(Number(id));
      if (res.sucesso) {
        window.AppCat?.mostrarToast("Cooldown e histórico de erros redefinidos!", "✓");
      }
      await this.carregarPoolIa();
    } catch (e) {
      window.AppCat?.mostrarToast("Erro ao redefinir cooldown: " + e.message, "✕");
    }
  },

  async copiarTextoParaAreaTransferencia(texto) {
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(texto);
      } else {
        const area = document.createElement("textarea");
        area.value = texto;
        area.style.position = "fixed";
        area.style.opacity = "0";
        document.body.appendChild(area);
        area.select();
        document.execCommand("copy");
        document.body.removeChild(area);
      }
      window.AppCat?.mostrarToast("Copiado para a área de transferência!", "✓");
    } catch (e) {
      window.AppCat?.mostrarToast("Falha ao copiar: " + e.message, "✕");
    }
  },

  async analisarDeltasIa() {
    window.AppCat?.mostrarToast("Analisando deltas e comparando com Deep TM...", "⏳");
    try {
      const analise = await ApiCat.analisarDeltasIa();
      const container = document.getElementById("resultado-analise-deltas");
      if (container) {
        container.innerHTML = `
          <div class="grade-estatisticas-deltas">
            <div class="card-delta-stat">
              <span class="delta-num">${(analise.total_segmentos || 0).toLocaleString()}</span>
              <span class="delta-rotulo">Total de Frases no Mod</span>
            </div>
            <div class="card-delta-stat stat-sucesso">
              <span class="delta-num">${(analise.reaproveitamento_oficial || 0).toLocaleString()}</span>
              <span class="delta-rotulo">Reaproveitadas do Vanilla PT (0 tokens)</span>
            </div>
            <div class="card-delta-stat stat-sucesso">
              <span class="delta-num">${(analise.reaproveitamento_tm_global || 0).toLocaleString()}</span>
              <span class="delta-rotulo">Reaproveitadas da TM Global (0 tokens)</span>
            </div>
            <div class="card-delta-stat stat-alerta">
              <span class="delta-num">${(analise.necessita_ia || 0).toLocaleString()}</span>
              <span class="delta-rotulo">Frases Genuínas para Traduzir por IA</span>
            </div>
          </div>
          <div class="delta-resumo-texto">
            Economia imediata de tokens: <strong>${analise.porcentagem_reaproveitamento}%</strong> das frases do mod.
            ${analise.necessita_ia > 0 ? `Tempo estimado para IA: ~${analise.estimativa_tempo_segundos} segundos.` : 'Nenhuma frase precisa de IA, 100% já reaproveitado!'}
          </div>
        `;
        container.classList.remove("oculto");
      }
    } catch (e) {
      window.AppCat?.mostrarToast("Erro ao analisar deltas: " + e.message, "✕");
    }
  },

  async iniciarIaLote() {
    if (!confirm("Deseja iniciar o processamento de tradução em lote por IA em segundo plano?")) return;

    try {
      const res = await ApiCat.iniciarTraducaoLoteIa();
      if (res.sucesso) {
        window.AppCat?.mostrarToast("Tradução em lote iniciada!", "✨");
        this.iniciarMonitoramentoIa();
      } else {
        window.AppCat?.mostrarToast(res.mensagem || "Não foi possível iniciar.", "⚠️");
      }
    } catch (e) {
      window.AppCat?.mostrarToast("Falha ao iniciar IA: " + e.message, "✕");
    }
  },

  iniciarMonitoramentoIa() {
    clearInterval(this.timerPollingIa);
    const barra = document.getElementById("barra-progresso-ia-lote");
    const label = document.getElementById("label-progresso-ia-lote");
    const containerProg = document.getElementById("container-progresso-ia-lote");
    if (containerProg) containerProg.classList.remove("oculto");

    this.timerPollingIa = setInterval(async () => {
      try {
        const status = await ApiCat.obterStatusLoteIa();
        if (barra) barra.style.width = `${status.porcentagem}%`;
        if (label) label.textContent = `${status.porcentagem}% - ${status.mensagem}`;

        if (!status.ativo) {
          clearInterval(this.timerPollingIa);
          if (status.concluido) {
            window.AppCat?.mostrarToast("Tradução em lote por IA concluída com sucesso!", "✓");
          } else if (status.erro) {
            window.AppCat?.mostrarToast("Erro na IA: " + status.erro, "✕");
          }
        }
      } catch (e) {
        console.warn("Erro ao consultar progresso IA:", e);
      }
    }, 1500);
  },

  // --------------------------------------------------------------------------
  // Aba 4: Sincronização & Ativação no CAT Studio
  // --------------------------------------------------------------------------
  carregarResumoVias() {
    if (!this.projetoAtivo) return;
    const elModEn = document.getElementById("resumo-caminho-mod-en");
    const elIaPt = document.getElementById("resumo-caminho-ia-pt");
    const elBanco = document.getElementById("resumo-caminho-banco");

    if (elModEn) elModEn.textContent = this.projetoAtivo.diretorio_mod_en;
    if (elIaPt) elIaPt.textContent = this.projetoAtivo.diretorio_traducao_ia;
    if (elBanco) elBanco.textContent = this.projetoAtivo.caminho_banco;
  },

  async sincronizarBanco() {
    if (!confirm("Deseja sincronizar os arquivos XML do mod com o banco de dados SQLite?")) return;

    const btn = document.getElementById("btn-sincronizar-banco-mod");
    if (btn) btn.disabled = true;
    window.AppCat?.mostrarToast("Sincronizando segmentos XML com o banco de dados...", "⏳");

    try {
      const res = await ApiCat.sincronizarBancoProjeto(true);
      if (res.sucesso) {
        window.AppCat?.mostrarToast(`Sincronização concluída! ${res.resultado.total_importados} frases prontas no CAT Studio.`, "✓");
        // Fechar modal
        const modal = document.getElementById("modal-gerenciador-mod");
        if (modal && window.AppCat?.fecharModal) {
          window.AppCat.fecharModal(modal);
        }
        // Recarregar dados da interface
        if (window.AppCat?.carregarDados) {
          await window.AppCat.carregarDados();
        }
      }
    } catch (e) {
      window.AppCat?.mostrarToast("Erro ao sincronizar banco: " + e.message, "✕");
    } finally {
      if (btn) btn.disabled = false;
    }
  }
};

// Exportar globalmente
window.ModuloGerenciadorMod = ModuloGerenciadorMod;

document.addEventListener("DOMContentLoaded", () => {
  ModuloGerenciadorMod.inicializar();
});
