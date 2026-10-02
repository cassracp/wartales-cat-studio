# ⚔️ Wartales CAT Studio - Estúdio Profissional de Tradução Offline

O **Wartales CAT Studio** é uma ferramenta profissional de tradução assistida por computador (*Computer-Assisted Translation* - CAT Tool), 100% autônoma, local e offline, projetada especialmente para localização contínua, revisão terminológica e geração de pacotes modulares de tradução para **Wartales** e seus mods (como o *Wartales Remastered*).

---

## 🎯 Por que o Wartales CAT Studio foi Criado?

Traduções automáticas via IA geram uma base inicial rápida, porém introduzem inconsistências graves:
- **Inconsistência Terminológica e Sinônimos Excessivos:** A mesma mecânica ou atributo é traduzido ora como *"Vontade"*, ora como *"Determinação"*, ora como *"Bravura"*.
- **Crashes e Asserts no CastleDB:** Strings com tags `<br/>` no início ou variáveis corrompidas (`::name::`, `[DMG]`) quebram o motor da Shiro Games (Heaps.io) em tempo de execução.
- **Falta de Contexto Comparativo:** Para traduzir um mod com precisão, o tradutor necessita de um **cenário comparativo de 4 vias**.

---

## 🚀 Funcionalidades Principais

### 1. Grade Comparativa de 4 Colunas Lado a Lado
1. **Coluna 1 (Jogo Base Oficial):** Texto original em inglês (*Vanilla EN*) e a tradução oficial da Shiro Games (*Vanilla PT*) para referência de estilo.
2. **Coluna 2 (Mod Remastered EN):** O texto original modificado ou introduzido pelo mod.
3. **Coluna 3 (Tradução Vigente):** O texto atualmente em uso no mod gerado pela IA ou versão anterior.
4. **Coluna 4 (Editor do Usuário):** Campo de edição focado com atalhos de teclado (`Enter` para salvar e avançar para o próximo, `Ctrl+Enter` para propagar).

### 2. Banco de Dados SQLite Local com Índice FTS5
- Indexação de mais de 30.000 nós de texto.
- Busca instantânea por qualquer palavra em inglês, português ou chave hierárquica em **menos de 10 milissegundos**.
- Modo WAL (*Write-Ahead Logging*) ativado para máxima velocidade e concorrência sem bloqueios de arquivo.

### 3. Auto-Propagação Atômica de Repetições
- Ao traduzir ou ajustar uma frase (ex.: alterando de *"O Bando descansou"* para *"A Tropa descansou"*), o sistema detecta se aquela frase existe em múltiplos nós em todo o jogo e oferece a opção de **propagar a tradução para todas as repetições com 1 clique**.

### 4. Termbase & Auditoria de Sinônimos em Tempo Real
- Cadastro de termos oficiais com definição de **sinônimos proibidos** (ex.: *Troop ➔ Tropa* [Proibidos: Bando, Grupo]; *Willpower ➔ Bravura* [Proibidos: Vontade, Determinação]; *Crowns ➔ Koroas* [Proibidos: Coroas, Moedas]).
- Botão de **Substituição de Sinônimos em Lote**: varre o jogo inteiro e padroniza os termos respeitando capitalização.

### 5. Garantia de Qualidade (QA) Integrada e CastleDB Safe
- Verificação automática de tags e variáveis protegidas (`::target::`, `[DMG]`, `<b>`, `<good>`).
- Higienização preventiva contra o erro de `assert` do CastleDB em `cdb.Lang` / `Trails.hx` (remove tags `<br/>` em início de nós folha).

### 6. Empacotador Oficial Heaps.io (.PAK) e Exportador Nexus Mods
- Um clique em **"Compilar res2.pak"** executa o pipeline completo:
  - Compila `export_pt-BR.xml` e `texts_pt-BR.xml`.
  - Empacota o arquivo modular `res2.pak` obedecendo à risca à assinatura `PAK\0`, cabeçalho global de 18 bytes, cálculo de CRC32 e marcador ASCII `DATA`.
  - Gera o arquivo `.zip` pronto com o `LEIAME_INSTALACAO.txt` para publicação no **Nexus Mods**.
  - Opcionalmente atualiza a pasta do jogo na Steam com um único clique.

---

## 🏗️ Arquitetura de Software e Estrutura de Pastas

O projeto adota padrões consolidados de engenharia de software (*Clean Architecture*, padrão *Repository*, *Separation of Concerns*):

