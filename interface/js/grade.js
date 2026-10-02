/**
 * Renderizador da Grade Comparativa de 4 Colunas e Editor de Revisão.
 */
const RenderizadorGrade = {
  containerId: "containerGrade",

  escaparHtml(str) {
    if (!str) return "";
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  },

  destacarTokens(texto) {
    if (!texto) return "";
    let seguro = this.escaparHtml(texto);

    // Destaque de variáveis ::nome::
    seguro = seguro.replace(/(::[a-zA-Z0-9_\-]+::)/g, '<span class="token-protegido">$1</span>');
    // Destaque de tokens [DMG], [KOROAS]
    seguro = seguro.replace(/(\[[A-Za-z0-9_\-]+\])/g, '<span class="token-protegido">$1</span>');
    // Destaque de tags XML/HTML simuladas &lt;b&gt;, etc.
    seguro = seguro.replace(/(&lt;\/?[a-zA-Z0-9_\-]+(?:\s+[^&]*)?&gt;)/g, '<span class="tag-html-destaque">$1</span>');

    return seguro;
  },

  renderizarSegmentos(segmentos, onSalvar, onAbrirPropagacao) {
    const container = document.getElementById(this.containerId);
    if (!container) return;

    if (!segmentos || segmentos.length === 0) {
      container.innerHTML = `
        <div style="text-align: center; padding: 60px 20px; color: var(--cor-texto-esmaecido);">
          <h3>Nenhum segmento encontrado para os filtros atuais.</h3>
          <p>Tente ajustar a busca ou limpar os filtros na barra superior.</p>
        </div>
      `;
      return;
    }

    container.innerHTML = segmentos.map(seg => {
      const revisado = seg.status === "revisado";
      const temInconsistencia = seg.tem_inconsistencia === 1;
      const classeStatus = revisado ? "revisado" : (temInconsistencia ? "tem-inconsistencia" : "");
      const traducaoAtiva = seg.traducao_revisada || seg.traducao_atual || "";

      return `
        <article class="cartao-segmento ${classeStatus}" id="cartao-${seg.id}" data-id="${seg.id}">
          <div class="cartao-meta">
            <div class="meta-esquerda">
              <span class="tag-arquivo">${this.escaparHtml(seg.arquivo)}</span>
              <span class="tag-chave">${this.escaparHtml(seg.chave_hierarquica)}</span>
              ${revisado ? '<span style="color: var(--cor-sucesso); font-weight: bold;">✓ Revisado</span>' : ''}
            </div>
            <div>
              <button 
                class="badge-repeticao" 
                title="Ver repetições deste texto em outros nós" 
                onclick="window.AppCat.verificarRepeticoes(${seg.id})"
                aria-label="Verificar repetições do segmento ${seg.id}"
              >
                ⟲ Checar Repetições
              </button>
            </div>
          </div>

          <div class="grid-quatro-vias">
            <!-- Coluna 1: Vanilla Oficial (EN e PT) -->
            <div class="coluna-quadro">
              <div>
                <div class="rotulo-subsecao">1. Vanilla EN (Oficial)</div>
                <div class="conteudo-texto vanilla-en">${this.destacarTokens(seg.vanilla_en || "(Sem correspondência direta)")}</div>
                <div class="rotulo-subsecao">1. Vanilla PT (Shiro Games)</div>
                <div class="conteudo-texto">${this.destacarTokens(seg.vanilla_pt || "(Não traduzido oficialmente)")}</div>
              </div>
            </div>

            <!-- Coluna 2: Mod Remastered EN -->
            <div class="coluna-quadro">
              <div class="rotulo-subsecao">2. Mod EN (Remastered)</div>
              <div class="conteudo-texto">${this.destacarTokens(seg.mod_en)}</div>
            </div>

            <!-- Coluna 3: Tradução Atual / IA -->
            <div class="coluna-quadro">
              <div class="rotulo-subsecao">3. Tradução Vigente</div>
              <div class="conteudo-texto">${this.destacarTokens(seg.traducao_atual)}</div>
            </div>

            <!-- Coluna 4: Editor do Usuário -->
            <div class="coluna-quadro">
              <div class="rotulo-subsecao">4. Tradução Revisada (Sua Edição)</div>
              <textarea 
                class="area-edicao-usuario" 
                id="editor-${seg.id}" 
                rows="2"
                aria-label="Editar tradução para ${this.escaparHtml(seg.chave_hierarquica)}"
              >${this.escaparHtml(traducaoAtiva)}</textarea>
              
              <div class="barra-acoes-editor">
                <span class="atalho-dica">Enter: Salvar | Ctrl+Enter: Propagar</span>
                <button 
                  class="botao-salvar-segmento" 
                  onclick="window.AppCat.salvarSegmentoRapido(${seg.id})"
                  aria-label="Salvar tradução do segmento ${seg.id}"
                >
                  Salvar
                </button>
              </div>
            </div>
          </div>

          ${temInconsistencia && seg.aviso_qa ? `
            <div class="caixa-alerta-qa" role="alert">
              <span>⚠️</span>
              <div>${this.escaparHtml(seg.aviso_qa).replace(/\n/g, "<br/>")}</div>
            </div>
          ` : ''}
        </article>
      `;
    }).join("");

    // Adiciona atalhos de teclado aos editores
    segmentos.forEach(seg => {
      const editor = document.getElementById(`editor-${seg.id}`);
      if (!editor) return;

      editor.addEventListener("keydown", (e) => {
        if (e.ctrlKey && e.key === "Enter") {
          e.preventDefault();
          window.AppCat.salvarEPropagarSegmento(seg.id);
        } else if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();
          window.AppCat.salvarSegmentoRapido(seg.id, true);
        }
      });
    });
  }
};
