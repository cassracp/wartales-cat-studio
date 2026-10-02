/**
 * Controlador de Glossário / Termbase e Auditoria de Sinônimos Proibidos.
 */
const ModuloGlossario = {
  listaTermos: [],
  termoFiltro: "",

  async carregarTermos() {
    try {
      this.listaTermos = await ApiCat.listarGlossario();
      this.renderizarTabelaGlossario();
      this.inicializarFiltro();
    } catch (erro) {
      console.error("Erro ao carregar glossário:", erro);
    }
  },

  inicializarFiltro() {
    const inputFiltro = document.getElementById("input-filtro-glossario");
    if (inputFiltro && !inputFiltro.dataset.ouvindo) {
      inputFiltro.dataset.ouvindo = "true";
      inputFiltro.addEventListener("input", (e) => {
        this.termoFiltro = (e.target.value || "").toLowerCase().trim();
        this.renderizarTabelaGlossario();
      });
    }
  },

  escaparHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  },

  notificar(mensagem, icone = "ℹ️") {
    if (window.AppCat && window.AppCat.mostrarToast) {
      window.AppCat.mostrarToast(mensagem, icone);
    } else {
      console.log(mensagem);
    }
  },

  renderizarTabelaGlossario() {
    const container = document.getElementById("corpoTabelaGlossario");
    if (!container) return;

    let termosExibir = this.listaTermos;
    if (this.termoFiltro) {
      termosExibir = this.listaTermos.filter(item => {
        const en = (item.termo_en || "").toLowerCase();
        const pt = (item.termo_pt_padrao || "").toLowerCase();
        const sin = (item.sinonimos_proibidos || "").toLowerCase();
        const cat = (item.categoria || "").toLowerCase();
        return en.includes(this.termoFiltro) || pt.includes(this.termoFiltro) || sin.includes(this.termoFiltro) || cat.includes(this.termoFiltro);
      });
    }

    if (termosExibir.length === 0) {
      const msg = this.termoFiltro ? "Nenhum termo corresponde ao filtro atual." : "Nenhum termo cadastrado no momento.";
      container.innerHTML = `<tr><td colspan="5" class="tabela-glossario-vazia">${msg}</td></tr>`;
      return;
    }

    container.innerHTML = termosExibir.map(item => `
      <tr>
        <td class="termo-en-col">${this.escaparHtml(item.termo_en)}</td>
        <td class="termo-pt-col">${this.escaparHtml(item.termo_pt_padrao)}</td>
        <td class="termo-sinonimos-col">${this.escaparHtml(item.sinonimos_proibidos || "-")}</td>
        <td><span class="badge-tag">${this.escaparHtml(item.categoria || "Geral")}</span></td>
        <td class="termo-acoes-col">
          <button 
            class="btn btn-secundario btn-compacto" 
            onclick="ModuloGlossario.aplicarSubstituicaoLotePorId(${item.id})"
            title="Substituir sinônimos proibidos no jogo inteiro"
          >
            Substituir em Lote
          </button>
          <button 
            class="btn btn-perigo btn-compacto" 
            onclick="ModuloGlossario.excluirTermo(${item.id})"
            title="Excluir termo do glossário"
            aria-label="Excluir termo ${this.escaparHtml(item.termo_en)}"
          >
            ✕
          </button>
        </td>
      </tr>
    `).join("");
  },

  async aplicarSubstituicaoLotePorId(id) {
    const item = this.listaTermos.find(t => t.id === id);
    if (!item) return;
    return this.aplicarSubstituicaoLote(item.sinonimos_proibidos, item.termo_pt_padrao);
  },

  async adicionarTermo(form) {
    const termo_en = (form.termo_en?.value || "").trim();
    const termo_pt_padrao = (form.termo_pt_padrao?.value || "").trim();
    const sinonimos_proibidos = (form.sinonimos_proibidos?.value || "").trim();
    const categoria = (form.categoria?.value || "").trim() || "Geral";
    const notas = (form.notas?.value || "").trim();

    if (!termo_en || !termo_pt_padrao) {
      this.notificar("Termo em Inglês e Tradução Padrão em Português são obrigatórios!", "⚠️");
      return;
    }

    try {
      await ApiCat.salvarTermoGlossario({
        termo_en,
        termo_pt_padrao,
        sinonimos_proibidos,
        categoria,
        notas
      });
      form.reset();
      await this.carregarTermos();
      this.notificar("Termo cadastrado com sucesso no Glossário!", "✓");
      // Notifica o app para re-auditar se desejado
      if (window.AppCat && window.AppCat.carregarDados) {
        window.AppCat.carregarDados();
      }
    } catch (erro) {
      this.notificar("Erro ao salvar termo: " + erro.message, "✕");
    }
  },

  async excluirTermo(id) {
    if (!confirm("Deseja realmente remover este termo do glossário?")) return;
    try {
      await ApiCat.removerTermoGlossario(id);
      await this.carregarTermos();
      this.notificar("Termo removido do glossário.", "✓");
      if (window.AppCat && window.AppCat.carregarDados) {
        window.AppCat.carregarDados();
      }
    } catch (erro) {
      this.notificar("Erro ao excluir termo: " + erro.message, "✕");
    }
  },

  async aplicarSubstituicaoLote(sinonimosStr, termoPadrao) {
    if (!sinonimosStr || sinonimosStr === "-") {
      this.notificar("Este termo não possui sinônimos proibidos cadastrados.", "ℹ️");
      return;
    }

    const sinonimos = sinonimosStr.split(",").map(s => s.trim()).filter(Boolean);
    if (sinonimos.length === 0) return;

    const confirmacao = confirm(
      `Deseja varrer todas as traduções e substituir os seguintes sinônimos: [${sinonimos.join(", ")}] pelo termo oficial '${termoPadrao}'?\n\n(Nota: O status de revisão de cada frase será rigorosamente mantido; itens pendentes continuarão pendentes para sua revisão final).`
    );
    if (!confirmacao) return;

    let totalSubstituidos = 0;
    try {
      for (const sin of sinonimos) {
        const res = await ApiCat.substituirSinonimoLote(sin, termoPadrao);
        totalSubstituidos += res.total_substituidos;
      }
      this.notificar(`Padronização concluída! Total de ${totalSubstituidos} ocorrências corrigidas (status preservados).`, "✓");
      if (window.AppCat && window.AppCat.carregarDados) {
        window.AppCat.carregarDados();
      }
    } catch (erro) {
      this.notificar("Erro durante substituição em lote: " + erro.message, "✕");
    }
  }
};

// Exportar explicitamente para o escopo global de window
window.ModuloGlossario = ModuloGlossario;

// Auto-carregar termos imediatamente no carregamento da página
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => {
    ModuloGlossario.carregarTermos();
  });
} else {
  ModuloGlossario.carregarTermos();
}