```text
wartales-cat-studio/
├── .gitignore                      # Arquivo completo para repositório limpo
├── README.md                       # Documentação técnica e operacional
├── configuracao.json               # Configurações do servidor, portas e caminhos
├── requisitos.txt                  # Requisitos de execução (zero dependências obrigatórias)
├── Iniciar_Estudio_CAT.bat         # Inicializador Desktop em 1 clique (Edge App Mode)
├── Iniciar_Estudio_CAT.ps1         # Inicializador nativo PowerShell
├── Migrar_Para_D.bat               # Script para migração para D:\Projetos\wartales-cat-studio
├── Migrar_Para_D.ps1               # Script PowerShell de migração
├── executar_testes.py              # Executor da suíte de testes unitários
├── nucleo/                         # Camada de Serviços e Lógica de Negócio
│   ├── banco_dados.py              # Repositório SQLite + FTS5 + Triggers + WAL
│   ├── normalizador.py             # Normalização de espaços, tokens e sanitização CastleDB
│   ├── servico_qa.py               # Auditoria de tags, variáveis e integridade
│   ├── servico_glossario.py        # Gestão de Termbase e substituição em lote
│   ├── servico_propagacao.py       # Propagação atômica por hash de conteúdo
│   ├── empacotador_pak.py          # Empacotador de alta precisão Heaps.io (.PAK)
│   └── sincronizador.py            # Parser e importador de XMLs Vanilla e Mod
├── exportadores/                   # Camada de Saída e Compilação
│   ├── compilador_xml.py           # Compilador de export_pt-BR.xml e texts_pt-BR.xml
│   └── gerador_distribuicao.py     # Gerador de res2.pak e ZIP para Nexus Mods
├── servidor/                       # Camada de Transporte / API
│   └── servidor_api.py             # Servidor REST HTTP nativo em Python
├── interface/                      # Camada de Apresentação (SPA WCAG 2.1 AA)
│   ├── index.html                  # Interface semântica em HTML5
│   ├── css/
│   │   ├── tema.css                # Paleta tema escuro Wartales (contraste >= 4.5:1)
│   │   └── grade.css               # Estilos da grade 4 vias, editores e modais
│   └── js/
│       ├── api.js                  # Cliente REST para a API local
│       ├── grade.js                # Renderizador da grade e tags destacadas
│       ├── glossario.js            # Painel do glossário e sinônimos
│       └── app.js                  # Controlador da aplicação e atalhos
├── dados/                          # Armazenamento e Referência
│   ├── referencia_vanilla/         # XMLs oficiais do jogo base (Shiro Games)
│   ├── mod_atual/                  # XMLs do mod em tradução
│   └── banco/
│       └── wartales_cat.db         # Banco SQLite persistente com FTS5
├── saida/                          # Artefatos Gerados
│   ├── compilados/                 # export_pt-BR.xml e texts_pt-BR.xml gerados
│   └── distribuicao_nexus/         # res2.pak e arquivo ZIP final
├── scripts/                        # Ferramentas auxiliares
│   └── importar_dados_iniciais.py  # Script de carga inicial de dados
└── testes/                         # Suíte de Testes Automatizados
    ├── test_normalizador.py        # Testes de sanitização CastleDB e tokens
    ├── test_banco_dados.py         # Testes de persistência, FTS5 e propagação
    ├── test_servico_qa.py          # Testes de auditoria e conformidade de tags
    └── test_empacotador_pak.py     # Testes de conformidade binária Heaps.io (.PAK)
```

---

## 💻 Como Executar

### Pré-requisitos
- Windows 10 ou 11
- Python 3.10 ou superior instalado no PATH
- Microsoft Edge ou qualquer navegador moderno

### Executando o CAT Studio em Modo Desktop:
Basta dar um duplo clique no arquivo:
👉 **`Iniciar_Estudio_CAT.bat`**

O inicializador irá:
1. Subir o servidor local em segundo plano na porta 5000.
2. Abrir automaticamente a janela do aplicativo desacoplada da barra de navegação (Edge App Mode), proporcionando uma experiência de aplicativo desktop nativo.

---

## 🚚 Migração para `D:\Projetos\wartales-cat-studio`

Se você deseja mover este projeto para o caminho definitivo `D:\Projetos\wartales-cat-studio`:
1. Execute o script **`Migrar_Para_D.bat`** (ou `Migrar_Para_D.ps1`).
2. O script copiará toda a estrutura do projeto com integridade preservada utilizando o utilitário nativo `robocopy`.

---

## 🧪 Testes Automatizados

Para executar todos os testes da aplicação:
```bash
python executar_testes.py
```
Todos os módulos (normalizador, banco de dados FTS5, validador de QA e empacotador de .PAK) possuem cobertura de testes automatizados com 100% de aprovação.

---

## ♿ Acessibilidade Digital (WCAG 2.1 AA)

- **Contraste de Cores:** Todos os textos possuem taxa de contraste estrita superior a **7:1** para texto normal e **4.5:1** para textos auxiliares.
- **Navegabilidade por Teclado:** Acesso total via teclado (`Tab`, `Shift+Tab`, `Enter`, `Ctrl+Enter`, `Ctrl+F`, `Escape`) com indicador de foco visível nítido (`focus-visible`).
- **Independência de Cores:** Estados de erro, aviso e sucesso são sempre acompanhados de ícones e rótulos textuais explícitos.
