"""
Módulo de gestão de termos terminológicos (Termbase) e auditoria de sinônimos.
"""

import re
from typing import Any, Dict, List
from nucleo.banco_dados import GerenciadorBancoDados
from nucleo.servico_qa import ServicoGarantiaQualidade


TERMOS_INICIAIS_PADRAO = [
    {
        "termo_en": "Troop",
        "termo_pt_padrao": "Tropa",
        "sinonimos_proibidos": "Bando, Grupo, Companhia",
        "categoria": "Mecânica",
        "notas": "Termo oficial da Shiro Games para o grupo de mercenários do jogador."
    },
    {
        "termo_en": "Willpower",
        "termo_pt_padrao": "Bravura",
        "sinonimos_proibidos": "Vontade, Determinação",
        "categoria": "Atributo",
        "notas": "Atributo principal de sobrevivência e bônus de pontos de bravura."
    },
    {
        "termo_en": "Crowns",
        "termo_pt_padrao": "Koroas",
        "sinonimos_proibidos": "Coroas, Moedas, Ouro",
        "categoria": "Economia",
        "notas": "Moeda oficial do jogo (escrita com K no PT-BR oficial)."
    },
    {
        "termo_en": "Influence",
        "termo_pt_padrao": "Influência",
        "sinonimos_proibidos": "Prestígio, Poder",
        "categoria": "Economia",
        "notas": "Recurso político para negociações e recrutamento."
    },
    {
        "termo_en": "Knowledge",
        "termo_pt_padrao": "Conhecimento",
        "sinonimos_proibidos": "Sabedoria, Saber",
        "categoria": "Progresso",
        "notas": "Pontos usados para desbloquear tecnologias no Compêndio."
    },
    {
        "termo_en": "Valor Points",
        "termo_pt_padrao": "Pontos de Bravura",
        "sinonimos_proibidos": "Pontos de Valor, Pontos de Coragem",
        "categoria": "Combate",
        "notas": "Recurso em combate para ativação de habilidades especiais."
    },
    {
        "termo_en": "Rest",
        "termo_pt_padrao": "Descanso",
        "sinonimos_proibidos": "Repouso, Descansar",
        "categoria": "Acampamento",
        "notas": "Ação de descanso no acampamento para recuperar fadiga."
    }
]


class ServicoGlossario:
    """Serviço de auditoria e aplicação de glossário/sinônimos."""

    def __init__(self, gerenciador_banco: GerenciadorBancoDados):
        self.banco = gerenciador_banco

    def inicializar_glossario_padrao(self) -> int:
        """Popula o glossário com a base padrão de Wartales caso esteja vazio."""
        termos_atuais = self.banco.listar_glossario()
        if not termos_atuais:
            inseridos = 0
            for item in TERMOS_INICIAIS_PADRAO:
                self.banco.salvar_termo_glossario(
                    termo_en=item["termo_en"],
                    termo_pt_padrao=item["termo_pt_padrao"],
                    sinonimos_proibidos=item["sinonimos_proibidos"],
                    categoria=item["categoria"],
                    notas=item["notas"]
                )
                inseridos += 1
            return inseridos
        return 0

    def auditar_todo_o_banco(self) -> Dict[str, Any]:
        """
        Varre todos os segmentos do banco de dados, avalia QA e consistência
        com o glossário atual e atualiza as flags de inconsistência.
        """
        glossario = self.banco.listar_glossario()
        total_inconsistencias = 0

        with self.banco.obter_conexao() as conexao:
            cursor = conexao.cursor()
            cursor.execute("SELECT id, mod_en, traducao_atual, traducao_revisada FROM segmentos")
            todos_segmentos = cursor.fetchall()

            for segmento in todos_segmentos:
                seg_id = segmento["id"]
                mod_en = segmento["mod_en"]
                traducao = segmento["traducao_revisada"] or segmento["traducao_atual"]

                resultado_qa = ServicoGarantiaQualidade.validar_segmento(mod_en, traducao, glossario)
                tem_inconsistencia = 1 if resultado_qa["tem_inconsistencia"] else 0
                avisos_texto = "\n".join(resultado_qa["avisos"])

                if tem_inconsistencia:
                    total_inconsistencias += 1

                cursor.execute("""
                    UPDATE segmentos SET
                        tem_inconsistencia = ?,
                        aviso_qa = ?
                    WHERE id = ?
                """, (tem_inconsistencia, avisos_texto, seg_id))

            conexao.commit()

        return {
            "total_auditados": len(todos_segmentos),
            "total_inconsistencias": total_inconsistencias
        }

    def substituir_sinonimo_em_lote(
        self,
        sinonimo_proibido: str,
        termo_padrao: str,
        apenas_pendentes: bool = False
    ) -> int:
        """
        Substitui em lote ocorrências de um sinônimo proibido pelo termo padronizado.
        Diferencia maiúsculas de minúsculas e aplica o termo exatamente como cadastrado.
        """
        sinonimo_limpo = sinonimo_proibido.strip()
        termo_limpo = termo_padrao.strip()

        if not sinonimo_limpo or not termo_limpo:
            return 0

        # Case-sensitive: "The Troop" e "the troop" são entradas distintas do glossário.
        padrao_re = re.compile(rf"(?<!\w){re.escape(sinonimo_limpo)}(?!\w)")

        def substituir_com_caixa(match: re.Match) -> str:
            return termo_limpo
        modificados = 0
        glossario = self.banco.listar_glossario()

        with self.banco.obter_conexao() as conexao:
            cursor = conexao.cursor()
            query = "SELECT id, mod_en, status, traducao_atual, traducao_revisada FROM segmentos"
            if apenas_pendentes:
                query += " WHERE status = 'pendente'"

            cursor.execute(query)
            linhas = cursor.fetchall()

            for linha in linhas:
                seg_id = linha["id"]
                texto_alvo = linha["traducao_revisada"] or linha["traducao_atual"]

                if padrao_re.search(texto_alvo):
                    novo_texto = padrao_re.sub(substituir_com_caixa, texto_alvo)

                    # Reavalia garantia de qualidade no segmento com o novo texto
                    resultado_qa = ServicoGarantiaQualidade.validar_segmento(linha["mod_en"], novo_texto, glossario)
                    tem_inconsistencia = 1 if resultado_qa["tem_inconsistencia"] else 0
                    aviso_qa = "\n".join(resultado_qa["avisos"])

                    # O status existente ('pendente', 'revisado', etc.) é rigorosamente PRESERVADO
                    cursor.execute("""
                        UPDATE segmentos SET
                            traducao_revisada = ?,
                            tem_inconsistencia = ?,
                            aviso_qa = ?,
                            data_atualizacao = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (novo_texto, tem_inconsistencia, aviso_qa, seg_id))
                    modificados += 1

            conexao.commit()

        return modificados
