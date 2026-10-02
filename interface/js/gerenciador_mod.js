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

    // Aba 3: IA
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
    if (tabId === "ia") this.carregarStatusIa();
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
    } catch (e) {
      window.AppCat?.mostrarToast("Erro ao salvar chave: " + e.message, "✕");
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
