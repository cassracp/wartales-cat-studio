"""
Módulo de auto-propagação atômica de traduções repetidas.
Permite atualizar todas as ocorrências de uma mesma frase em todo o jogo de uma só vez.
"""

from typing import Any, Dict, List
from nucleo.banco_dados import GerenciadorBancoDados
from nucleo.normalizador import gerar_hash_conteudo


class ServicoAutoPropagacao:
    """Motor de propagação de traduções em repetições exatas."""

    def __init__(self, gerenciador_banco: GerenciadorBancoDados):
        self.banco = gerenciador_banco

    def obter_estatisticas_repeticao(self, texto_origem_en: str, segmento_id_atual: int) -> Dict[str, Any]:
        """
        Retorna informações sobre repetições do segmento atual no banco de dados.
        """
        hash_conteudo = gerar_hash_conteudo(texto_origem_en)
        repeticoes = self.banco.obter_repeticoes(hash_conteudo, excluir_id=segmento_id_atual)

        return {
            "hash_conteudo": hash_conteudo,
            "total_repeticoes": len(repeticoes),
            "itens_repetidos": repeticoes
        }

    def executar_propagacao(
        self,
        hash_conteudo: str,
        nova_traducao: str,
        status: str = "revisado"
    ) -> Dict[str, Any]:
        """
        Aplica a tradução atômica em todas as linhas que compartilham o mesmo hash de conteúdo.
        """
        total_afetados = self.banco.propagar_traducao_por_hash(
            hash_conteudo=hash_conteudo,
            nova_traducao=nova_traducao,
            status=status
        )

        return {
            "sucesso": True,
            "hash_conteudo": hash_conteudo,
            "total_propagados": total_afetados
        }
