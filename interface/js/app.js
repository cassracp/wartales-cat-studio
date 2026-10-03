/**
 * ==============================================================================
 *  Aplicação Frontend Reativa - Wartales CAT Studio v2.0
 * ==============================================================================
 *  Arquitetura limpa, focada em UX minimalista e total acessibilidade por teclado.
 *  Conformidade estrita com WCAG 2.1 AA.
 *  Nomenclatura 100% em Português do Brasil (pt-BR).
 * ==============================================================================
 */

(function () {
  "use strict";

  // ----------------------------------------------------------------------------
  // Estado Global Unificado da Aplicação
  // ----------------------------------------------------------------------------
  const estado = {
    idSegmentoAtual: 0,
    totalSegmentos: 0,
    posicaoFiltrada: 1,
    totalFiltrados: 0,
    modoAtual: "foco", // 'foco' ou 'overview'
    segmentoAtual: null,
    textoOriginalCarregado: "",
    exibirDiff: false, // alternador visual entre texto puro e realce de diferenças
    arvore: [],
    pastasAbertas: new Set(["arq::export_pt-BR.xml", "arq::texts_pt-BR.xml"]),
    filtro: {
      termo: "",
      status: "pendentes", // 'pendentes', 'aprovados', 'todos'
      origem: "apenas_mod", // 'apenas_mod', 'novos', 'modificados', 'todos', 'vanilla'
      especial: "todos", // 'todos', 'inconsistencias', 'sem_ia'
      categoria: "",
      arquivo: "",
      pagina: 1,
      limite: 25,
      totalPaginas: 1
    },
    carregando: false,
    timerDebounceBusca: null,
    acaoAposPropagacao: null
  };

  // ----------------------------------------------------------------------------
  // Referências aos Elementos do DOM
  // ----------------------------------------------------------------------------
  const el = {
    // Acessibilidade
    regiaoAnuncios: document.getElementById("regiao-anuncios"),

    // Modos
    btnModoFoco: document.getElementById("btn-modo-foco"),
    btnModoOverview: document.getElementById("btn-modo-overview"),
    secaoModoFoco: document.getElementById("secao-modo-foco"),
    secaoModoOverview: document.getElementById("secao-modo-overview"),

    // Progresso Geral e Relatório
    containerProgressoGeral: document.getElementById("container-progresso-geral"),
    rotuloProgressoTitulo: document.getElementById("rotulo-progresso-titulo"),
    rotuloProgresso: document.getElementById("rotulo-progresso-percentual"),
    barraPreenchimento: document.getElementById("barra-preenchimento"),
    rotuloProgressoSubtexto: document.getElementById("rotulo-progresso-subtexto"),
    btnAbrirRelatorio: document.getElementById("btn-abrir-relatorio"),

    // Barra de Navegação e Filtros do Modo Foco
    btnAnterior: document.getElementById("btn-segmento-anterior"),
    btnProximo: document.getElementById("btn-segmento-proximo"),
    selectFiltroFoco: document.getElementById("select-filtro-foco"),
    btnToggleFiltrosDetalhados: document.getElementById("btn-toggle-filtros-detalhados"),
    painelFiltrosDetalhados: document.getElementById("painel-filtros-detalhados"),
    selectCompostoOrigem: document.getElementById("select-composto-origem"),
    selectCompostoStatus: document.getElementById("select-composto-status"),
    selectCompostoEspecial: document.getElementById("select-composto-especial"),
    btnAplicarFiltrosCompostos: document.getElementById("btn-aplicar-filtros-compostos"),
    btnResetarFiltrosCompostos: document.getElementById("btn-resetar-filtros-compostos"),
    textoPosicaoFiltrada: document.getElementById("texto-posicao-filtrada"),
    textoTotalFiltrados: document.getElementById("texto-total-filtrados"),
    textoPosicao: document.getElementById("texto-posicao-segmento"),
    textoTotal: document.getElementById("texto-total-segmentos"),
    inputSalto: document.getElementById("input-salto-segmento"),
    chipFiltroAtivo: document.getElementById("chip-filtro-ativo"),
    textoChipFiltro: document.getElementById("texto-chip-filtro"),
    btnRemoverFiltroContexto: document.getElementById("btn-remover-filtro-contexto"),

    // Badges de Metadados
    badgeArquivo: document.getElementById("badge-arquivo"),
    badgeChave: document.getElementById("badge-chave"),
    badgeStatus: document.getElementById("badge-status-segmento"),
    badgeRepeticoes: document.getElementById("badge-repeticoes"),

    // Cards das 4 Versões Comparativas
    conteudoVanillaEn: document.getElementById("conteudo-vanilla-en"),
    conteudoVanillaPt: document.getElementById("conteudo-vanilla-pt"),
    conteudoModEn: document.getElementById("conteudo-mod-en"),
    conteudoIaPt: document.getElementById("conteudo-ia-pt"),

    btnCopiarVanillaEnEditor: document.getElementById("btn-copiar-vanilla-en-editor"),
    btnCopiarVanillaEn: document.getElementById("btn-copiar-vanilla-en"),
    btnCopiarVanillaPt: document.getElementById("btn-copiar-vanilla-pt"),
    btnToggleDiff: document.getElementById("btn-toggle-diff"),
    btnCopiarModEn: document.getElementById("btn-copiar-mod-en"),
    btnCopiarIaPt: document.getElementById("btn-copiar-ia-pt"),
    btnGerarIaAgora: document.getElementById("btn-gerar-ia-agora"),

    // Editor Humano em Destaque
    campoTraducaoHumana: document.getElementById("campo-traducao-humana"),
    contadorCaracteres: document.getElementById("contador-caracteres"),
    contadorPalavras: document.getElementById("contador-palavras"),
    painelValidacaoTags: document.getElementById("painel-validacao-tags"),
    listaStatusTags: document.getElementById("lista-status-tags"),

    // Barra de Ferramentas CastleDB
    btnInserirBr: document.getElementById("btn-inserir-br"),
    btnInserirB: document.getElementById("btn-inserir-b"),
    btnInserirGood: document.getElementById("btn-inserir-good"),
    btnInserirBad: document.getElementById("btn-inserir-bad"),
    btnInserirTodasTags: document.getElementById("btn-inserir-todas-tags"),
    btnRestaurarTexto: document.getElementById("btn-restaurar-texto"),
    btnLimparEditor: document.getElementById("btn-limpar-editor"),

    // Ações Rápidas de Cópia e Salvar
    btnAtalhoCopiarOficial: document.getElementById("btn-atalho-copiar-oficial"),
    btnAtalhoCopiarIa: document.getElementById("btn-atalho-copiar-ia"),
    btnAtalhoCopiarMod: document.getElementById("btn-atalho-copiar-mod"),

    btnSalvarPermanecer: document.getElementById("btn-salvar-permanecer"),
    btnAprovarSegmento: document.getElementById("btn-aprovar-segmento"),
    btnDesfazerAprovacao: document.getElementById("btn-desfazer-aprovacao"),
    btnSalvarAvancar: document.getElementById("btn-salvar-avancar"),

    // Tela de Visão Geral / Árvore
    containerArvore: document.getElementById("container-arvore"),
    btnExpandirArvore: document.getElementById("btn-expandir-arvore"),
    btnRecolherArvore: document.getElementById("btn-recolher-arvore"),
    btnLimparFiltroArvore: document.getElementById("btn-limpar-filtro-arvore"),
    inputBuscaGlobal: document.getElementById("input-busca-global"),
    btnLimparBuscaOverview: document.getElementById("btn-limpar-busca-overview"),
    pillsFiltroStatus: document.querySelectorAll(".filtro-pill"),
    pillsOrigem: document.querySelectorAll(".pill-origem"),
    pillsStatus: document.querySelectorAll(".pill-status"),
    pillsEspecial: document.querySelectorAll(".pill-especial"),
    badgeResumoFiltrosOverview: document.getElementById("badge-resumo-filtros-overview"),
    btnLimparFiltrosOverview: document.getElementById("btn-limpar-filtros-overview"),
    tabelaSegmentos: document.getElementById("tabela-segmentos"),
    textoPaginacaoInfo: document.getElementById("texto-paginacao-info"),
    btnPaginaAnterior: document.getElementById("btn-pagina-anterior"),
    btnPaginaProxima: document.getElementById("btn-pagina-proxima"),

    // Modais e Toasts
    btnAbrirAtalhos: document.getElementById("btn-abrir-atalhos"),
    modalAtalhos: document.getElementById("modal-atalhos"),
    btnFecharModalAtalhos: document.getElementById("btn-fechar-modal-atalhos"),
    btnOkModalAtalhos: document.getElementById("btn-ok-modal-atalhos"),

    btnAbrirCompilacao: document.getElementById("btn-abrir-compilacao"),
    modalCompilacao: document.getElementById("modal-compilacao"),
    btnFecharModalCompilacao: document.getElementById("btn-fechar-modal-compilacao"),
    btnFecharModalCompilacaoRodape: document.getElementById("btn-fechar-modal-compilacao-rodape"),
    btnIniciarCompilacaoExec: document.getElementById("btn-iniciar-compilacao-exec"),
    statusCompilacaoLog: document.getElementById("status-compilacao-log"),

    btnAbrirGlossario: document.getElementById("btn-abrir-glossario"),
    modalGlossario: document.getElementById("modal-glossario"),
    btnFecharModalGlossario: document.getElementById("btn-fechar-modal-glossario"),
    btnFecharModalGlossarioRodape: document.getElementById("btn-fechar-modal-glossario-rodape"),
    formNovoTermoGlossario: document.getElementById("form-novo-termo-glossario"),
    btnAuditarSinonimosGeral: document.getElementById("btn-auditar-sinonimos-geral"),

    modalPropagacao: document.getElementById("modal-propagacao"),
    btnFecharModalPropagacao: document.getElementById("btn-fechar-modal-propagacao"),
    spanContagemRepeticoes: document.getElementById("spanContagemRepeticoes"),
    spanNovaTraducaoPropagar: document.getElementById("spanNovaTraducaoPropagar"),
    listaPreviaRepeticoes: document.getElementById("listaPreviaRepeticoes"),
    btnSalvarSomenteEste: document.getElementById("btn-salvar-somente-este"),
    btnConfirmarPropagarTodos: document.getElementById("btn-confirmar-propagar-todos"),

    // Modal Gerenciador de Mod (Setup Mod-Agnostic)
    btnAbrirGerenciadorMod: document.getElementById("btn-abrir-gerenciador-mod"),
    modalGerenciadorMod: document.getElementById("modal-gerenciador-mod"),
    btnFecharModalGerenciador: document.getElementById("btn-fechar-modal-gerenciador"),
    btnFecharModalGerenciadorRodape: document.getElementById("btn-fechar-modal-gerenciador-rodape"),
    modalChavePool: document.getElementById("modal-chave-pool"),

    // Modal Filtros Avançados & Compostos (Modo Foco)
    modalFiltrosAvancados: document.getElementById("modal-filtros-avancados"),
    btnFecharModalFiltros: document.getElementById("btn-fechar-modal-filtros"),
    btnFecharModalFiltrosRodape: document.getElementById("btn-fechar-modal-filtros-rodape"),

    // Modal Relatório Inteligente & Gerador Nexus Mods
    modalRelatorio: document.getElementById("modal-relatorio"),
    btnFecharModalRelatorio: document.getElementById("btn-fechar-modal-relatorio"),
    btnFecharModalRelatorioRodape: document.getElementById("btn-fechar-modal-relatorio-rodape"),
    btnAtualizarRelatorio: document.getElementById("btn-atualizar-relatorio"),
    btnAbaRelatorioMetricas: document.getElementById("btn-aba-relatorio-metricas"),
    btnAbaRelatorioFaltantes: document.getElementById("btn-aba-relatorio-faltantes"),
    btnAbaRelatorioNexus: document.getElementById("btn-aba-relatorio-nexus"),
    painelAbaRelatorioMetricas: document.getElementById("painel-aba-relatorio-metricas"),
    painelAbaRelatorioFaltantes: document.getElementById("painel-aba-relatorio-faltantes"),
    painelAbaRelatorioNexus: document.getElementById("painel-aba-relatorio-nexus"),
    relatorioBannerTotalGeral: document.getElementById("relatorio-banner-total-geral"),
    relatorioBannerTotalMod: document.getElementById("relatorio-banner-total-mod"),
    relatorioBannerPctGeral: document.getElementById("relatorio-banner-pct-geral"),
    relatorioBannerPctMod: document.getElementById("relatorio-banner-pct-mod"),
    relatorioModPctRevisao: document.getElementById("relatorio-mod-pct-revisao"),
    relatorioModBarraRevisao: document.getElementById("relatorio-mod-barra-revisao"),
    relatorioModContagemRevisao: document.getElementById("relatorio-mod-contagem-revisao"),
    relatorioModPendentesTexto: document.getElementById("relatorio-mod-pendentes-texto"),
    relatorioModPctTraducao: document.getElementById("relatorio-mod-pct-traducao"),
    relatorioModBarraTraducao: document.getElementById("relatorio-mod-barra-traducao"),
    relatorioModContagemTraducao: document.getElementById("relatorio-mod-contagem-traducao"),
    relatorioNovosPct: document.getElementById("relatorio-novos-pct"),
    relatorioNovosBarra: document.getElementById("relatorio-novos-barra"),
    relatorioNovosContagem: document.getElementById("relatorio-novos-contagem"),
    relatorioNovosPendentes: document.getElementById("relatorio-novos-pendentes"),
    relatorioNovosTraduzidosPct: document.getElementById("relatorio-novos-traduzidos-pct"),
    relatorioModificadosPct: document.getElementById("relatorio-modificados-pct"),
    relatorioModificadosBarra: document.getElementById("relatorio-modificados-barra"),
    relatorioModificadosContagem: document.getElementById("relatorio-modificados-contagem"),
    relatorioModificadosPendentes: document.getElementById("relatorio-modificados-pendentes"),
    relatorioModificadosTraduzidosPct: document.getElementById("relatorio-modificados-traduzidos-pct"),
    relatorioVanillaOficialPct: document.getElementById("relatorio-vanilla-oficial-pct"),
    relatorioVanillaTotal: document.getElementById("relatorio-vanilla-total"),
    relatorioGeralPct: document.getElementById("relatorio-geral-pct"),
    relatorioGeralBarra: document.getElementById("relatorio-geral-barra"),
    relatorioGeralContagem: document.getElementById("relatorio-geral-contagem"),
    relatorioGeralInconsistencias: document.getElementById("relatorio-geral-inconsistencias"),
    tabelaRelatorioArquivosCorpo: document.getElementById("tabela-relatorio-arquivos-corpo"),
    containerRelatorioTopCategorias: document.getElementById("container-relatorio-top-categorias"),
    selectRelatorioFiltroEscopo: document.getElementById("select-relatorio-filtro-escopo"),
    selectRelatorioFiltroStatus: document.getElementById("select-relatorio-filtro-status"),
    selectRelatorioFiltroArquivo: document.getElementById("select-relatorio-filtro-arquivo"),
    selectRelatorioFiltroCategoria: document.getElementById("select-relatorio-filtro-categoria"),
    inputRelatorioBuscaFaltantes: document.getElementById("input-relatorio-busca-faltantes"),
    btnLimparBuscaRelatorio: document.getElementById("btn-limpar-busca-relatorio"),
    btnRelatorioLimparFiltros: document.getElementById("btn-relatorio-limpar-filtros"),
    btnRelatorioAplicarModoFoco: document.getElementById("btn-relatorio-aplicar-modo-foco"),
    relatorioFaltantesResumoContador: document.getElementById("relatorio-faltantes-resumo-contador"),
    tabelaRelatorioFaltantesCorpo: document.getElementById("tabela-relatorio-faltantes-corpo"),
    btnRelatorioPagAnterior: document.getElementById("btn-relatorio-pag-anterior"),
    btnRelatorioPagProxima: document.getElementById("btn-relatorio-pag-proxima"),
    relatorioFaltantesPaginacaoInfo: document.getElementById("relatorio-faltantes-paginacao-info"),
    selectNexusModelo: document.getElementById("select-nexus-modelo"),
    inputNexusNomeMod: document.getElementById("input-nexus-nome-mod"),
    inputNexusVersaoMod: document.getElementById("input-nexus-versao-mod"),
    inputNexusAutor: document.getElementById("input-nexus-autor"),
    checkNexusBarras: document.getElementById("check-nexus-barras"),
    checkNexusEscopo: document.getElementById("check-nexus-escopo"),
    checkNexusArquivos: document.getElementById("check-nexus-arquivos"),
    checkNexusCastledb: document.getElementById("check-nexus-castledb"),
    checkNexusInstalacao: document.getElementById("check-nexus-instalacao"),
    checkNexusFeedback: document.getElementById("check-nexus-feedback"),
    btnCopiarNexusBbcode: document.getElementById("btn-copiar-nexus-bbcode"),
    btnSalvarNexusArquivo: document.getElementById("btn-salvar-nexus-arquivo"),
    containerNexusPreview: document.getElementById("container-nexus-preview"),
    btnCopiarBbcodeRapido: document.getElementById("btn-copiar-bbcode-rapido"),
    textareaNexusBbcode: document.getElementById("textarea-nexus-bbcode"),

    toast: document.getElementById("toast-notificacao"),
    toastIcone: document.getElementById("toast-icone"),
    toastMensagem: document.getElementById("toast-mensagem")
  };

  // ----------------------------------------------------------------------------
  // Utilidades e Acessibilidade (WCAG 2.1 AA)
  // ----------------------------------------------------------------------------
  function escaparHtml(str) {
    if (!str && str !== 0) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function anunciarLeitorDeTela(texto) {
    if (el.regiaoAnuncios) {
      el.regiaoAnuncios.textContent = texto;
    }
  }

  function mostrarToast(mensagem, icone = "✓", duracao = 3000) {
    el.toastIcone.textContent = icone;
    el.toastMensagem.textContent = mensagem;
    el.toast.classList.remove("oculto");
    anunciarLeitorDeTela(mensagem);

    if (window.toastTimeout) {
      clearTimeout(window.toastTimeout);
    }
    window.toastTimeout = setTimeout(() => {
      el.toast.classList.add("oculto");
    }, duracao);
  }

  // ----------------------------------------------------------------------------
  // Controlador de Modais Acessíveis com Focus Trap (WCAG 2.1 AA)
  // ----------------------------------------------------------------------------
  let ultimoElementoFocado = null;

  function obterElementosFocaveis(container) {
    const seletores = [
      'a[href]',
      'button:not([disabled])',
      'textarea:not([disabled])',
      'input:not([disabled])',
      'select:not([disabled])',
      '[tabindex]:not([tabindex="-1"])'
    ];
    return Array.from(container.querySelectorAll(seletores.join(', ')))
      .filter(elem => elem.offsetWidth > 0 || elem.offsetHeight > 0 || elem === document.activeElement);
  }

  function interceptarFocoModal(e, modal) {
    if (e.key !== "Tab") return;

    const focaveis = obterElementosFocaveis(modal);
    if (focaveis.length === 0) {
      e.preventDefault();
      return;
    }

    const primeiro = focaveis[0];
    const ultimo = focaveis[focaveis.length - 1];

    if (e.shiftKey) {
      if (document.activeElement === primeiro) {
        e.preventDefault();
        ultimo.focus();
      }
    } else {
      if (document.activeElement === ultimo) {
        e.preventDefault();
        primeiro.focus();
      }
    }
  }

  function abrirModal(modal, elementoDisparador) {
    if (!modal) return;
    ultimoElementoFocado = elementoDisparador || document.activeElement;
    if (elementoDisparador && typeof elementoDisparador.setAttribute === "function") {
      elementoDisparador.setAttribute("aria-expanded", "true");
    }

    modal.classList.remove("oculto");
    document.body.classList.add("modal-aberto");
    modal.setAttribute("aria-hidden", "false");

    // Adicionar suporte a Focus Trap
    if (!modal._ouvinteFocusTrap) {
      modal._ouvinteFocusTrap = (e) => interceptarFocoModal(e, modal);
      modal.addEventListener("keydown", modal._ouvinteFocusTrap);
    }

    // Foco imediato no primeiro controle interativo do modal
    const focaveis = obterElementosFocaveis(modal);
    if (focaveis.length > 0) {
      setTimeout(() => focaveis[0].focus(), 50);
    }
  }

  function fecharModal(modal) {
    if (!modal) return;
    modal.classList.add("oculto");
    modal.setAttribute("aria-hidden", "true");

    if (ultimoElementoFocado && typeof ultimoElementoFocado.setAttribute === "function") {
      ultimoElementoFocado.setAttribute("aria-expanded", "false");
    }

    const algumModalAberto = document.querySelector(".modal-overlay:not(.oculto)");
    if (!algumModalAberto) {
      document.body.classList.remove("modal-aberto");
    }

    if (ultimoElementoFocado && typeof ultimoElementoFocado.focus === "function") {
      try {
        ultimoElementoFocado.focus();
      } catch (errFoco) {
        if (estado.modoAtual === "foco" && el.campoTraducaoHumana) {
          el.campoTraducaoHumana.focus();
        }
      }
    } else if (estado.modoAtual === "foco" && el.campoTraducaoHumana) {
      el.campoTraducaoHumana.focus();
    }
  }

  function fecharTodosModais() {
    [el.modalAtalhos, el.modalCompilacao, el.modalGlossario, el.modalPropagacao, el.modalGerenciadorMod, el.modalFiltrosAvancados, el.modalRelatorio, el.modalChavePool].forEach(m => {
      if (m && !m.classList.contains("oculto")) {
        fecharModal(m);
      }
    });
  }

  function escaparHtml(texto) {
    if (!texto) return "";
    return String(texto)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function destacarTagsCastleDB(texto) {
    if (!texto) return '<span style="color: var(--cor-texto-fraco); font-style: italic;">[Vazio]</span>';
    const padraoTags = /(&lt;.*?&gt;|<[^>]+>|\[[a-zA-Z0-9_]+\]|::[a-zA-Z0-9_]+::|\$[a-zA-Z0-9_]+\$|\{[a-zA-Z0-9_]+\})/g;
    let partes = [];
    let ultimoIndice = 0;
    let match;

    while ((match = padraoTags.exec(texto)) !== null) {
      if (match.index > ultimoIndice) {
        partes.push(escaparHtml(texto.substring(ultimoIndice, match.index)));
      }
      partes.push(`<span class="tag-destaque">${escaparHtml(match[0])}</span>`);
      ultimoIndice = padraoTags.lastIndex;
    }
    if (ultimoIndice < texto.length) {
      partes.push(escaparHtml(texto.substring(ultimoIndice)));
    }
    return partes.join("").replace(/\n/g, "<br>");
  }

  // ----------------------------------------------------------------------------
  // Algoritmo de Diff Palavra por Palavra (Vanilla EN vs Mod EN)
  // ----------------------------------------------------------------------------
  function renderizarDiff(textoOrig, textoMod) {
    if (!textoOrig || !textoMod || textoOrig === textoMod) {
      return destacarTagsCastleDB(textoMod || "");
    }
    const tokensOrig = textoOrig.split(/(\s+|[.,!?;:()\[\]])/);
    const tokensMod = textoMod.split(/(\s+|[.,!?;:()\[\]])/);

    let i = 0, j = 0;
    let htmlDiff = [];

    while (i < tokensOrig.length || j < tokensMod.length) {
      if (i < tokensOrig.length && j < tokensMod.length && tokensOrig[i] === tokensMod[j]) {
        htmlDiff.push(destacarTagsCastleDB(tokensMod[j]));
        i++;
        j++;
      } else {
        if (j < tokensMod.length && !tokensOrig.slice(i, i + 5).includes(tokensMod[j])) {
          htmlDiff.push(`<span class="diff-adicionado" title="Adicionado pelo Mod">${escaparHtml(tokensMod[j])}</span>`);
          j++;
        } else if (i < tokensOrig.length && !tokensMod.slice(j, j + 5).includes(tokensOrig[i])) {
          htmlDiff.push(`<span class="diff-removido" title="Removido do Original">${escaparHtml(tokensOrig[i])}</span>`);
          i++;
        } else {
          if (j < tokensMod.length) {
            htmlDiff.push(`<span class="diff-adicionado">${escaparHtml(tokensMod[j])}</span>`);
            j++;
          }
          if (i < tokensOrig.length) {
            htmlDiff.push(`<span class="diff-removido">${escaparHtml(tokensOrig[i])}</span>`);
            i++;
          }
        }
      }
    }
    return htmlDiff.join("");
  }

  // ----------------------------------------------------------------------------
  // Validação em Tempo Real de Tags CastleDB e Integridade
  // ----------------------------------------------------------------------------
  function validarTagsTempoReal() {
    if (!estado.segmentoAtual) return;

    const textoMod = estado.segmentoAtual.mod_en || "";
    const textoTrad = el.campoTraducaoHumana.value || "";

    const padraoTags = /(&lt;.*?&gt;|<[^>]+>|\[[a-zA-Z0-9_]+\]|::[a-zA-Z0-9_]+::|\$[a-zA-Z0-9_]+\$|\{[a-zA-Z0-9_]+\})/g;
    const tagsOrig = (textoMod.match(padraoTags) || []).map(t => t.replace(/&lt;/g, "<").replace(/&gt;/g, ">"));
    const tagsTrad = (textoTrad.match(padraoTags) || []).map(t => t.replace(/&lt;/g, "<").replace(/&gt;/g, ">"));

    const tagsFaltando = [];
    const contagemTrad = {};
    for (const t of tagsTrad) {
      contagemTrad[t] = (contagemTrad[t] || 0) + 1;
    }

    for (const t of tagsOrig) {
      if (!contagemTrad[t] || contagemTrad[t] <= 0) {
        tagsFaltando.push(t);
      } else {
        contagemTrad[t]--;
      }
    }

    // Alerta de quebra de linha inicial CastleDB
    const quebraInicial = /^\s*(?:<br\s*\/?>|&lt;br\s*\/?>)/i.test(textoTrad);

    // Checagem de fechamento balanceado de tags HTML/XML básicas
    const tagsBalancear = ["b", "i", "u", "good", "bad", "skill", "gold"];
    const tagsDesbalanceadas = [];
    for (const tag of tagsBalancear) {
      const regAbertura = new RegExp(`<(?:${tag})\\b[^>]*>`, "gi");
      const regFechamento = new RegExp(`</(?:${tag})>`, "gi");
      const aberturas = (textoTrad.match(regAbertura) || []).length;
      const fechamentos = (textoTrad.match(regFechamento) || []).length;
      if (aberturas !== fechamentos) {
        tagsDesbalanceadas.push({ tag, aberturas, fechamentos });
      }
    }

    el.listaStatusTags.innerHTML = "";

    if (quebraInicial) {
      const badgePerigo = document.createElement("span");
      badgePerigo.className = "tag-badge-alerta";
      badgePerigo.textContent = "⚠️ Alerta CastleDB: tag <br/> no início pode causar crash (assert em cdb.Lang)";
      el.listaStatusTags.appendChild(badgePerigo);
    }

    if (tagsDesbalanceadas.length > 0) {
      tagsDesbalanceadas.forEach(d => {
        const badgeDesb = document.createElement("span");
        badgeDesb.className = "tag-badge-alerta";
        badgeDesb.textContent = `⚠️ Tag <${d.tag}> desbalanceada (${d.aberturas} abr vs ${d.fechamentos} fech)`;
        el.listaStatusTags.appendChild(badgeDesb);
      });
    }

    if (tagsFaltando.length === 0 && !quebraInicial && tagsDesbalanceadas.length === 0) {
      const badgeOk = document.createElement("span");
      badgeOk.className = "tag-badge-ok";
      badgeOk.textContent = tagsOrig.length > 0 ? `✓ Todas as ${tagsOrig.length} tags presentes` : "✓ Nenhuma inconsistência detectada";
      el.listaStatusTags.appendChild(badgeOk);
    } else if (tagsFaltando.length > 0) {
      tagsFaltando.forEach(tag => {
        const badgeFaltando = document.createElement("span");
        badgeFaltando.className = "tag-badge-alerta";
        badgeFaltando.textContent = `+ Inserir tag: ${tag}`;
        badgeFaltando.title = "Clique para inserir no editor";
        badgeFaltando.style.cursor = "pointer";
        badgeFaltando.addEventListener("click", () => inserirTextoNaPosicaoCursor(" " + tag));
        el.listaStatusTags.appendChild(badgeFaltando);
      });
    }
  }

  function atualizarMetricasTexto() {
    const texto = el.campoTraducaoHumana.value || "";
    el.contadorCaracteres.textContent = texto.length;
    const palavras = texto.trim() ? texto.trim().split(/\s+/).length : 0;
    el.contadorPalavras.textContent = palavras;
  }

  // ----------------------------------------------------------------------------
  // Carregamento de Estatísticas Gerais e Específicas do Mod
  // ----------------------------------------------------------------------------
  async function carregarEstatisticas() {
    try {
      const stats = await ApiCat.obterEstatisticas();
      const pctMod = stats.mod_porcentagem_concluida || 0;
      const modTotal = stats.mod_total || 0;
      const modRevisados = stats.mod_revisados || 0;
      const pctGeral = stats.porcentagem_concluida || 0;

      // Destacar o progresso real do Mod na barra do cabeçalho
      el.rotuloProgresso.textContent = `${pctMod}%`;
      el.barraPreenchimento.style.width = `${pctMod}%`;

      if (el.rotuloProgressoTitulo) {
        el.rotuloProgressoTitulo.textContent = "Progresso do Mod";
      }
      if (el.rotuloProgressoSubtexto) {
        el.rotuloProgressoSubtexto.textContent = `${modRevisados.toLocaleString("pt-BR")} / ${modTotal.toLocaleString("pt-BR")} validados (Geral: ${pctGeral}%)`;
      }

      estado.totalSegmentos = stats.total_segmentos || 0;
      if (el.textoTotal) {
        el.textoTotal.textContent = estado.totalSegmentos.toLocaleString("pt-BR");
      }
    } catch (e) {
      console.error("Erro ao carregar estatísticas:", e);
    }
  }

  // ----------------------------------------------------------------------------
  // Auxiliares de Filtros Compostos
  // ----------------------------------------------------------------------------
  function obterFiltrosAtivos() {
    const f = {
      termo: estado.filtro.termo,
      arquivo: estado.filtro.arquivo,
      categoria: estado.filtro.categoria,
      pagina: estado.filtro.pagina,
      limite: estado.filtro.limite
    };
    if (estado.filtro.status && estado.filtro.status !== "todos") {
      f.status = estado.filtro.status;
    }
    if (estado.filtro.origem && estado.filtro.origem !== "todos") {
      f.origem = estado.filtro.origem;
    }
    if (estado.filtro.especial === "inconsistencias") {
      f.inconsistencias = true;
    } else if (estado.filtro.especial === "sem_ia") {
      f.sem_ia = true;
    }
    return f;
  }

  function obterDescricaoFiltroAtivo() {
    const partes = [];
    if (estado.filtro.origem === "apenas_mod") partes.push("⚔️ Apenas Mod");
    else if (estado.filtro.origem === "novos") partes.push("✨ Novos");
    else if (estado.filtro.origem === "modificados") partes.push("✏️ Modificados");
    else if (estado.filtro.origem === "vanilla") partes.push("🏛️ Vanilla");

    if (estado.filtro.status === "pendentes") partes.push("⏳ Pendentes");
    else if (estado.filtro.status === "aprovados") partes.push("✓ Aprovados");

    if (estado.filtro.especial === "inconsistencias") partes.push("⚠️ QA");
    else if (estado.filtro.especial === "sem_ia") partes.push("🤖 Sem IA");

    if (estado.filtro.categoria) partes.push(`Cat: ${estado.filtro.categoria}`);
    if (estado.filtro.arquivo) partes.push(estado.filtro.arquivo);
    if (estado.filtro.termo) partes.push(`"${estado.filtro.termo}"`);

    return partes.length > 0 ? partes.join(" + ") : "Todas as Frases";
  }

  function sincronizarFiltrosUI() {
    // Sincronizar select rápido do Modo Foco
    if (el.selectFiltroFoco) {
      if (estado.filtro.especial === "inconsistencias") {
        el.selectFiltroFoco.value = "inconsistencias";
      } else if (estado.filtro.especial === "sem_ia") {
        el.selectFiltroFoco.value = "sem_ia";
      } else if (estado.filtro.origem === "apenas_mod" && estado.filtro.status === "pendentes") {
        el.selectFiltroFoco.value = "mod_pendentes";
      } else if (estado.filtro.origem === "novos" && estado.filtro.status === "pendentes") {
        el.selectFiltroFoco.value = "mod_novos_pendentes";
      } else if (estado.filtro.origem === "modificados" && estado.filtro.status === "pendentes") {
        el.selectFiltroFoco.value = "mod_modificados_pendentes";
      } else if (estado.filtro.origem === "apenas_mod" && estado.filtro.status === "todos") {
        el.selectFiltroFoco.value = "mod_todos";
      } else if (estado.filtro.origem === "todos" && estado.filtro.status === "pendentes") {
        el.selectFiltroFoco.value = "pendentes";
      } else if (estado.filtro.origem === "todos" && estado.filtro.status === "aprovados") {
        el.selectFiltroFoco.value = "aprovados";
      } else if (estado.filtro.origem === "todos" && estado.filtro.status === "todos") {
        el.selectFiltroFoco.value = "todos";
      }
    }

    // Sincronizar painel detalhado de filtros
    if (el.selectCompostoOrigem) el.selectCompostoOrigem.value = estado.filtro.origem;
    if (el.selectCompostoStatus) el.selectCompostoStatus.value = estado.filtro.status;
    if (el.selectCompostoEspecial) el.selectCompostoEspecial.value = estado.filtro.especial;

    // Sincronizar pills da Visão Geral
    if (el.pillsOrigem) {
      el.pillsOrigem.forEach(p => {
        p.classList.toggle("ativo", p.dataset.origem === estado.filtro.origem);
      });
    }
    if (el.pillsStatus) {
      el.pillsStatus.forEach(p => {
        p.classList.toggle("ativo", p.dataset.status === estado.filtro.status);
      });
    }
    if (el.pillsEspecial) {
      el.pillsEspecial.forEach(p => {
        p.classList.toggle("ativo", p.dataset.especial === estado.filtro.especial);
      });
    }

    // Sincronizar resumo na Visão Geral
    if (el.badgeResumoFiltrosOverview) {
      el.badgeResumoFiltrosOverview.innerHTML = `Filtro Ativo: <strong>${escaparHtml(obterDescricaoFiltroAtivo())}</strong>`;
    }

    atualizarChipFiltroAtivo();
  }

  async function aplicarNovoFiltroFoco(pularParaPrimeiro = true) {
    sincronizarFiltrosUI();
    if (pularParaPrimeiro) {
      try {
        const filtrosConsulta = obterFiltrosAtivos();
        const seg = await ApiCat.obterPrimeiroSegmento(filtrosConsulta);
        if (seg && seg.id) {
          await carregarSegmento(seg.id);
          mostrarToast(`Filtro: ${obterDescricaoFiltroAtivo()}`, "🎯");
        } else {
          mostrarToast("Nenhuma frase encontrada para os filtros selecionados.", "ℹ️");
        }
      } catch (e) {
        mostrarToast(`Filtro: ${e.message}`, "ℹ️");
      }
    } else {
      await carregarSegmento(estado.idSegmentoAtual, true);
    }
  }

  // ----------------------------------------------------------------------------
  // Carregamento de Segmento (Modo Foco)
  // ----------------------------------------------------------------------------
  async function carregarSegmento(id, manterFiltro = true) {
    if (!id || isNaN(id) || id <= 0) return;
    if (estado.carregando) return;
    estado.carregando = true;

    try {
      const filtrosConsulta = obterFiltrosAtivos();
      const seg = await ApiCat.obterSegmento(id, filtrosConsulta);
      if (!seg || !seg.id) {
        throw new Error("Segmento não encontrado");
      }
      estado.segmentoAtual = seg;
      estado.idSegmentoAtual = seg.id;

      // Atualizar Badges e Posição
      el.badgeArquivo.textContent = seg.arquivo || "export_pt-BR.xml";
      el.badgeChave.textContent = seg.chave_hierarquica || `item_${seg.id}`;
      el.textoPosicao.textContent = seg.id;
      el.inputSalto.value = seg.id;

      // Status do Segmento
      const status = seg.status || "pendente";
      const ehAprovado = status === "revisado" || status === "aprovado";
      el.badgeStatus.textContent = ehAprovado ? "Aprovado" : "Pendente";
      el.badgeStatus.className = `badge-status status-${ehAprovado ? "aprovado" : "pendente"}`;

      if (el.btnDesfazerAprovacao) {
        if (ehAprovado) {
          el.btnDesfazerAprovacao.classList.remove("oculto");
          el.btnAprovarSegmento.innerHTML = '<span>✓ Já Aprovado</span><kbd class="tecla-atalho">Alt+A</kbd>';
          el.btnAprovarSegmento.classList.remove("btn-sucesso");
          el.btnAprovarSegmento.classList.add("btn-secundario");
        } else {
          el.btnDesfazerAprovacao.classList.add("oculto");
          el.btnAprovarSegmento.innerHTML = '<span aria-hidden="true">✓</span><span>Aprovar & Próximo</span><kbd class="tecla-atalho">Alt+A</kbd>';
          el.btnAprovarSegmento.classList.add("btn-sucesso");
          el.btnAprovarSegmento.classList.remove("btn-secundario");
        }
      }

      // Posição Filtrada e Total Filtrado
      estado.posicaoFiltrada = seg.posicao_filtrada || 1;
      estado.totalFiltrados = seg.total_filtrados !== undefined ? seg.total_filtrados : estado.totalSegmentos;
      el.textoPosicaoFiltrada.textContent = `#${estado.posicaoFiltrada.toLocaleString("pt-BR")}`;
      el.textoTotalFiltrados.textContent = estado.totalFiltrados.toLocaleString("pt-BR");

      // Badge de Repetições
      if (seg.repeticoes_totais && seg.repeticoes_totais > 1) {
        el.badgeRepeticoes.textContent = `🔁 ${seg.repeticoes_totais} repetições no jogo`;
        el.badgeRepeticoes.classList.remove("oculto");
      } else {
        el.badgeRepeticoes.classList.add("oculto");
      }

      // Chip de Filtro Ativo
      atualizarChipFiltroAtivo();

      // Atualizar Cards das 4 Versões
      el.conteudoVanillaEn.innerHTML = destacarTagsCastleDB(seg.vanilla_en);
      el.conteudoVanillaPt.innerHTML = destacarTagsCastleDB(seg.vanilla_pt);
      renderizarModEn();

      // Versão IA / Tradução Atual
      const textoIa = seg.traducao_atual || "";
      el.conteudoIaPt.innerHTML = destacarTagsCastleDB(textoIa);

      // Campo de Tradução Humana
      const textoHumano = seg.traducao_revisada || seg.traducao_atual || seg.vanilla_pt || "";
      el.campoTraducaoHumana.value = textoHumano;
      estado.textoOriginalCarregado = textoHumano;

      atualizarMetricasTexto();
      validarTagsTempoReal();

      // Foco suave no editor para digitação imediata
      el.campoTraducaoHumana.focus();
      anunciarLeitorDeTela(`Segmento ${estado.posicaoFiltrada} carregado. Chave: ${seg.chave_hierarquica}`);
    } catch (erro) {
      console.error("Erro ao carregar segmento:", erro);
      mostrarToast(`Erro ao carregar segmento: ${erro.message}`, "✕");
    } finally {
      estado.carregando = false;
    }
  }

  function renderizarModEn() {
    if (!estado.segmentoAtual) return;
    if (estado.exibirDiff) {
      el.conteudoModEn.innerHTML = renderizarDiff(estado.segmentoAtual.vanilla_en, estado.segmentoAtual.mod_en);
      el.btnToggleDiff.classList.add("btn-primario");
      el.btnToggleDiff.classList.remove("btn-secundario");
    } else {
      el.conteudoModEn.innerHTML = destacarTagsCastleDB(estado.segmentoAtual.mod_en);
      el.btnToggleDiff.classList.remove("btn-primario");
      el.btnToggleDiff.classList.add("btn-secundario");
    }
  }

  function atualizarChipFiltroAtivo() {
    const filtrosAtivos = [];
    if (estado.filtro.origem === "apenas_mod") {
      filtrosAtivos.push("⚔️ Apenas Mod");
    } else if (estado.filtro.origem === "novos") {
      filtrosAtivos.push("✨ Termos Novos");
    } else if (estado.filtro.origem === "modificados") {
      filtrosAtivos.push("✏️ Frases Modificadas");
    }

    if (estado.filtro.status === "pendentes") {
      filtrosAtivos.push("⏳ Pendentes");
    } else if (estado.filtro.status === "aprovados") {
      filtrosAtivos.push("✓ Aprovados");
    }

    if (estado.filtro.especial === "inconsistencias") {
      filtrosAtivos.push("⚠️ QA");
    } else if (estado.filtro.especial === "sem_ia") {
      filtrosAtivos.push("🤖 Sem IA");
    }

    if (estado.filtro.categoria) filtrosAtivos.push(`Cat: ${estado.filtro.categoria}`);
    if (estado.filtro.arquivo) filtrosAtivos.push(`Arquivo: ${estado.filtro.arquivo}`);
    if (estado.filtro.termo) filtrosAtivos.push(`Busca: "${estado.filtro.termo}"`);

    if (filtrosAtivos.length > 0) {
      el.textoChipFiltro.textContent = filtrosAtivos.join(" | ");
      el.chipFiltroAtivo.classList.remove("oculto");
    } else {
      el.chipFiltroAtivo.classList.add("oculto");
    }
  }

  // ----------------------------------------------------------------------------
  // Navegação entre Frases (Ida e Volta)
  // ----------------------------------------------------------------------------
  async function navegarDirecao(direcao) {
    if (estado.carregando) return;
    try {
      const filtrosConsulta = obterFiltrosAtivos();
      const res = await ApiCat.navegarSegmento(estado.idSegmentoAtual, direcao, filtrosConsulta);
      if (res.id_segmento) {
        await carregarSegmento(res.id_segmento);
        if (res.inicio_alcancado && direcao === "anterior") {
          mostrarToast("Primeira frase do filtro alcançada.", "ℹ️");
        } else if (res.fim_alcancado && direcao === "proximo") {
          mostrarToast("Última frase do filtro alcançada.", "ℹ️");
        }
      }
    } catch (e) {
      mostrarToast(e.message || "Fim da navegação alcançado.", "ℹ️");
    }
  }

  // ----------------------------------------------------------------------------
  // Ações do Editor Humano (Salvar, Avançar, Copiar)
  // ----------------------------------------------------------------------------
  async function salvarSegmentoAtual(avancar = false, aprovar = false) {
    if (!estado.segmentoAtual) return;

    const textoTrad = el.campoTraducaoHumana.value;
    const novoStatus = aprovar ? "revisado" : (estado.segmentoAtual.status || "pendente");

    // Verificar se há repetições e se o usuário deseja auto-propagar
    if (estado.segmentoAtual.repeticoes_totais && estado.segmentoAtual.repeticoes_totais > 1 && !estado.acaoAposPropagacao) {
      abrirModalPropagacao(textoTrad, novoStatus, avancar);
      return;
    }

    try {
      await ApiCat.salvarSegmento(estado.idSegmentoAtual, textoTrad, novoStatus, false);
      estado.textoOriginalCarregado = textoTrad;
      estado.segmentoAtual.status = novoStatus;
      estado.segmentoAtual.traducao_revisada = textoTrad;

      const ehAprovado = novoStatus === "revisado" || novoStatus === "aprovado";
      el.badgeStatus.textContent = ehAprovado ? "Aprovado" : "Pendente";
      el.badgeStatus.className = `badge-status status-${ehAprovado ? "aprovado" : "pendente"}`;

      if (el.btnDesfazerAprovacao) {
        if (ehAprovado) {
          el.btnDesfazerAprovacao.classList.remove("oculto");
          el.btnAprovarSegmento.innerHTML = '<span>✓ Já Aprovado</span><kbd class="tecla-atalho">Alt+A</kbd>';
          el.btnAprovarSegmento.classList.remove("btn-sucesso");
          el.btnAprovarSegmento.classList.add("btn-secundario");
        } else {
          el.btnDesfazerAprovacao.classList.add("oculto");
          el.btnAprovarSegmento.innerHTML = '<span aria-hidden="true">✓</span><span>Aprovar & Próximo</span><kbd class="tecla-atalho">Alt+A</kbd>';
          el.btnAprovarSegmento.classList.add("btn-sucesso");
          el.btnAprovarSegmento.classList.remove("btn-secundario");
        }
      }

      mostrarToast(aprovar ? "Tradução aprovada!" : "Tradução salva!", "💾");
      await carregarEstatisticas();

      if (avancar) {
        await navegarDirecao("proximo");
      }
    } catch (e) {
      console.error("Erro ao salvar:", e);
      mostrarToast(`Erro ao salvar: ${e.message}`, "✕");
    }
  }

  async function desfazerAprovacaoAtual() {
    if (!estado.segmentoAtual) return;

    try {
      const textoAtual = el.campoTraducaoHumana.value;
      await ApiCat.salvarSegmento(estado.idSegmentoAtual, textoAtual, "pendente", false);
      estado.segmentoAtual.status = "pendente";

      el.badgeStatus.textContent = "Pendente";
      el.badgeStatus.className = "badge-status status-pendente";

      if (el.btnDesfazerAprovacao) {
        el.btnDesfazerAprovacao.classList.add("oculto");
        el.btnAprovarSegmento.innerHTML = '<span aria-hidden="true">✓</span><span>Aprovar & Próximo</span><kbd class="tecla-atalho">Alt+A</kbd>';
        el.btnAprovarSegmento.classList.add("btn-sucesso");
        el.btnAprovarSegmento.classList.remove("btn-secundario");
      }

      mostrarToast("Aprovação desfeita! A frase voltou para 'Pendente de Revisão'.", "↩️");
      await carregarEstatisticas();
    } catch (e) {
      console.error("Erro ao desfazer aprovação:", e);
      mostrarToast(`Erro ao desfazer aprovação: ${e.message}`, "✕");
    }
  }

  async function alternarStatusSegmentoAtual() {
    if (!estado.segmentoAtual) return;
    const ehAprovado = estado.segmentoAtual.status === "revisado" || estado.segmentoAtual.status === "aprovado";
    if (ehAprovado) {
      await desfazerAprovacaoAtual();
    } else {
      await salvarSegmentoAtual(false, true);
    }
  }

  function abrirModalPropagacao(novaTraducao, novoStatus, avancar) {
    el.spanContagemRepeticoes.textContent = (estado.segmentoAtual.repeticoes_totais - 1).toString();
    el.spanNovaTraducaoPropagar.textContent = novaTraducao;

    const itens = estado.segmentoAtual.itens_repetidos || [];
    el.listaPreviaRepeticoes.innerHTML = itens.map(i => `
      <div class="item-previa-repeticao">
        <code>${escaparHtml(i.chave_hierarquica)}</code>
        <span style="color: var(--cor-texto-mutado); font-size: 0.75rem;">${escaparHtml(i.arquivo)}</span>
      </div>
    `).join("") || "<div style='color: var(--cor-texto-mutado); font-style: italic; padding: 0.5rem;'>Demais ocorrências no projeto.</div>";

    estado.acaoAposPropagacao = { novaTraducao, novoStatus, avancar };
    abrirModal(el.modalPropagacao);
  }

  async function confirmarPropagacao(propagarTodos) {
    fecharModal(el.modalPropagacao);
    if (!estado.acaoAposPropagacao) return;

    const { novaTraducao, novoStatus, avancar } = estado.acaoAposPropagacao;
    estado.acaoAposPropagacao = null;

    try {
      await ApiCat.salvarSegmento(estado.idSegmentoAtual, novaTraducao, novoStatus, propagarTodos);
      estado.textoOriginalCarregado = novaTraducao;
      mostrarToast(propagarTodos ? "Tradução propagada para todas as repetições!" : "Salvo apenas neste segmento.", "🔁");
      await carregarEstatisticas();

      if (avancar) {
        await navegarDirecao("proximo");
      }
    } catch (e) {
      mostrarToast(`Erro ao salvar: ${e.message}`, "✕");
    }
  }

  // Prioriza a retradução feita nesta sessão (com glossário) sobre a tradução base antiga.
  function obterTextoIaAtual() {
    const seg = estado.segmentoAtual;
    if (!seg) return "";
    return seg.traducao_ia_regerada ?? seg.traducao_atual;
  }

  function copiarTextoParaEditor(texto, rotuloOrigem) {
    if (texto === undefined || texto === null) return;
    el.campoTraducaoHumana.value = texto;
    atualizarMetricasTexto();
    validarTagsTempoReal();
    el.campoTraducaoHumana.focus();
    mostrarToast(`Copiado da versão ${rotuloOrigem}`, "📋");
  }

  async function traduzirComIaAtual() {
    if (!estado.segmentoAtual) return;
    const textoMod = estado.segmentoAtual.mod_en;
    if (!textoMod) return;

    el.btnGerarIaAgora.disabled = true;
    el.btnGerarIaAgora.innerHTML = "<span>Gerando...</span>";
    mostrarToast("Consultando IA Gemini...", "⏳");

    try {
      const res = await ApiCat.traduzirIa(textoMod);
      if (res.sucesso && res.traducao) {
        estado.segmentoAtual.traducao_ia_regerada = res.traducao;
        el.conteudoIaPt.innerHTML = destacarTagsCastleDB(res.traducao);
        copiarTextoParaEditor(res.traducao, "IA Gemini");
        mostrarToast("Tradução gerada com sucesso pela IA!", "✨");
      } else {
        mostrarToast(`IA: ${res.erro || "Sem resposta"}`, "⚠️");
      }
    } catch (e) {
      mostrarToast(`Falha na IA: ${e.message}`, "✕");
    } finally {
      el.btnGerarIaAgora.disabled = false;
      el.btnGerarIaAgora.innerHTML = `<span>Traduzir com IA</span> <kbd class="tecla-atalho">Alt+T</kbd>`;
    }
  }

  // ----------------------------------------------------------------------------
  // Manipulação de Tags e Toolbar CastleDB
  // ----------------------------------------------------------------------------
  function inserirTextoNaPosicaoCursor(textoInserir) {
    const area = el.campoTraducaoHumana;
    const inicio = area.selectionStart;
    const fim = area.selectionEnd;
    const textoAtual = area.value;

    area.value = textoAtual.substring(0, inicio) + textoInserir + textoAtual.substring(fim);
    area.selectionStart = area.selectionEnd = inicio + textoInserir.length;
    area.focus();
    atualizarMetricasTexto();
    validarTagsTempoReal();
  }

  function envolverSelecaoComTags(tagAbertura, tagFechamento) {
    const area = el.campoTraducaoHumana;
    const inicio = area.selectionStart;
    const fim = area.selectionEnd;
    const textoAtual = area.value;
    const textoSelecionado = textoAtual.substring(inicio, fim) || "texto";

    const textoSubstituto = tagAbertura + textoSelecionado + tagFechamento;
    area.value = textoAtual.substring(0, inicio) + textoSubstituto + textoAtual.substring(fim);
    area.selectionStart = inicio + tagAbertura.length;
    area.selectionEnd = area.selectionStart + textoSelecionado.length;
    area.focus();
    atualizarMetricasTexto();
    validarTagsTempoReal();
  }

  // ----------------------------------------------------------------------------
  // Modo Visão Geral: Árvore Hierárquica e Busca Global
  // ----------------------------------------------------------------------------
  async function carregarArvore() {
    try {
      const arvore = await ApiCat.obterArvore();
      estado.arvore = Array.isArray(arvore) ? arvore : [];
      renderizarArvore();
    } catch (e) {
      console.error("Erro ao carregar árvore:", e);
      if (el.containerArvore) {
        el.containerArvore.innerHTML = `<div style="padding: 1rem; color: var(--cor-erro); font-size: 0.85rem;">Erro ao carregar estrutura do jogo: ${escaparHtml(e.message)}</div>`;
      }
    }
  }

  function renderizarArvore() {
    el.containerArvore.innerHTML = "";

    estado.arvore.forEach(noArquivo => {
      const divArquivo = document.createElement("div");
      divArquivo.className = "no-arquivo";
      if (!estado.pastasAbertas.has(noArquivo.id_no)) {
        divArquivo.classList.add("recolhido");
      }

      const cabecalho = document.createElement("div");
      cabecalho.className = "no-arquivo-cabecalho";
      cabecalho.setAttribute("tabindex", "0");
      cabecalho.setAttribute("role", "treeitem");
      const estaAberto = estado.pastasAbertas.has(noArquivo.id_no);
      cabecalho.setAttribute("aria-expanded", estaAberto ? "true" : "false");
      cabecalho.innerHTML = `
        <span class="icone-pasta" aria-hidden="true">▼</span>
        <span class="nome-pasta">${escaparHtml(noArquivo.rotulo)}</span>
        <span class="contagem-no" title="Pendentes / Total">${noArquivo.total_pendentes}/${noArquivo.total_itens}</span>
      `;

      const alternarPasta = (forcarAberto = null) => {
        const deveAbrir = forcarAberto !== null ? forcarAberto : !estado.pastasAbertas.has(noArquivo.id_no);
        if (deveAbrir) {
          estado.pastasAbertas.add(noArquivo.id_no);
          divArquivo.classList.remove("recolhido");
          cabecalho.setAttribute("aria-expanded", "true");
        } else {
          estado.pastasAbertas.delete(noArquivo.id_no);
          divArquivo.classList.add("recolhido");
          cabecalho.setAttribute("aria-expanded", "false");
        }
      };

      cabecalho.addEventListener("click", () => alternarPasta());
      cabecalho.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          alternarPasta();
        } else if (e.key === "ArrowRight") {
          e.preventDefault();
          alternarPasta(true);
        } else if (e.key === "ArrowLeft") {
          e.preventDefault();
          alternarPasta(false);
        }
      });

      const listaFilhos = document.createElement("ul");
      listaFilhos.className = "lista-filhos";
      listaFilhos.setAttribute("role", "group");

      noArquivo.categorias.forEach(cat => {
        const itemCat = document.createElement("li");
        itemCat.className = "item-categoria";
        itemCat.setAttribute("tabindex", "0");
        itemCat.setAttribute("role", "treeitem");
        if (estado.filtro.categoria === cat.nome && estado.filtro.arquivo === cat.arquivo) {
          itemCat.classList.add("selecionado");
        }

        itemCat.innerHTML = `
          <span>🏷️ ${escaparHtml(cat.nome)}</span>
          <span class="contagem-no">${cat.pendentes}/${cat.total}</span>
        `;

        const selecionarCategoria = () => {
          document.querySelectorAll(".item-categoria").forEach(c => c.classList.remove("selecionado"));
          itemCat.classList.add("selecionado");
          estado.filtro.arquivo = cat.arquivo;
          estado.filtro.categoria = cat.nome;
          estado.filtro.pagina = 1;
          carregarListaOverview();
        };

        itemCat.addEventListener("click", selecionarCategoria);
        itemCat.addEventListener("keydown", (e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            selecionarCategoria();
          }
        });

        listaFilhos.appendChild(itemCat);
      });

      divArquivo.appendChild(cabecalho);
      divArquivo.appendChild(listaFilhos);
      el.containerArvore.appendChild(divArquivo);
    });
  }

  async function carregarListaOverview() {
    el.tabelaSegmentos.innerHTML = '<div style="padding: 2rem; text-align: center; color: var(--cor-texto-mutado);">Buscando segmentos no banco de dados...</div>';

    try {
      const filtrosConsulta = obterFiltrosAtivos();
      const dados = await ApiCat.buscarSegmentos(filtrosConsulta);

      estado.filtro.totalPaginas = dados.total_paginas || 1;
      el.textoPaginacaoInfo.textContent = `Página ${dados.pagina_atual} de ${dados.total_paginas} (${dados.total_itens.toLocaleString("pt-BR")} itens)`;
      el.btnPaginaAnterior.disabled = dados.pagina_atual <= 1;
      el.btnPaginaProxima.disabled = dados.pagina_atual >= dados.total_paginas;

      if (!dados.itens || dados.itens.length === 0) {
        el.tabelaSegmentos.innerHTML = '<div style="padding: 2rem; text-align: center; color: var(--cor-texto-mutado);">Nenhum segmento encontrado para os filtros selecionados.</div>';
        return;
      }

      el.tabelaSegmentos.innerHTML = "";
      dados.itens.forEach(item => {
        const linha = document.createElement("article");
        linha.className = "linha-segmento-overview";
        linha.setAttribute("tabindex", "0");
        linha.setAttribute("role", "button");
        linha.setAttribute("aria-label", `Segmento #${item.id}, arquivo ${item.arquivo}, status ${item.status === "revisado" ? "Aprovado" : "Pendente"}`);
        linha.innerHTML = `
          <header class="linha-segmento-topo">
            <div style="display: flex; gap: 0.5rem; align-items: center;">
              <strong style="color: var(--cor-primaria-clara);">#${item.id}</strong>
              <span class="badge-tag">${escaparHtml(item.arquivo)}</span>
              <span style="color: var(--cor-texto-mutado); font-family: var(--fonte-mono); font-size: 0.8rem;">${escaparHtml(item.chave_hierarquica)}</span>
            </div>
            <span class="badge-status status-${item.status}">${item.status === "revisado" ? "Aprovado" : "Pendente"}</span>
          </header>
          <div class="linha-segmento-comparacao">
            <div class="col-previa">
              <span class="rotulo-col-previa">Original EN:</span>
              <p>${destacarTagsCastleDB(item.mod_en)}</p>
            </div>
            <div class="col-previa">
              <span class="rotulo-col-previa">Tradução:</span>
              <p style="color: var(--cor-sucesso);">${destacarTagsCastleDB(item.traducao_revisada || item.traducao_atual)}</p>
            </div>
          </div>
        `;

        linha.addEventListener("click", () => {
          alternarModo("foco");
          carregarSegmento(item.id);
        });

        linha.addEventListener("keydown", (e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            alternarModo("foco");
            carregarSegmento(item.id);
          }
        });

        el.tabelaSegmentos.appendChild(linha);
      });
    } catch (e) {
      el.tabelaSegmentos.innerHTML = `<div style="padding: 2rem; color: var(--cor-erro);">Erro ao carregar lista: ${e.message}</div>`;
    }
  }

  // ----------------------------------------------------------------------------
  // Alternância de Modos e Modais
  // ----------------------------------------------------------------------------
  function alternarModo(modo) {
    estado.modoAtual = modo;
    if (modo === "foco") {
      el.secaoModoFoco.classList.remove("oculto");
      el.secaoModoOverview.classList.add("oculto");
      el.btnModoFoco.classList.add("ativo");
      el.btnModoFoco.setAttribute("aria-pressed", "true");
      el.btnModoOverview.classList.remove("ativo");
      el.btnModoOverview.setAttribute("aria-pressed", "false");
      el.campoTraducaoHumana.focus();
    } else {
      el.secaoModoFoco.classList.add("oculto");
      el.secaoModoOverview.classList.remove("oculto");
      el.btnModoFoco.classList.remove("ativo");
      el.btnModoFoco.setAttribute("aria-pressed", "false");
      el.btnModoOverview.classList.add("ativo");
      el.btnModoOverview.setAttribute("aria-pressed", "true");
      carregarArvore();
      carregarListaOverview();
      el.inputBuscaGlobal.focus();
    }
  }

  async function executarCompilacaoMod() {
    el.btnIniciarCompilacaoExec.disabled = true;
    el.btnIniciarCompilacaoExec.innerHTML = `<span>⏳ Compilando Mod...</span>`;
    el.statusCompilacaoLog.innerHTML = `<span style="color: var(--cor-primaria-clara);">Iniciando compilação de XMLs e empacotador PAK...</span>`;
    try {
      const res = await ApiCat.compilarProjeto();
      if (res.sucesso) {
        el.statusCompilacaoLog.innerHTML = `
          <strong style="color: var(--cor-sucesso);">✓ Compilação concluída com sucesso!</strong><br><br>
          • Arquivo export_pt-BR.xml compilado e sanitizado.<br>
          • Arquivo texts_pt-BR.xml compilado.<br>
          • Arquivo <strong>res2.pak</strong> gerado com cabeçalho oficial Heaps.io (${res.res2_pak_bytes ? (res.res2_pak_bytes / 1024 / 1024).toFixed(2) + " MB" : "OK"}).<br>
          • Pacote de distribuição para o Nexus Mods atualizado em <code>saida/distribuicao_nexus/</code>.
        `;
        mostrarToast("Mod compilado com sucesso!", "📦");
      } else {
        el.statusCompilacaoLog.innerHTML = `<span style="color: var(--cor-erro);">Erro: ${res.erro}</span>`;
      }
    } catch (e) {
      el.statusCompilacaoLog.innerHTML = `<span style="color: var(--cor-erro);">Falha: ${e.message}</span>`;
    } finally {
      el.btnIniciarCompilacaoExec.disabled = false;
      el.btnIniciarCompilacaoExec.innerHTML = `<span>🚀 Executar Compilação</span>`;
    }
  }

  // ----------------------------------------------------------------------------
  // Controlador do Relatório Inteligente & Gerador Nexus Mods
  // ----------------------------------------------------------------------------
  const estadoRelatorio = {
    abaAtiva: "metricas",
    dados: null,
    filtrosFaltantes: {
      escopo: "apenas_mod",
      status: "pendentes",
      arquivo: "",
      categoria: "",
      termo: "",
      pagina: 1,
      limite: 15,
      totalPaginas: 1,
      totalItens: 0
    },
    timerDebounceFaltantes: null
  };

  function abrirModalRelatorio(abaInicial = "metricas") {
    if (!el.modalRelatorio) return;
    abrirModal(el.modalRelatorio, el.btnAbrirRelatorio || el.containerProgressoGeral);
    alternarAbaRelatorio(abaInicial);
    carregarDadosRelatorio();
  }

  function fecharModalRelatorio() {
    if (el.modalRelatorio) {
      fecharModal(el.modalRelatorio);
    }
  }

  function alternarAbaRelatorio(aba) {
    estadoRelatorio.abaAtiva = aba;

    const abas = [
      { id: "metricas", btn: el.btnAbaRelatorioMetricas, painel: el.painelAbaRelatorioMetricas },
      { id: "faltantes", btn: el.btnAbaRelatorioFaltantes, painel: el.painelAbaRelatorioFaltantes },
      { id: "nexus", btn: el.btnAbaRelatorioNexus, painel: el.painelAbaRelatorioNexus }
    ];

    abas.forEach(item => {
      if (item.btn && item.painel) {
        const ativo = item.id === aba;
        item.btn.classList.toggle("ativo", ativo);
        item.btn.setAttribute("aria-selected", ativo ? "true" : "false");
        item.painel.classList.toggle("oculto", !ativo);
      }
    });

    if (aba === "faltantes") {
      carregarItensFaltantesRelatorio(estadoRelatorio.filtrosFaltantes.pagina || 1);
    } else if (aba === "nexus") {
      atualizarGeradorNexus();
    }
  }

  async function carregarDadosRelatorio() {
    try {
      const rel = await ApiCat.obterRelatorio();
      estadoRelatorio.dados = rel;
      renderizarMetricasRelatorio(rel);
      await carregarEstatisticas();

      if (estadoRelatorio.abaAtiva === "faltantes") {
        await carregarItensFaltantesRelatorio(estadoRelatorio.filtrosFaltantes.pagina || 1);
      } else if (estadoRelatorio.abaAtiva === "nexus") {
        await atualizarGeradorNexus();
      }
    } catch (e) {
      console.error("Erro ao carregar dados do relatório:", e);
      mostrarToast(`Falha ao obter relatório: ${e.message}`, "✕");
    }
  }

  function renderizarMetricasRelatorio(rel) {
    if (!rel) return;
    const mod = rel.mod || {};
    const novos = rel.novos || {};
    const modif = rel.modificados || {};
    const vanilla = rel.vanilla || {};
    const geral = rel.geral || {};

    // 1. Banner explicativo
    if (el.relatorioBannerTotalGeral) el.relatorioBannerTotalGeral.textContent = `${geral.total?.toLocaleString("pt-BR") || 0} frases`;
    if (el.relatorioBannerTotalMod) el.relatorioBannerTotalMod.textContent = `${mod.total?.toLocaleString("pt-BR") || 0} termos`;
    if (el.relatorioBannerPctGeral) el.relatorioBannerPctGeral.textContent = `${geral.porcentagem_revisao || 0}%`;
    if (el.relatorioBannerPctMod) el.relatorioBannerPctMod.textContent = `${mod.porcentagem_revisao || 0}%`;

    // 2. Card Escopo do Mod
    if (el.relatorioModPctRevisao) el.relatorioModPctRevisao.textContent = `${mod.porcentagem_revisao || 0}%`;
    if (el.relatorioModBarraRevisao) el.relatorioModBarraRevisao.style.width = `${mod.porcentagem_revisao || 0}%`;
    if (el.relatorioModContagemRevisao) el.relatorioModContagemRevisao.textContent = `${(mod.revisados || 0).toLocaleString("pt-BR")} de ${(mod.total || 0).toLocaleString("pt-BR")} validados`;
    if (el.relatorioModPendentesTexto) el.relatorioModPendentesTexto.textContent = `${(mod.pendentes || 0).toLocaleString("pt-BR")} pendentes`;
    if (el.relatorioModPctTraducao) el.relatorioModPctTraducao.textContent = `${mod.porcentagem_traducao || 0}%`;
    if (el.relatorioModBarraTraducao) el.relatorioModBarraTraducao.style.width = `${mod.porcentagem_traducao || 0}%`;
    if (el.relatorioModContagemTraducao) el.relatorioModContagemTraducao.textContent = `${(mod.com_traducao || 0).toLocaleString("pt-BR")} de ${(mod.total || 0).toLocaleString("pt-BR")} prontos para gameplay`;

    // 3. Card Termos Novos
    if (el.relatorioNovosPct) el.relatorioNovosPct.textContent = `${novos.porcentagem_revisao || 0}%`;
    if (el.relatorioNovosBarra) el.relatorioNovosBarra.style.width = `${novos.porcentagem_revisao || 0}%`;
    if (el.relatorioNovosContagem) el.relatorioNovosContagem.textContent = `${(novos.revisados || 0).toLocaleString("pt-BR")} de ${(novos.total || 0).toLocaleString("pt-BR")} termos`;
    if (el.relatorioNovosPendentes) el.relatorioNovosPendentes.textContent = `${(novos.pendentes || 0).toLocaleString("pt-BR")} a revisar`;
    if (el.relatorioNovosTraduzidosPct) el.relatorioNovosTraduzidosPct.textContent = `${novos.porcentagem_traducao || 0}%`;

    // 4. Card Termos Modificados
    if (el.relatorioModificadosPct) el.relatorioModificadosPct.textContent = `${modif.porcentagem_revisao || 0}%`;
    if (el.relatorioModificadosBarra) el.relatorioModificadosBarra.style.width = `${modif.porcentagem_revisao || 0}%`;
    if (el.relatorioModificadosContagem) el.relatorioModificadosContagem.textContent = `${(modif.revisados || 0).toLocaleString("pt-BR")} de ${(modif.total || 0).toLocaleString("pt-BR")} termos`;
    if (el.relatorioModificadosPendentes) el.relatorioModificadosPendentes.textContent = `${(modif.pendentes || 0).toLocaleString("pt-BR")} a revisar`;
    if (el.relatorioModificadosTraduzidosPct) el.relatorioModificadosTraduzidosPct.textContent = `${modif.porcentagem_traducao || 0}%`;

    // 5. Card Vanilla
    if (el.relatorioVanillaOficialPct) el.relatorioVanillaOficialPct.textContent = `${vanilla.porcentagem_oficial || 0}%`;
    if (el.relatorioVanillaTotal) el.relatorioVanillaTotal.textContent = `${(vanilla.total || 0).toLocaleString("pt-BR")} termos`;

    // 6. Card Banco Geral
    if (el.relatorioGeralPct) el.relatorioGeralPct.textContent = `${geral.porcentagem_revisao || 0}%`;
    if (el.relatorioGeralBarra) el.relatorioGeralBarra.style.width = `${geral.porcentagem_revisao || 0}%`;
    if (el.relatorioGeralContagem) el.relatorioGeralContagem.textContent = `${(geral.revisados || 0).toLocaleString("pt-BR")} de ${(geral.total || 0).toLocaleString("pt-BR")} termos`;
    if (el.relatorioGeralInconsistencias) el.relatorioGeralInconsistencias.textContent = `${(mod.avisos_qa || 0).toLocaleString("pt-BR")} avisos QA no mod`;

    // 7. Tabela de Arquivos e Povoamento do Seletor
    if (el.tabelaRelatorioArquivosCorpo) {
      el.tabelaRelatorioArquivosCorpo.innerHTML = "";
      const arqs = rel.arquivos || [];

      if (el.selectRelatorioFiltroArquivo) {
        const valAtual = estadoRelatorio.filtrosFaltantes.arquivo || "";
        el.selectRelatorioFiltroArquivo.innerHTML = '<option value="">📁 Todos os Arquivos</option>';
        arqs.forEach(a => {
          const opt = document.createElement("option");
          opt.value = a.arquivo;
          opt.textContent = `${a.arquivo} (${a.rotulo_amigavel || ''})`;
          el.selectRelatorioFiltroArquivo.appendChild(opt);
        });
        el.selectRelatorioFiltroArquivo.value = valAtual;
      }

      if (arqs.length === 0) {
        el.tabelaRelatorioArquivosCorpo.innerHTML = `<tr><td colspan="7" class="tabela-vazia">Nenhum arquivo encontrado no banco de dados.</td></tr>`;
      } else {
        arqs.forEach(arq => {
          const tr = document.createElement("tr");
          tr.innerHTML = `
            <td><strong>${escaparHtml(arq.arquivo)}</strong></td>
            <td><span class="texto-mutado-sm">${escaparHtml(arq.rotulo_amigavel || "")}</span></td>
            <td><strong>${(arq.mod_total || 0).toLocaleString("pt-BR")}</strong></td>
            <td>${(arq.mod_com_traducao || 0).toLocaleString("pt-BR")} <span class="texto-mutado-sm">(${arq.porcentagem_traducao_mod || 0}%)</span></td>
            <td><strong class="texto-sucesso">${(arq.mod_revisados || 0).toLocaleString("pt-BR")}</strong> <span class="texto-mutado-sm">(${arq.porcentagem_revisao_mod || 0}%)</span></td>
            <td><strong class="texto-alerta">${(arq.mod_pendentes || 0).toLocaleString("pt-BR")}</strong></td>
            <td>
              <button type="button" class="btn btn-compacto btn-secundario btn-filtrar-arquivo-relatorio" data-arquivo="${escaparHtml(arq.arquivo)}" title="Filtrar pendências deste arquivo">
                🔍 Ver Faltantes
              </button>
            </td>
          `;
          const btnFiltrar = tr.querySelector(".btn-filtrar-arquivo-relatorio");
          if (btnFiltrar) {
            btnFiltrar.addEventListener("click", () => {
              estadoRelatorio.filtrosFaltantes.arquivo = arq.arquivo;
              estadoRelatorio.filtrosFaltantes.categoria = "";
              if (el.selectRelatorioFiltroArquivo) el.selectRelatorioFiltroArquivo.value = arq.arquivo;
              if (el.selectRelatorioFiltroCategoria) el.selectRelatorioFiltroCategoria.value = "";
              alternarAbaRelatorio("faltantes");
            });
          }
          el.tabelaRelatorioArquivosCorpo.appendChild(tr);
        });
      }
    }

    // 8. Top Categorias e Povoamento do Seletor de Categoria
    if (el.containerRelatorioTopCategorias) {
      el.containerRelatorioTopCategorias.innerHTML = "";
      const cats = rel.top_categorias || [];

      if (el.selectRelatorioFiltroCategoria) {
        const catAtual = estadoRelatorio.filtrosFaltantes.categoria || "";
        el.selectRelatorioFiltroCategoria.innerHTML = '<option value="">🏷️ Todas as Categorias</option>';
        const categoriasUnicas = new Set();
        cats.forEach(c => {
          if (!categoriasUnicas.has(c.categoria)) {
            categoriasUnicas.add(c.categoria);
            const opt = document.createElement("option");
            opt.value = c.categoria;
            opt.textContent = `🏷️ ${c.categoria} (${c.pendentes || 0} a revisar)`;
            el.selectRelatorioFiltroCategoria.appendChild(opt);
          }
        });
        el.selectRelatorioFiltroCategoria.value = catAtual;
      }

      if (cats.length === 0) {
        el.containerRelatorioTopCategorias.innerHTML = `<div class="carregando-texto">Nenhuma pendência encontrada nas categorias.</div>`;
      } else {
        cats.forEach(c => {
          const divCat = document.createElement("div");
          divCat.className = "card-categoria-relatorio";
          divCat.title = `Clique para ver pendências da categoria ${c.categoria}`;
          divCat.innerHTML = `
            <div class="card-categoria-topo">
              <span>🏷️ ${escaparHtml(c.categoria)}</span>
              <span class="texto-alerta font-bold">${c.pendentes || 0} a revisar</span>
            </div>
            <div class="texto-mutado-sm">${escaparHtml(c.arquivo)} (${c.total_categoria || 0} frases)</div>
          `;
          divCat.addEventListener("click", () => {
            estadoRelatorio.filtrosFaltantes.arquivo = c.arquivo;
            estadoRelatorio.filtrosFaltantes.categoria = c.categoria;
            estadoRelatorio.filtrosFaltantes.termo = "";
            if (el.selectRelatorioFiltroArquivo) el.selectRelatorioFiltroArquivo.value = c.arquivo;
            if (el.selectRelatorioFiltroCategoria) el.selectRelatorioFiltroCategoria.value = c.categoria;
            if (el.inputRelatorioBuscaFaltantes) el.inputRelatorioBuscaFaltantes.value = "";
            alternarAbaRelatorio("faltantes");
          });
          el.containerRelatorioTopCategorias.appendChild(divCat);
        });
      }
    }
  }

  async function carregarItensFaltantesRelatorio(pagina = 1) {
    if (!el.tabelaRelatorioFaltantesCorpo) return;
    estadoRelatorio.filtrosFaltantes.pagina = pagina;

    const filtros = {
      pagina: pagina,
      limite: estadoRelatorio.filtrosFaltantes.limite || 15
    };

    const escopo = estadoRelatorio.filtrosFaltantes.escopo;
    if (escopo === "inconsistencias") {
      filtros.inconsistencias = true;
      filtros.origem = "apenas_mod";
    } else if (escopo === "sem_ia") {
      filtros.sem_ia = true;
      filtros.origem = "apenas_mod";
    } else if (escopo && escopo !== "todos") {
      filtros.origem = escopo;
    }

    const st = estadoRelatorio.filtrosFaltantes.status;
    if (st && st !== "todos") {
      filtros.status = st;
    }

    if (estadoRelatorio.filtrosFaltantes.arquivo) {
      filtros.arquivo = estadoRelatorio.filtrosFaltantes.arquivo;
    }

    if (estadoRelatorio.filtrosFaltantes.categoria) {
      filtros.categoria = estadoRelatorio.filtrosFaltantes.categoria;
    }

    if (estadoRelatorio.filtrosFaltantes.termo) {
      filtros.termo = estadoRelatorio.filtrosFaltantes.termo;
    }

    el.tabelaRelatorioFaltantesCorpo.innerHTML = `<tr><td colspan="6" class="tabela-vazia">Carregando lista de pendências...</td></tr>`;

    try {
      const res = await ApiCat.buscarSegmentos(filtros);
      estadoRelatorio.filtrosFaltantes.totalPaginas = res.total_paginas || 1;
      estadoRelatorio.filtrosFaltantes.totalItens = res.total_itens || 0;

      renderizarTabelaFaltantes(res);
    } catch (e) {
      console.error("Erro ao buscar itens faltantes:", e);
      el.tabelaRelatorioFaltantesCorpo.innerHTML = `<tr><td colspan="6" class="tabela-vazia" style="color: var(--cor-erro);">Erro: ${e.message}</td></tr>`;
    }
  }

  function renderizarTabelaFaltantes(res) {
    const itens = res.itens || [];
    el.tabelaRelatorioFaltantesCorpo.innerHTML = "";

    if (el.relatorioFaltantesResumoContador) {
      el.relatorioFaltantesResumoContador.textContent = `Mostrando ${(res.total_itens || 0).toLocaleString("pt-BR")} termos correspondentes aos critérios`;
    }

    if (el.relatorioFaltantesPaginacaoInfo) {
      el.relatorioFaltantesPaginacaoInfo.textContent = `Página ${res.pagina_atual || 1} de ${res.total_paginas || 1} (${(res.total_itens || 0).toLocaleString("pt-BR")} itens)`;
    }

    if (el.btnRelatorioPagAnterior) {
      el.btnRelatorioPagAnterior.disabled = (res.pagina_atual || 1) <= 1;
    }
    if (el.btnRelatorioPagProxima) {
      el.btnRelatorioPagProxima.disabled = (res.pagina_atual || 1) >= (res.total_paginas || 1);
    }

    if (itens.length === 0) {
      el.tabelaRelatorioFaltantesCorpo.innerHTML = `<tr><td colspan="6" class="tabela-vazia">Nenhum termo faltante encontrado com os filtros selecionados. Parabéns! 🎉</td></tr>`;
      return;
    }

    itens.forEach(seg => {
      const tr = document.createElement("tr");

      let badgeDelta = `<span class="badge badge-delta-vanilla">🏛️ Vanilla</span>`;
      if (seg.tipo_delta === "novo" || (!seg.vanilla_en && seg.vanilla_en !== 0)) {
        badgeDelta = `<span class="badge badge-delta-novo">✨ Novo</span>`;
      } else if (seg.tipo_delta === "modificado" || (seg.vanilla_en && seg.mod_en !== seg.vanilla_en)) {
        badgeDelta = `<span class="badge badge-delta-modificado">✏️ Modificado</span>`;
      }

      let badgeStatus = `<span class="badge badge-pendente">⏳ Pendente</span>`;
      if (seg.status === "revisado") {
        badgeStatus = `<span class="badge badge-revisado">✓ Revisado</span>`;
      }
      if (seg.tem_inconsistencia || seg.aviso_qa) {
        badgeStatus += ` <span class="badge badge-alerta" title="${escaparHtml(seg.aviso_qa || 'Inconsistência de QA')}">⚠️ QA</span>`;
      }

      const textoEn = seg.mod_en || "";
      const textoTrad = seg.traducao_revisada || seg.traducao_atual || "";

      tr.innerHTML = `
        <td>${badgeDelta}</td>
        <td>
          <div style="font-weight: 600; font-size: 0.8rem; color: var(--cor-texto-titulo);">${escaparHtml(seg.arquivo)}</div>
          <div style="font-size: 0.75rem; color: var(--cor-texto-mutado); word-break: break-all;">${escaparHtml(seg.chave_hierarquica)}</div>
        </td>
        <td><div style="max-height: 70px; overflow-y: auto;">${escaparHtml(textoEn)}</div></td>
        <td><div style="max-height: 70px; overflow-y: auto; color: ${textoTrad ? 'var(--cor-texto-corpo)' : 'var(--cor-alerta)'};">${escaparHtml(textoTrad || '(Sem tradução)')}</div></td>
        <td>${badgeStatus}</td>
        <td style="text-align: center;">
          <button type="button" class="btn btn-compacto btn-primario btn-abrir-foco-linha" title="Editar este segmento no Modo Foco" data-id="${seg.id}">
            🎯 Foco
          </button>
        </td>
      `;

      const btnFoco = tr.querySelector(".btn-abrir-foco-linha");
      if (btnFoco) {
        btnFoco.addEventListener("click", () => {
          abrirSegmentoNoFocoDeRelatorio(seg.id);
        });
      }

      el.tabelaRelatorioFaltantesCorpo.appendChild(tr);
    });
  }

  function abrirSegmentoNoFocoDeRelatorio(idSegmento) {
    const escopo = estadoRelatorio.filtrosFaltantes.escopo;
    const st = estadoRelatorio.filtrosFaltantes.status;

    if (escopo === "inconsistencias") {
      estado.filtro.origem = "apenas_mod";
      estado.filtro.especial = "inconsistencias";
    } else if (escopo === "sem_ia") {
      estado.filtro.origem = "apenas_mod";
      estado.filtro.especial = "sem_ia";
    } else {
      estado.filtro.origem = escopo || "apenas_mod";
      estado.filtro.especial = "todos";
    }

    estado.filtro.status = st || "pendentes";
    estado.filtro.arquivo = estadoRelatorio.filtrosFaltantes.arquivo || "";
    estado.filtro.categoria = estadoRelatorio.filtrosFaltantes.categoria || "";
    estado.filtro.termo = estadoRelatorio.filtrosFaltantes.termo || "";

    sincronizarFiltrosUI();
    fecharModalRelatorio();
    alternarModo("foco");
    carregarSegmento(idSegmento);
    setTimeout(() => {
      if (el.campoTraducaoHumana) {
        el.campoTraducaoHumana.focus();
        el.campoTraducaoHumana.select();
      }
    }, 150);
  }

  function aplicarFiltroFaltantesNoModoFoco() {
    const escopo = estadoRelatorio.filtrosFaltantes.escopo;
    const st = estadoRelatorio.filtrosFaltantes.status;

    if (escopo === "inconsistencias") {
      estado.filtro.origem = "apenas_mod";
      estado.filtro.especial = "inconsistencias";
    } else if (escopo === "sem_ia") {
      estado.filtro.origem = "apenas_mod";
      estado.filtro.especial = "sem_ia";
    } else {
      estado.filtro.origem = escopo || "apenas_mod";
      estado.filtro.especial = "todos";
    }

    estado.filtro.status = st || "pendentes";
    estado.filtro.arquivo = estadoRelatorio.filtrosFaltantes.arquivo || "";
    estado.filtro.categoria = estadoRelatorio.filtrosFaltantes.categoria || "";
    estado.filtro.termo = estadoRelatorio.filtrosFaltantes.termo || "";

    sincronizarFiltrosUI();
    fecharModalRelatorio();
    alternarModo("foco");
    aplicarNovoFiltroFoco(true);
    mostrarToast("Filtro do relatório aplicado com sucesso no Modo Foco!", "🎯");
  }

  async function atualizarGeradorNexus() {
    if (!el.textareaNexusBbcode || !el.containerNexusPreview) return;

    const opcoes = {
      modelo: el.selectNexusModelo?.value || "atualizacao",
      nome_mod: el.inputNexusNomeMod?.value?.trim() || "Wartales Remastered",
      versao_mod: el.inputNexusVersaoMod?.value?.trim() || "v7.40",
      autor: el.inputNexusAutor?.value?.trim() || "Cassr",
      incluir_barras_progresso: el.checkNexusBarras?.checked ?? true,
      incluir_detalhes_escopo: el.checkNexusEscopo?.checked ?? true,
      incluir_detalhes_arquivos: el.checkNexusArquivos?.checked ?? true,
      incluir_castledb: el.checkNexusCastledb?.checked ?? true,
      incluir_instalacao: el.checkNexusInstalacao?.checked ?? true,
      incluir_feedback: el.checkNexusFeedback?.checked ?? true
    };

    try {
      const res = await ApiCat.gerarTextoNexus(opcoes);
      if (res && res.resultado) {
        el.textareaNexusBbcode.value = res.resultado.bbcode || "";
        el.containerNexusPreview.innerHTML = res.resultado.html_preview || "";
      }
    } catch (e) {
      console.error("Erro ao gerar texto para Nexus:", e);
    }
  }

  async function copiarBbcodeNexus() {
    const texto = el.textareaNexusBbcode?.value || "";
    if (!texto) {
      mostrarToast("Nenhum código BBCode gerado para copiar.", "⚠️");
      return;
    }
    try {
      await navigator.clipboard.writeText(texto);
      mostrarToast("Código BBCode copiado com sucesso para o Nexus!", "📋");
    } catch (e) {
      if (el.textareaNexusBbcode) {
        try {
          el.textareaNexusBbcode.select();
          document.execCommand("copy");
          mostrarToast("Código BBCode copiado!", "📋");
        } catch (errFallback) {
          mostrarToast("Texto selecionado. Pressione Ctrl+C para copiar.", "ℹ️");
        }
      }
    }
  }

  async function salvarArquivoNexus() {
    const opcoes = {
      modelo: el.selectNexusModelo?.value || "atualizacao",
      nome_mod: el.inputNexusNomeMod?.value?.trim() || "Wartales Remastered",
      versao_mod: el.inputNexusVersaoMod?.value?.trim() || "v7.40",
      autor: el.inputNexusAutor?.value?.trim() || "Cassr",
      incluir_barras_progresso: el.checkNexusBarras?.checked ?? true,
      incluir_detalhes_escopo: el.checkNexusEscopo?.checked ?? true,
      incluir_detalhes_arquivos: el.checkNexusArquivos?.checked ?? true,
      incluir_castledb: el.checkNexusCastledb?.checked ?? true,
      incluir_instalacao: el.checkNexusInstalacao?.checked ?? true,
      incluir_feedback: el.checkNexusFeedback?.checked ?? true
    };

    try {
      const res = await ApiCat.salvarTextoNexus(opcoes);
      if (res && res.sucesso) {
        mostrarToast("Salvo com sucesso em: STATUS_TRADUCAO_NEXUS.txt", "💾");
      }
    } catch (e) {
      mostrarToast(`Erro ao salvar arquivo: ${e.message}`, "✕");
    }
  }

  // ----------------------------------------------------------------------------
  // Registro de Eventos e Atalhos Globais
  // ----------------------------------------------------------------------------
  function registrarEventos() {
    // Alternância de Modos
    el.btnModoFoco.addEventListener("click", () => alternarModo("foco"));
    el.btnModoOverview.addEventListener("click", () => alternarModo("overview"));

    // Navegação Modo Foco
    el.btnAnterior.addEventListener("click", () => navegarDirecao("anterior"));
    el.btnProximo.addEventListener("click", () => navegarDirecao("proximo"));

    el.selectFiltroFoco.addEventListener("change", () => {
      const val = el.selectFiltroFoco.value;
      if (val === "mod_pendentes") {
        estado.filtro.origem = "apenas_mod";
        estado.filtro.status = "pendentes";
        estado.filtro.especial = "todos";
      } else if (val === "mod_novos_pendentes") {
        estado.filtro.origem = "novos";
        estado.filtro.status = "pendentes";
        estado.filtro.especial = "todos";
      } else if (val === "mod_modificados_pendentes") {
        estado.filtro.origem = "modificados";
        estado.filtro.status = "pendentes";
        estado.filtro.especial = "todos";
      } else if (val === "mod_todos") {
        estado.filtro.origem = "apenas_mod";
        estado.filtro.status = "todos";
        estado.filtro.especial = "todos";
      } else if (val === "pendentes") {
        estado.filtro.origem = "todos";
        estado.filtro.status = "pendentes";
        estado.filtro.especial = "todos";
      } else if (val === "aprovados") {
        estado.filtro.origem = "todos";
        estado.filtro.status = "aprovados";
        estado.filtro.especial = "todos";
      } else if (val === "inconsistencias") {
        estado.filtro.origem = "todos";
        estado.filtro.status = "todos";
        estado.filtro.especial = "inconsistencias";
      } else if (val === "sem_ia") {
        estado.filtro.origem = "todos";
        estado.filtro.status = "todos";
        estado.filtro.especial = "sem_ia";
      } else {
        estado.filtro.origem = "todos";
        estado.filtro.status = "todos";
        estado.filtro.especial = "todos";
      }
      aplicarNovoFiltroFoco(true);
    });

    if (el.btnToggleFiltrosDetalhados) {
      el.btnToggleFiltrosDetalhados.addEventListener("click", () => {
        sincronizarFiltrosUI();
        abrirModal(el.modalFiltrosAvancados, el.btnToggleFiltrosDetalhados);
      });
    }

    if (el.btnFecharModalFiltros) {
      el.btnFecharModalFiltros.addEventListener("click", () => fecharModal(el.modalFiltrosAvancados));
    }

    if (el.btnFecharModalFiltrosRodape) {
      el.btnFecharModalFiltrosRodape.addEventListener("click", () => fecharModal(el.modalFiltrosAvancados));
    }

    if (el.btnAplicarFiltrosCompostos) {
      el.btnAplicarFiltrosCompostos.addEventListener("click", () => {
        estado.filtro.origem = el.selectCompostoOrigem.value;
        estado.filtro.status = el.selectCompostoStatus.value;
        estado.filtro.especial = el.selectCompostoEspecial.value;
        fecharModal(el.modalFiltrosAvancados);
        aplicarNovoFiltroFoco(true);
        mostrarToast("Filtros compostos aplicados com sucesso!", "⚙️");
      });
    }

    if (el.btnResetarFiltrosCompostos) {
      el.btnResetarFiltrosCompostos.addEventListener("click", () => {
        estado.filtro.origem = "apenas_mod";
        estado.filtro.status = "pendentes";
        estado.filtro.especial = "todos";
        sincronizarFiltrosUI();
        fecharModal(el.modalFiltrosAvancados);
        aplicarNovoFiltroFoco(true);
        mostrarToast("Filtros restaurados para o padrão (Mod: Pendentes).", "↺");
      });
    }

    el.btnRemoverFiltroContexto.addEventListener("click", () => {
      estado.filtro.origem = "todos";
      estado.filtro.status = "todos";
      estado.filtro.especial = "todos";
      estado.filtro.categoria = "";
      estado.filtro.arquivo = "";
      estado.filtro.termo = "";
      if (el.inputBuscaGlobal) el.inputBuscaGlobal.value = "";
      document.querySelectorAll(".item-categoria").forEach(c => c.classList.remove("selecionado"));
      sincronizarFiltrosUI();
      carregarSegmento(estado.idSegmentoAtual, true);
      mostrarToast("Filtros removidos. Exibindo todas as frases.", "ℹ️");
    });

    // Salto Direto por ID
    el.inputSalto.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        const id = parseInt(el.inputSalto.value, 10);
        if (!isNaN(id) && id > 0) {
          carregarSegmento(id);
        }
      }
    });

    // Copiar das 4 Versões
    el.btnCopiarVanillaEnEditor.addEventListener("click", () => {
      if (estado.segmentoAtual) copiarTextoParaEditor(estado.segmentoAtual.vanilla_en, "Vanilla EN");
    });

    el.btnCopiarVanillaEn.addEventListener("click", () => {
      if (estado.segmentoAtual) {
        navigator.clipboard.writeText(estado.segmentoAtual.vanilla_en || "");
        mostrarToast("Texto Vanilla EN copiado para o clipboard!", "📋");
      }
    });

    el.btnCopiarVanillaPt.addEventListener("click", () => {
      if (estado.segmentoAtual) copiarTextoParaEditor(estado.segmentoAtual.vanilla_pt, "Oficial Shiro Games");
    });

    el.btnToggleDiff.addEventListener("click", () => {
      estado.exibirDiff = !estado.exibirDiff;
      renderizarModEn();
    });

    el.btnCopiarModEn.addEventListener("click", () => {
      if (estado.segmentoAtual) copiarTextoParaEditor(estado.segmentoAtual.mod_en, "Mod Inglês");
    });

    el.btnCopiarIaPt.addEventListener("click", () => {
      if (estado.segmentoAtual) copiarTextoParaEditor(obterTextoIaAtual(), "IA / TM");
    });

    el.btnGerarIaAgora.addEventListener("click", traduzirComIaAtual);

    // Botões Rápidos CastleDB
    el.btnInserirBr.addEventListener("click", () => inserirTextoNaPosicaoCursor("<br/>"));
    el.btnInserirB.addEventListener("click", () => envolverSelecaoComTags("<b>", "</b>"));
    el.btnInserirGood.addEventListener("click", () => envolverSelecaoComTags("<good>", "</good>"));
    el.btnInserirBad.addEventListener("click", () => envolverSelecaoComTags("<bad>", "</bad>"));

    el.btnInserirTodasTags.addEventListener("click", () => {
      if (!estado.segmentoAtual) return;
      const textoMod = estado.segmentoAtual.mod_en || "";
      const padraoTags = /(&lt;.*?&gt;|<[^>]+>|\[[a-zA-Z0-9_]+\]|::[a-zA-Z0-9_]+::|\$[a-zA-Z0-9_]+\$|\{[a-zA-Z0-9_]+\})/g;
      const tagsOrig = textoMod.match(padraoTags) || [];
      if (tagsOrig.length > 0) {
        const tagsJuntas = tagsOrig.join(" ");
        inserirTextoNaPosicaoCursor(" " + tagsJuntas);
        mostrarToast("Tags copiadas para o editor!", "🏷️");
      } else {
        mostrarToast("Nenhuma tag detectada na frase original.", "ℹ️");
      }
    });

    el.btnRestaurarTexto.addEventListener("click", () => {
      el.campoTraducaoHumana.value = estado.textoOriginalCarregado;
      atualizarMetricasTexto();
      validarTagsTempoReal();
      mostrarToast("Texto restaurado!", "↺");
    });

    el.btnLimparEditor.addEventListener("click", () => {
      el.campoTraducaoHumana.value = "";
      atualizarMetricasTexto();
      validarTagsTempoReal();
      el.campoTraducaoHumana.focus();
    });

    // Botões de Atalho do Rodapé do Editor
    el.btnAtalhoCopiarOficial.addEventListener("click", () => {
      if (estado.segmentoAtual) copiarTextoParaEditor(estado.segmentoAtual.vanilla_pt, "Oficial Shiro");
    });

    el.btnAtalhoCopiarIa.addEventListener("click", () => {
      if (estado.segmentoAtual) copiarTextoParaEditor(obterTextoIaAtual(), "IA Gemini");
    });

    el.btnAtalhoCopiarMod.addEventListener("click", () => {
      if (estado.segmentoAtual) copiarTextoParaEditor(estado.segmentoAtual.mod_en, "Mod EN");
    });

    // Ações do Editor
    el.badgeRepeticoes.addEventListener("click", () => {
      if (estado.segmentoAtual && estado.segmentoAtual.repeticoes_totais > 1) {
        abrirModalPropagacao(el.campoTraducaoHumana.value, estado.segmentoAtual.status, false);
      }
    });

    el.btnSalvarPermanecer.addEventListener("click", () => salvarSegmentoAtual(false, false));
    el.btnAprovarSegmento.addEventListener("click", () => salvarSegmentoAtual(true, true));
    if (el.btnDesfazerAprovacao) {
      el.btnDesfazerAprovacao.addEventListener("click", () => desfazerAprovacaoAtual());
    }
    el.btnSalvarAvancar.addEventListener("click", () => salvarSegmentoAtual(true, true));

    // Clique e foco no Badge de Status para alternar
    if (el.badgeStatus) {
      el.badgeStatus.addEventListener("click", () => alternarStatusSegmentoAtual());
      el.badgeStatus.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          alternarStatusSegmentoAtual();
        }
      });
    }

    // Input do Editor
    el.campoTraducaoHumana.addEventListener("input", () => {
      atualizarMetricasTexto();
      validarTagsTempoReal();
    });

    // Busca Global Overview com Debounce
    el.inputBuscaGlobal.addEventListener("input", () => {
      clearTimeout(estado.timerDebounceBusca);
      estado.timerDebounceBusca = setTimeout(() => {
        estado.filtro.termo = el.inputBuscaGlobal.value.trim();
        estado.filtro.pagina = 1;
        carregarListaOverview();
      }, 250);
    });

    // Filtros de Escopo do Mod (Overview)
    if (el.pillsOrigem) {
      el.pillsOrigem.forEach(pill => {
        pill.addEventListener("click", () => {
          estado.filtro.origem = pill.dataset.origem;
          estado.filtro.pagina = 1;
          sincronizarFiltrosUI();
          carregarListaOverview();
        });
      });
    }

    // Filtros de Status (Overview)
    if (el.pillsStatus) {
      el.pillsStatus.forEach(pill => {
        pill.addEventListener("click", () => {
          estado.filtro.status = pill.dataset.status;
          estado.filtro.pagina = 1;
          sincronizarFiltrosUI();
          carregarListaOverview();
        });
      });
    }

    // Filtros Especiais (Overview)
    if (el.pillsEspecial) {
      el.pillsEspecial.forEach(pill => {
        pill.addEventListener("click", () => {
          estado.filtro.especial = pill.dataset.especial;
          estado.filtro.pagina = 1;
          sincronizarFiltrosUI();
          carregarListaOverview();
        });
      });
    }

    // Limpar Busca
    if (el.btnLimparBuscaOverview) {
      el.btnLimparBuscaOverview.addEventListener("click", () => {
        el.inputBuscaGlobal.value = "";
        estado.filtro.termo = "";
        estado.filtro.pagina = 1;
        sincronizarFiltrosUI();
        carregarListaOverview();
      });
    }

    // Redefinir Todos os Filtros Compostos
    if (el.btnLimparFiltrosOverview) {
      el.btnLimparFiltrosOverview.addEventListener("click", () => {
        estado.filtro.origem = "todos";
        estado.filtro.status = "todos";
        estado.filtro.especial = "todos";
        estado.filtro.categoria = "";
        estado.filtro.arquivo = "";
        estado.filtro.termo = "";
        if (el.inputBuscaGlobal) el.inputBuscaGlobal.value = "";
        estado.filtro.pagina = 1;
        document.querySelectorAll(".item-categoria").forEach(c => c.classList.remove("selecionado"));
        sincronizarFiltrosUI();
        carregarListaOverview();
        mostrarToast("Filtros redefinidos. Exibindo todas as frases.", "↺");
      });
    }

    // Controles da Árvore
    el.btnExpandirArvore.addEventListener("click", () => {
      document.querySelectorAll(".no-arquivo").forEach(n => {
        n.classList.remove("recolhido");
        const icone = n.querySelector(".icone-pasta");
        if (icone) icone.textContent = "▼";
      });
      estado.arvore.forEach(no => estado.pastasAbertas.add(no.id_no));
    });

    el.btnRecolherArvore.addEventListener("click", () => {
      document.querySelectorAll(".no-arquivo").forEach(n => {
        n.classList.add("recolhido");
        const icone = n.querySelector(".icone-pasta");
        if (icone) icone.textContent = "▶";
      });
      estado.pastasAbertas.clear();
    });

    el.btnLimparFiltroArvore.addEventListener("click", () => {
      estado.filtro.arquivo = "";
      estado.filtro.categoria = "";
      document.querySelectorAll(".item-categoria").forEach(c => c.classList.remove("selecionado"));
      carregarListaOverview();
    });

    // Paginação Overview
    el.btnPaginaAnterior.addEventListener("click", () => {
      if (estado.filtro.pagina > 1) {
        estado.filtro.pagina--;
        carregarListaOverview();
      }
    });

    el.btnPaginaProxima.addEventListener("click", () => {
      if (estado.filtro.pagina < estado.filtro.totalPaginas) {
        estado.filtro.pagina++;
        carregarListaOverview();
      }
    });

    // Modais Profissionais (com foco e clique no backdrop)
    el.btnAbrirAtalhos.addEventListener("click", () => abrirModal(el.modalAtalhos, el.btnAbrirAtalhos));
    el.btnFecharModalAtalhos.addEventListener("click", () => fecharModal(el.modalAtalhos));
    el.btnOkModalAtalhos.addEventListener("click", () => fecharModal(el.modalAtalhos));

    el.btnAbrirCompilacao.addEventListener("click", () => abrirModal(el.modalCompilacao, el.btnAbrirCompilacao));
    el.btnFecharModalCompilacao.addEventListener("click", () => fecharModal(el.modalCompilacao));
    if (el.btnFecharModalCompilacaoRodape) {
      el.btnFecharModalCompilacaoRodape.addEventListener("click", () => fecharModal(el.modalCompilacao));
    }
    el.btnIniciarCompilacaoExec.addEventListener("click", executarCompilacaoMod);

    // Modal Glossário
    el.btnAbrirGlossario.addEventListener("click", () => {
      abrirModal(el.modalGlossario, el.btnAbrirGlossario);
      if (window.ModuloGlossario) {
        window.ModuloGlossario.carregarTermos();
      } else if (typeof ModuloGlossario !== "undefined") {
        ModuloGlossario.carregarTermos();
      }
    });
    el.btnFecharModalGlossario.addEventListener("click", () => fecharModal(el.modalGlossario));
    el.btnFecharModalGlossarioRodape.addEventListener("click", () => fecharModal(el.modalGlossario));
    el.formNovoTermoGlossario.addEventListener("submit", (e) => {
      e.preventDefault();
      if (window.ModuloGlossario) {
        window.ModuloGlossario.adicionarTermo(el.formNovoTermoGlossario);
      } else if (typeof ModuloGlossario !== "undefined") {
        ModuloGlossario.adicionarTermo(el.formNovoTermoGlossario);
      }
    });
    el.btnAuditarSinonimosGeral.addEventListener("click", async () => {
      mostrarToast("Auditando sinônimos no banco de dados...", "🔍");
      try {
        const res = await ApiCat.auditarInconsistencias();
        if (res.sucesso && res.auditoria) {
          mostrarToast(`Auditoria: ${res.auditoria.total_inconsistencias || 0} avisos encontrados.`, "ℹ️");
        }
      } catch (e) {
        mostrarToast(`Erro: ${e.message}`, "✕");
      }
    });

    // Modal Propagação
    el.btnFecharModalPropagacao.addEventListener("click", () => fecharModal(el.modalPropagacao));
    el.btnSalvarSomenteEste.addEventListener("click", () => confirmarPropagacao(false));
    el.btnConfirmarPropagarTodos.addEventListener("click", () => confirmarPropagacao(true));

    // Modal Gerenciador de Mod (Setup Mod-Agnostic)
    if (el.btnAbrirGerenciadorMod) {
      el.btnAbrirGerenciadorMod.addEventListener("click", () => {
        abrirModal(el.modalGerenciadorMod, el.btnAbrirGerenciadorMod);
        if (window.ModuloGerenciadorMod) {
          window.ModuloGerenciadorMod.trocarAba(window.ModuloGerenciadorMod.abaAtiva || "vanilla");
        }
      });
    }
    if (el.btnFecharModalGerenciador) {
      el.btnFecharModalGerenciador.addEventListener("click", () => fecharModal(el.modalGerenciadorMod));
    }
    if (el.btnFecharModalGerenciadorRodape) {
      el.btnFecharModalGerenciadorRodape.addEventListener("click", () => fecharModal(el.modalGerenciadorMod));
    }

    // Modal Relatório Inteligente & Gerador Nexus
    if (el.btnAbrirRelatorio) {
      el.btnAbrirRelatorio.addEventListener("click", () => abrirModalRelatorio("metricas"));
    }
    if (el.containerProgressoGeral) {
      el.containerProgressoGeral.addEventListener("click", () => abrirModalRelatorio("metricas"));
      el.containerProgressoGeral.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          abrirModalRelatorio("metricas");
        }
      });
    }
    if (el.btnFecharModalRelatorio) {
      el.btnFecharModalRelatorio.addEventListener("click", fecharModalRelatorio);
    }
    if (el.btnFecharModalRelatorioRodape) {
      el.btnFecharModalRelatorioRodape.addEventListener("click", fecharModalRelatorio);
    }
    if (el.btnAtualizarRelatorio) {
      el.btnAtualizarRelatorio.addEventListener("click", carregarDadosRelatorio);
    }

    // Abas do Relatório
    if (el.btnAbaRelatorioMetricas) {
      el.btnAbaRelatorioMetricas.addEventListener("click", () => alternarAbaRelatorio("metricas"));
    }
    if (el.btnAbaRelatorioFaltantes) {
      el.btnAbaRelatorioFaltantes.addEventListener("click", () => alternarAbaRelatorio("faltantes"));
    }
    if (el.btnAbaRelatorioNexus) {
      el.btnAbaRelatorioNexus.addEventListener("click", () => alternarAbaRelatorio("nexus"));
    }

    // Controles de Faltantes
    if (el.selectRelatorioFiltroEscopo) {
      el.selectRelatorioFiltroEscopo.addEventListener("change", (e) => {
        estadoRelatorio.filtrosFaltantes.escopo = e.target.value;
        carregarItensFaltantesRelatorio(1);
      });
    }
    if (el.selectRelatorioFiltroStatus) {
      el.selectRelatorioFiltroStatus.addEventListener("change", (e) => {
        estadoRelatorio.filtrosFaltantes.status = e.target.value;
        carregarItensFaltantesRelatorio(1);
      });
    }
    if (el.selectRelatorioFiltroArquivo) {
      el.selectRelatorioFiltroArquivo.addEventListener("change", (e) => {
        estadoRelatorio.filtrosFaltantes.arquivo = e.target.value;
        carregarItensFaltantesRelatorio(1);
      });
    }
    if (el.selectRelatorioFiltroCategoria) {
      el.selectRelatorioFiltroCategoria.addEventListener("change", (e) => {
        estadoRelatorio.filtrosFaltantes.categoria = e.target.value;
        carregarItensFaltantesRelatorio(1);
      });
    }
    if (el.inputRelatorioBuscaFaltantes) {
      el.inputRelatorioBuscaFaltantes.addEventListener("input", (e) => {
        clearTimeout(estadoRelatorio.timerDebounceFaltantes);
        estadoRelatorio.timerDebounceFaltantes = setTimeout(() => {
          estadoRelatorio.filtrosFaltantes.termo = e.target.value.trim();
          carregarItensFaltantesRelatorio(1);
        }, 250);
      });
    }
    if (el.btnLimparBuscaRelatorio) {
      el.btnLimparBuscaRelatorio.addEventListener("click", () => {
        el.inputRelatorioBuscaFaltantes.value = "";
        estadoRelatorio.filtrosFaltantes.termo = "";
        carregarItensFaltantesRelatorio(1);
      });
    }
    if (el.btnRelatorioLimparFiltros) {
      el.btnRelatorioLimparFiltros.addEventListener("click", () => {
        estadoRelatorio.filtrosFaltantes.escopo = "apenas_mod";
        estadoRelatorio.filtrosFaltantes.status = "pendentes";
        estadoRelatorio.filtrosFaltantes.arquivo = "";
        estadoRelatorio.filtrosFaltantes.categoria = "";
        estadoRelatorio.filtrosFaltantes.termo = "";
        if (el.selectRelatorioFiltroEscopo) el.selectRelatorioFiltroEscopo.value = "apenas_mod";
        if (el.selectRelatorioFiltroStatus) el.selectRelatorioFiltroStatus.value = "pendentes";
        if (el.selectRelatorioFiltroArquivo) el.selectRelatorioFiltroArquivo.value = "";
        if (el.selectRelatorioFiltroCategoria) el.selectRelatorioFiltroCategoria.value = "";
        if (el.inputRelatorioBuscaFaltantes) el.inputRelatorioBuscaFaltantes.value = "";
        carregarItensFaltantesRelatorio(1);
        mostrarToast("Filtros do relatório restaurados.", "↺");
      });
    }
    if (el.btnRelatorioAplicarModoFoco) {
      el.btnRelatorioAplicarModoFoco.addEventListener("click", aplicarFiltroFaltantesNoModoFoco);
    }
    if (el.btnRelatorioPagAnterior) {
      el.btnRelatorioPagAnterior.addEventListener("click", () => {
        if (estadoRelatorio.filtrosFaltantes.pagina > 1) {
          carregarItensFaltantesRelatorio(estadoRelatorio.filtrosFaltantes.pagina - 1);
        }
      });
    }
    if (el.btnRelatorioPagProxima) {
      el.btnRelatorioPagProxima.addEventListener("click", () => {
        if (estadoRelatorio.filtrosFaltantes.pagina < estadoRelatorio.filtrosFaltantes.totalPaginas) {
          carregarItensFaltantesRelatorio(estadoRelatorio.filtrosFaltantes.pagina + 1);
        }
      });
    }

    // Controles Nexus
    if (el.selectNexusModelo) {
      el.selectNexusModelo.addEventListener("change", atualizarGeradorNexus);
    }
    [el.selectNexusModelo, el.inputNexusNomeMod, el.inputNexusVersaoMod, el.inputNexusAutor].forEach(inp => {
      if (inp) inp.addEventListener("input", atualizarGeradorNexus);
    });
    [el.checkNexusBarras, el.checkNexusEscopo, el.checkNexusArquivos, el.checkNexusCastledb, el.checkNexusInstalacao, el.checkNexusFeedback].forEach(cb => {
      if (cb) cb.addEventListener("change", atualizarGeradorNexus);
    });
    if (el.btnCopiarNexusBbcode) {
      el.btnCopiarNexusBbcode.addEventListener("click", copiarBbcodeNexus);
    }
    if (el.btnCopiarBbcodeRapido) {
      el.btnCopiarBbcodeRapido.addEventListener("click", copiarBbcodeNexus);
    }
    if (el.btnSalvarNexusArquivo) {
      el.btnSalvarNexusArquivo.addEventListener("click", salvarArquivoNexus);
    }

    // Fechamento de Modais clicando no fundo escuro (Backdrop)
    [el.modalAtalhos, el.modalCompilacao, el.modalGlossario, el.modalPropagacao, el.modalGerenciadorMod, el.modalFiltrosAvancados, el.modalRelatorio, el.modalChavePool].forEach(modal => {
      if (modal) {
        modal.addEventListener("click", (e) => {
          if (e.target === modal) {
            fecharModal(modal);
          }
        });
      }
    });

    // Teclas de Atalho Globais
    document.addEventListener("keydown", lidarComAtalhosGlobais);
  }

  function lidarComAtalhosGlobais(e) {
    if (e.key === "Escape") {
      const modaisAbertos = document.querySelectorAll(".modal-overlay:not(.oculto)");
      if (modaisAbertos.length > 0) {
        fecharModal(modaisAbertos[modaisAbertos.length - 1]);
        return;
      }
      if (estado.modoAtual === "foco" && el.campoTraducaoHumana) {
        el.campoTraducaoHumana.focus();
      }
      return;
    }

    // Ctrl + Enter: Salvar e Avançar
    if (e.ctrlKey && e.key === "Enter") {
      e.preventDefault();
      salvarSegmentoAtual(true, true);
      return;
    }

    // Ctrl + S: Salvar mantendo página
    if (e.ctrlKey && (e.key === "s" || e.key === "S")) {
      e.preventDefault();
      salvarSegmentoAtual(false, false);
      return;
    }

    // Ctrl + G: Salto direto
    if (e.ctrlKey && (e.key === "g" || e.key === "G")) {
      e.preventDefault();
      el.inputSalto.focus();
      el.inputSalto.select();
      return;
    }

    // Ctrl + F: Busca Global
    if (e.ctrlKey && (e.key === "f" || e.key === "F")) {
      e.preventDefault();
      alternarModo("overview");
      el.inputBuscaGlobal.focus();
      el.inputBuscaGlobal.select();
      return;
    }

    // Alt + Teclas
    if (e.altKey) {
      if (e.key === "ArrowRight") {
        e.preventDefault();
        navegarDirecao("proximo");
      } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        navegarDirecao("anterior");
      } else if (e.key === "1") {
        e.preventDefault();
        if (estado.segmentoAtual) copiarTextoParaEditor(estado.segmentoAtual.vanilla_pt, "Oficial Shiro");
      } else if (e.key === "2") {
        e.preventDefault();
        if (estado.segmentoAtual) copiarTextoParaEditor(obterTextoIaAtual(), "IA Gemini");
      } else if (e.key === "3") {
        e.preventDefault();
        if (estado.segmentoAtual) copiarTextoParaEditor(estado.segmentoAtual.mod_en, "Mod EN");
      } else if (e.key === "t" || e.key === "T") {
        e.preventDefault();
        traduzirComIaAtual();
      } else if (e.key === "a" || e.key === "A") {
        e.preventDefault();
        salvarSegmentoAtual(true, true);
      } else if (e.key === "u" || e.key === "U") {
        e.preventDefault();
        desfazerAprovacaoAtual();
      } else if (e.key === "p" || e.key === "P") {
        e.preventDefault();
        if (estado.filtro.origem === "apenas_mod") {
          estado.filtro.status = estado.filtro.status === "pendentes" ? "todos" : "pendentes";
        } else {
          estado.filtro.origem = "apenas_mod";
          estado.filtro.status = "pendentes";
        }
        aplicarNovoFiltroFoco(true);
      } else if (e.key === "d" || e.key === "D") {
        e.preventDefault();
        estado.exibirDiff = !estado.exibirDiff;
        renderizarModEn();
        mostrarToast(`Realce de diferenças (Diff) ${estado.exibirDiff ? "ativado" : "desativado"}.`, "👁️");
      } else if (e.key === "z" || e.key === "Z") {
        e.preventDefault();
        el.campoTraducaoHumana.value = estado.textoOriginalCarregado;
        atualizarMetricasTexto();
        validarTagsTempoReal();
        mostrarToast("Texto restaurado!", "↺");
      } else if (e.key === "f" || e.key === "F") {
        e.preventDefault();
        alternarModo("foco");
      } else if (e.key === "o" || e.key === "O") {
        e.preventDefault();
        alternarModo("overview");
      } else if (e.key === "r" || e.key === "R") {
        e.preventDefault();
        abrirModalRelatorio();
      }
      return;
    }

    // Tecla '?' para Ajuda de Atalhos
    const tagAtiva = document.activeElement ? document.activeElement.tagName.toUpperCase() : "";
    if (e.key === "?" && !["INPUT", "TEXTAREA", "SELECT"].includes(tagAtiva) && !document.activeElement?.isContentEditable) {
      e.preventDefault();
      if (el.modalAtalhos.classList.contains("oculto")) {
        abrirModal(el.modalAtalhos, el.btnAbrirAtalhos);
      } else {
        fecharModal(el.modalAtalhos);
      }
    }
  }

  // ----------------------------------------------------------------------------
  // Inicialização do Aplicativo
  // ----------------------------------------------------------------------------
  async function inicializar() {
    registrarEventos();
    sincronizarFiltrosUI();
    await carregarEstatisticas();
    // Iniciar na primeira frase pendente do mod de forma dinâmica
    try {
      const segInicial = await ApiCat.obterPrimeiroSegmento(obterFiltrosAtivos());
      if (segInicial && segInicial.id) {
        await carregarSegmento(segInicial.id);
      } else {
        const segQualquer = await ApiCat.obterPrimeiroSegmento({});
        if (segQualquer && segQualquer.id) {
          await carregarSegmento(segQualquer.id);
        }
      }
    } catch (e) {
      console.warn("Aviso ao carregar frase inicial:", e);
      try {
        const resNav = await ApiCat.navegarSegmento(0, "proximo", obterFiltrosAtivos());
        if (resNav && resNav.id_segmento) {
          await carregarSegmento(resNav.id_segmento);
        }
      } catch (errNav) {
        console.error("Não foi possível carregar nenhum segmento:", errNav);
      }
    }
  }

  // Expor API para ModuloGlossario e ModuloGerenciadorMod
  window.AppCat = {
    carregarDados: async () => {
      await carregarEstatisticas();
      if (estado.idSegmentoAtual) {
        await carregarSegmento(estado.idSegmentoAtual);
      } else {
        const seg = await ApiCat.obterPrimeiroSegmento(obterFiltrosAtivos());
        if (seg && seg.id) await carregarSegmento(seg.id);
      }
      if (estado.modoAtual === "overview") carregarListaOverview();
    },
    mostrarToast: (mensagem, icone, duracao) => {
      mostrarToast(mensagem, icone, duracao);
    },
    abrirModal: (modal, elementoDisparador) => {
      abrirModal(modal, elementoDisparador);
    },
    fecharModal: (modal) => {
      fecharModal(modal);
    }
  };

  document.addEventListener("DOMContentLoaded", inicializar);
})();
