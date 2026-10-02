"""
Testes unitários para o módulo de banco de dados SQLite com FTS5.
"""

import os
import tempfile
import unittest
from nucleo.banco_dados import GerenciadorBancoDados


class TesteBancoDados(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.caminho_banco = os.path.join(self.temp_dir.name, "teste_cat.db")
        self.banco = GerenciadorBancoDados(self.caminho_banco)

    def tearDown(self):
        self.temp_dir.cleanup()

    def teste_inserir_e_obter_segmento(self):
        seg_id = self.banco.salvar_segmento(
            arquivo="export_pt-BR.xml",
            tag_nome="name",
            chave_hierarquica="items.iron_sword.name",
            caminho_xml="items/iron_sword/name",
            vanilla_en="Iron Sword",
            vanilla_pt="Espada de Ferro",
            mod_en="Refined Iron Sword",
            traducao_atual="Espada de Ferro Refinada",
            status="pendente"
        )
        self.assertGreater(seg_id, 0)

        dados = self.banco.obter_segmento_por_id(seg_id)
        self.assertIsNotNone(dados)
        if dados is None:
            self.fail(f"Segmento {seg_id} não encontrado após inserção")
        self.assertEqual(dados["mod_en"], "Refined Iron Sword")
        self.assertEqual(dados["status"], "pendente")

        # Testar obter_primeiro_segmento_id
        primeiro_id = self.banco.obter_primeiro_segmento_id(filtro_status="pendente")
        self.assertEqual(primeiro_id, seg_id)

    def teste_busca_fts5(self):
        self.banco.salvar_segmento(
            arquivo="texts_pt-BR.xml",
            tag_nome="t",
            chave_hierarquica="dialogo.marheim.1",
            caminho_xml="dialogo.marheim.1",
            vanilla_en="Welcome to Marheim",
            vanilla_pt="Bem-vindo a Marheim",
            mod_en="Welcome to the ancient town of Marheim",
            traducao_atual="Bem-vindo à antiga cidade de Marheim"
        )

        self.banco.salvar_segmento(
            arquivo="texts_pt-BR.xml",
            tag_nome="t",
            chave_hierarquica="dialogo.stromkapp.1",
            caminho_xml="dialogo.stromkapp.1",
            vanilla_en="Stromkapp is quiet",
            vanilla_pt="Stromkapp está tranquila",
            mod_en="Stromkapp is very dangerous now",
            traducao_atual="Stromkapp está muito perigosa agora"
        )

        # Busca por termo parcial FTS5
        resultado = self.banco.buscar_segmentos(termo_busca="Marheim")
        self.assertEqual(resultado["total_itens"], 1)
        self.assertEqual(resultado["itens"][0]["chave_hierarquica"], "dialogo.marheim.1")

        resultado2 = self.banco.buscar_segmentos(termo_busca="perigosa")
        self.assertEqual(resultado2["total_itens"], 1)
        self.assertEqual(resultado2["itens"][0]["chave_hierarquica"], "dialogo.stromkapp.1")

        # Busca com aspas e pontuações (proteção contra quebra no parser FTS5)
        resultado_aspas = self.banco.buscar_segmentos(termo_busca='"Marheim"')
        self.assertEqual(resultado_aspas["total_itens"], 1)

        resultado_aspa_solta = self.banco.buscar_segmentos(termo_busca='"')
        self.assertEqual(resultado_aspa_solta["total_itens"], 2)

        resultado_sufixo_aspa = self.banco.buscar_segmentos(termo_busca='perigosa"')
        self.assertEqual(resultado_sufixo_aspa["total_itens"], 1)

    def teste_propagar_repeticoes(self):
        # Inserir duas frases idênticas em nós diferentes
        id1 = self.banco.salvar_segmento(
            arquivo="export_pt-BR.xml",
            tag_nome="name",
            chave_hierarquica="loc1",
            caminho_xml="loc1",
            vanilla_en="Rest in camp",
            vanilla_pt="Descansar no acampamento",
            mod_en="Rest in camp",
            traducao_atual="Repouso no acampamento"
        )
        id2 = self.banco.salvar_segmento(
            arquivo="texts_pt-BR.xml",
            tag_nome="t",
            chave_hierarquica="loc2",
            caminho_xml="loc2",
            vanilla_en="Rest in camp",
            vanilla_pt="Descansar no acampamento",
            mod_en="Rest in camp",
            traducao_atual="Repouso no acampamento"
        )

        seg1 = self.banco.obter_segmento_por_id(id1)
        if seg1 is None:
            self.fail(f"Segmento {id1} não foi encontrado")
        hash_c = seg1["hash_conteudo"]

        # Checar repetições
        reps = self.banco.obter_repeticoes(hash_c, excluir_id=id1)
        self.assertEqual(len(reps), 1)
        self.assertEqual(reps[0]["id"], id2)

        # Propagar tradução
        total = self.banco.propagar_traducao_por_hash(hash_c, "Descanso no acampamento")
        self.assertEqual(total, 2)

        # Verificar se ambos atualizaram
        seg1_atualizado = self.banco.obter_segmento_por_id(id1)
        seg2_atualizado = self.banco.obter_segmento_por_id(id2)
        if seg1_atualizado is None:
            self.fail(f"Segmento {id1} não foi encontrado após a propagação")
        if seg2_atualizado is None:
            self.fail(f"Segmento {id2} não foi encontrado após a propagação")
        self.assertEqual(seg1_atualizado["traducao_revisada"], "Descanso no acampamento")
        self.assertEqual(seg2_atualizado["traducao_revisada"], "Descanso no acampamento")
        self.assertEqual(seg1_atualizado["status"], "revisado")
        self.assertEqual(seg2_atualizado["status"], "revisado")

    def teste_glossario_crud(self):
        termo_id = self.banco.salvar_termo_glossario(
            termo_en="Troop",
            termo_pt_padrao="Tropa",
            sinonimos_proibidos="Bando, Grupo",
            categoria="Mecânica"
        )
        self.assertGreater(termo_id, 0)

        lista = self.banco.listar_glossario()
        self.assertEqual(len(lista), 1)
        self.assertEqual(lista[0]["termo_pt_padrao"], "Tropa")

        sucesso_remocao = self.banco.remover_termo_glossario(termo_id)
        self.assertTrue(sucesso_remocao)
        self.assertEqual(len(self.banco.listar_glossario()), 0)

    def teste_limpar_segmentos(self):
        self.banco.salvar_segmento(
            arquivo="export_pt-BR.xml",
            tag_nome="name",
            chave_hierarquica="chave1",
            caminho_xml="caminho1",
            vanilla_en="Test",
            vanilla_pt="Teste",
            mod_en="Test",
            traducao_atual="Teste"
        )
        self.banco.salvar_segmento(
            arquivo="texts_pt-BR.xml",
            tag_nome="t",
            chave_hierarquica="chave2",
            caminho_xml="caminho2",
            vanilla_en="Sword",
            vanilla_pt="Espada",
            mod_en="Sword",
            traducao_atual="Espada"
        )
        self.assertEqual(self.banco.obter_estatisticas()["total_segmentos"], 2)
        removidos_arq = self.banco.limpar_segmentos("texts_pt-BR.xml")
        self.assertEqual(removidos_arq, 1)
        self.assertEqual(self.banco.obter_estatisticas()["total_segmentos"], 1)

        removidos = self.banco.limpar_segmentos()
        self.assertEqual(removidos, 1)
        self.assertEqual(self.banco.obter_estatisticas()["total_segmentos"], 0)

        removidos_vazio = self.banco.limpar_segmentos()
        self.assertEqual(removidos_vazio, 0)

    def teste_salvar_lote_idempotente(self):
        lote = [
            {
                "arquivo": "texts_pt-BR.xml",
                "tag_nome": "t",
                "chave_hierarquica": "chave_a",
                "caminho_xml": "chave_a",
                "mod_en": "Sword",
                "traducao_atual": "Espada",
                "status": "pendente"
            }
        ]
        self.banco.salvar_segmentos_em_lote(lote)
        self.assertEqual(self.banco.obter_estatisticas()["total_segmentos"], 1)

        # Atualizar segmento como revisado pelo usuário
        seg = self.banco.buscar_segmentos(termo_busca="Sword")["itens"][0]
        self.banco.atualizar_traducao_segmento(seg["id"], "Espada Curta", status="revisado")

        # Re-importar o mesmo lote (não deve duplicar e deve preservar revisão do usuário)
        self.banco.salvar_segmentos_em_lote(lote)
        self.assertEqual(self.banco.obter_estatisticas()["total_segmentos"], 1)

        seg_pos_reimport = self.banco.obter_segmento_por_id(seg["id"])
        assert seg_pos_reimport is not None
        self.assertEqual(seg_pos_reimport["traducao_revisada"], "Espada Curta")
        self.assertEqual(seg_pos_reimport["status"], "revisado")

    def teste_memoria_traducao(self):
        dicionario = {
            "Iron Ore": "Minério de Ferro",
            "Wood": "Madeira"
        }
        total = self.banco.carregar_memoria_traducao_lote(dicionario)
        self.assertEqual(total, 2)

        sugestao = self.banco.buscar_sugestao_memoria("Iron Ore")
        self.assertEqual(sugestao, "Minério de Ferro")

        sugestao_inexistente = self.banco.buscar_sugestao_memoria("Gold")
        self.assertIsNone(sugestao_inexistente)

    def teste_navegacao_e_posicao_filtro(self):
        id1 = self.banco.salvar_segmento(
            arquivo="export_pt-BR.xml",
            tag_nome="name",
            chave_hierarquica="items/sword/name",
            caminho_xml="items/sword/name",
            vanilla_en="Sword",
            vanilla_pt="Espada",
            mod_en="Master Sword",
            traducao_atual="Espada Mestra",
            status="pendente"
        )
        id2 = self.banco.salvar_segmento(
            arquivo="export_pt-BR.xml",
            tag_nome="name",
            chave_hierarquica="items/shield/name",
            caminho_xml="items/shield/name",
            vanilla_en="Shield",
            vanilla_pt="Escudo",
            mod_en="Shield",
            traducao_atual="Escudo",
            status="revisado"
        )
        id3 = self.banco.salvar_segmento(
            arquivo="texts_pt-BR.xml",
            tag_nome="t",
            chave_hierarquica="ui_button_ok",
            caminho_xml="ui_button_ok",
            vanilla_en="OK",
            vanilla_pt="OK",
            mod_en="OK",
            traducao_atual="OK",
            status="pendente"
        )

        # Navegar apenas pendentes
        nav_prox = self.banco.navegar_segmento(id1, direcao="proximo", filtro_status="pendente")
        self.assertEqual(nav_prox, id3)

        nav_ant = self.banco.navegar_segmento(id3, direcao="anterior", filtro_status="pendente")
        self.assertEqual(nav_ant, id1)

        # Posição no filtro
        pos_info = self.banco.obter_posicao_no_filtro(id1, filtro_status="pendente")
        self.assertEqual(pos_info["posicao_filtrada"], 1)
        self.assertEqual(pos_info["total_filtrados"], 2)

    def teste_arvore_hierarquica(self):
        self.banco.salvar_segmento(
            arquivo="export_pt-BR.xml",
            tag_nome="name",
            chave_hierarquica="items/bow/name",
            caminho_xml="items/bow/name",
            vanilla_en="Bow",
            vanilla_pt="Arco",
            mod_en="Bow",
            traducao_atual="Arco",
            status="pendente"
        )
        arvore = self.banco.obter_arvore_hierarquica()
        self.assertTrue(len(arvore) >= 1)
        no_export = next((n for n in arvore if n["arquivo"] == "export_pt-BR.xml"), None)
        self.assertIsNotNone(no_export)
        assert no_export is not None
        self.assertGreater(no_export["total_itens"], 0)
        self.assertTrue(any(c["nome"] == "items" for c in no_export["categorias"]))

    def teste_filtros_modificados_e_novos(self):
        # 1. Modificado pelo mod (mod_en != vanilla_en)
        id_mod = self.banco.salvar_segmento(
            arquivo="export_pt-BR.xml",
            tag_nome="desc",
            chave_hierarquica="items/bow/desc",
            caminho_xml="items/bow/desc",
            vanilla_en="Shoots arrows",
            vanilla_pt="Dispara flechas",
            mod_en="Shoots flaming arrows",
            traducao_atual="Dispara flechas",
            status="pendente"
        )
        # 2. Inédito / Novo (vanilla_en é nulo ou vazio)
        id_novo = self.banco.salvar_segmento(
            arquivo="export_pt-BR.xml",
            tag_nome="name",
            chave_hierarquica="items/flame_bow/name",
            caminho_xml="items/flame_bow/name",
            vanilla_en=None,
            vanilla_pt=None,
            mod_en="Flame Bow",
            traducao_atual="Arco Flamejante",
            status="pendente"
        )

        res_modificados = self.banco.buscar_segmentos(filtro_status="modificados")
        ids_mod = [item["id"] for item in res_modificados["itens"]]
        self.assertIn(id_mod, ids_mod)

        res_novos = self.banco.buscar_segmentos(filtro_status="novos")
        ids_novos = [item["id"] for item in res_novos["itens"]]
        self.assertIn(id_novo, ids_novos)

    def teste_filtros_compostos_mod_e_status(self):
        """Testa a combinação de filtros compostos (Apenas Mod + Pendentes/Revisados)."""
        # 1. Vanilla inalterado pendente
        id_vanilla_pendente = self.banco.salvar_segmento(
            arquivo="export_pt-BR.xml",
            tag_nome="name",
            chave_hierarquica="items/apple/name",
            caminho_xml="items/apple/name",
            vanilla_en="Apple",
            vanilla_pt="Maçã",
            mod_en="Apple",
            traducao_atual="Maçã",
            status="pendente"
        )
        # 2. Vanilla inalterado revisado
        id_vanilla_revisado = self.banco.salvar_segmento(
            arquivo="export_pt-BR.xml",
            tag_nome="name",
            chave_hierarquica="items/bread/name",
            caminho_xml="items/bread/name",
            vanilla_en="Bread",
            vanilla_pt="Pão",
            mod_en="Bread",
            traducao_atual="Pão",
            status="revisado"
        )
        # 3. Frase Modificada pelo Mod PENDENTE
        id_mod_pendente = self.banco.salvar_segmento(
            arquivo="export_pt-BR.xml",
            tag_nome="desc",
            chave_hierarquica="items/apple/desc",
            caminho_xml="items/apple/desc",
            vanilla_en="Restores 2 hunger",
            vanilla_pt="Restaura 2 de fome",
            mod_en="Restores 5 hunger and gives buff",
            traducao_atual="Restaura 5 de fome e dá bônus",
            status="pendente"
        )
        # 4. Frase Modificada pelo Mod REVISADA
        id_mod_revisado = self.banco.salvar_segmento(
            arquivo="export_pt-BR.xml",
            tag_nome="desc",
            chave_hierarquica="items/bread/desc",
            caminho_xml="items/bread/desc",
            vanilla_en="Restores 3 hunger",
            vanilla_pt="Restaura 3 de fome",
            mod_en="Restores 6 hunger",
            traducao_atual="Restaura 6 de fome",
            traducao_revisada="Restaura 6 de fome humana",
            status="revisado"
        )
        # 5. Frase Nova/Inédita do Mod PENDENTE
        id_novo_pendente = self.banco.salvar_segmento(
            arquivo="export_pt-BR.xml",
            tag_nome="name",
            chave_hierarquica="items/dragon_pie/name",
            caminho_xml="items/dragon_pie/name",
            vanilla_en=None,
            vanilla_pt=None,
            mod_en="Dragon Meat Pie",
            traducao_atual="Torta de Carne de Dragão",
            status="pendente"
        )
        # 6. Frase Nova/Inédita do Mod REVISADA
        id_novo_revisado = self.banco.salvar_segmento(
            arquivo="export_pt-BR.xml",
            tag_nome="name",
            chave_hierarquica="items/dragon_pie/desc",
            caminho_xml="items/dragon_pie/desc",
            vanilla_en="",
            vanilla_pt="",
            mod_en="Delicious pie made with dragon meat",
            traducao_atual="Deliciosa torta feita com carne de dragão",
            status="revisado"
        )

        # Teste 1: Apenas Mod (Novos + Modificados) que ainda NÃO foram aprovados/revisados (status = pendente)
        res_mod_pendentes = self.banco.buscar_segmentos(
            filtro_origem="apenas_mod",
            filtro_status="pendente"
        )
        ids_mod_pendentes = [item["id"] for item in res_mod_pendentes["itens"]]
        self.assertIn(id_mod_pendente, ids_mod_pendentes)
        self.assertIn(id_novo_pendente, ids_mod_pendentes)
        self.assertNotIn(id_vanilla_pendente, ids_mod_pendentes)
        self.assertNotIn(id_mod_revisado, ids_mod_pendentes)
        self.assertNotIn(id_novo_revisado, ids_mod_pendentes)
        self.assertNotIn(id_vanilla_revisado, ids_mod_pendentes)

        # Teste 2: Preset "mod_pendentes"
        res_preset = self.banco.buscar_segmentos(filtro_status="mod_pendentes")
        ids_preset = [item["id"] for item in res_preset["itens"]]
        self.assertEqual(sorted(ids_mod_pendentes), sorted(ids_preset))

        # Teste 3: Apenas Modificados PENDENTES
        res_mod_so_pendentes = self.banco.buscar_segmentos(
            filtro_origem="modificados",
            filtro_status="pendente"
        )
        ids_so_mod = [item["id"] for item in res_mod_so_pendentes["itens"]]
        self.assertIn(id_mod_pendente, ids_so_mod)
        self.assertNotIn(id_novo_pendente, ids_so_mod)

        # Teste 4: Navegação entre frases do Mod Pendentes
        nav_prox = self.banco.navegar_segmento(
            id_atual=id_mod_pendente,
            direcao="proximo",
            filtro_origem="apenas_mod",
            filtro_status="pendente"
        )
        self.assertEqual(nav_prox, id_novo_pendente)

        # Teste 5: Posição no filtro composto
        pos = self.banco.obter_posicao_no_filtro(
            id_segmento=id_novo_pendente,
            filtro_origem="apenas_mod",
            filtro_status="pendente"
        )
        self.assertEqual(pos["total_filtrados"], 2)
        self.assertEqual(pos["posicao_filtrada"], 2)

    def teste_tipo_delta_e_estatisticas_mod(self):
        """Valida que obter_segmento_por_id e buscar_segmentos retornem tipo_delta correto e obter_estatisticas inclua escopo do mod."""
        id_vanilla = self.banco.salvar_segmento(
            arquivo="export_pt-BR.xml",
            tag_nome="name",
            chave_hierarquica="item_v",
            caminho_xml="/item/1",
            vanilla_en="Bread",
            vanilla_pt="Pão",
            mod_en="Bread",
            traducao_atual="Pão"
        )
        id_novo = self.banco.salvar_segmento(
            arquivo="export_pt-BR.xml",
            tag_nome="name",
            chave_hierarquica="item_n",
            caminho_xml="/item/2",
            vanilla_en=None,
            vanilla_pt=None,
            mod_en="Elixir of Life",
            traducao_atual="Elixir da Vida",
            status="revisado"
        )
        id_modificado = self.banco.salvar_segmento(
            arquivo="export_pt-BR.xml",
            tag_nome="name",
            chave_hierarquica="item_m",
            caminho_xml="/item/3",
            vanilla_en="Old Ring",
            vanilla_pt="Anel Antigo",
            mod_en="Cursed Old Ring",
            traducao_atual="Anel Antigo Amaldiçoado"
        )

        # Checar tipo_delta por id
        seg_v = self.banco.obter_segmento_por_id(id_vanilla)
        seg_n = self.banco.obter_segmento_por_id(id_novo)
        seg_m = self.banco.obter_segmento_por_id(id_modificado)

        self.assertIsNotNone(seg_v)
        self.assertIsNotNone(seg_n)
        self.assertIsNotNone(seg_m)
        self.assertEqual(seg_v["tipo_delta"], "vanilla")
        self.assertEqual(seg_n["tipo_delta"], "novo")
        self.assertEqual(seg_m["tipo_delta"], "modificado")

        # Checar tipo_delta na busca
        busca = self.banco.buscar_segmentos()
        deltas = {item["id"]: item["tipo_delta"] for item in busca["itens"]}
        self.assertEqual(deltas[id_vanilla], "vanilla")
        self.assertEqual(deltas[id_novo], "novo")
        self.assertEqual(deltas[id_modificado], "modificado")

        # Checar estatísticas enriquecidas
        stats = self.banco.obter_estatisticas()
        self.assertEqual(stats["total_segmentos"], 3)
        self.assertEqual(stats["mod_total"], 2)
        self.assertEqual(stats["mod_revisados"], 1)
        self.assertEqual(stats["mod_porcentagem_concluida"], 50.0)
        self.assertEqual(stats["novos_total"], 1)
        self.assertEqual(stats["modificados_total"], 1)
        self.assertEqual(stats["vanilla_total"], 1)

    def teste_obter_primeiro_segmento_id_e_posicao_edge_cases(self):
        """Valida que obter_primeiro_segmento_id retorne None caso nada corresponda aos filtros e posicao_filtrada seja 0 quando fora do filtro."""
        # Salvar um segmento pendente
        seg_id = self.banco.salvar_segmento(
            arquivo="export_pt-BR.xml",
            tag_nome="name",
            chave_hierarquica="items/sword/name",
            caminho_xml="items/1",
            vanilla_en="Sword",
            vanilla_pt="Espada",
            mod_en="Sword",
            traducao_atual="Espada",
            status="pendente"
        )

        # 1. Filtro sem nenhum resultado correspondente
        primeiro_inexistente = self.banco.obter_primeiro_segmento_id(termo_busca="TERMO_INEXISTENTE_XYZ")
        self.assertIsNone(primeiro_inexistente)

        # 2. Posição no filtro quando o segmento NÃO pertence aos filtros
        pos_fora = self.banco.obter_posicao_no_filtro(
            id_segmento=seg_id,
            filtro_status="revisado"  # seg_id é pendente, não revisado!
        )
        self.assertEqual(pos_fora["posicao_filtrada"], 0)
        self.assertEqual(pos_fora["total_filtrados"], 0)

        # 3. Posição no filtro quando o segmento pertence ao filtro
        pos_dentro = self.banco.obter_posicao_no_filtro(
            id_segmento=seg_id,
            filtro_status="pendente"
        )
        self.assertEqual(pos_dentro["posicao_filtrada"], 1)
        self.assertEqual(pos_dentro["total_filtrados"], 1)

    def teste_filtro_categoria_separadores(self):
        """Valida a resolução de categorias com diferentes separadores (barra, ponto, underscore)."""
        self.banco.salvar_segmento(
            arquivo="export_pt-BR.xml",
            tag_nome="cell",
            chave_hierarquica="skill/fireball/desc",
            caminho_xml="/s/1",
            vanilla_en=None,
            vanilla_pt=None,
            mod_en="Fireball",
            traducao_atual="Bola de Fogo"
        )
        self.banco.salvar_segmento(
            arquivo="texts_pt-BR.xml",
            tag_nome="t",
            chave_hierarquica="battle.victory.message",
            caminho_xml="/t/1",
            vanilla_en=None,
            vanilla_pt=None,
            mod_en="Victory",
            traducao_atual="Vitória"
        )
        self.banco.salvar_segmento(
            arquivo="export_pt-BR.xml",
            tag_nome="cell",
            chave_hierarquica="trait_brave_desc",
            caminho_xml="/tr/1",
            vanilla_en=None,
            vanilla_pt=None,
            mod_en="Brave trait",
            traducao_atual="Traço corajoso"
        )

        # Busca por 'skill' (com /)
        res_skill = self.banco.buscar_segmentos(filtro_categoria="skill")
        self.assertEqual(res_skill["total_itens"], 1)

        # Busca por 'battle' (com .)
        res_battle = self.banco.buscar_segmentos(filtro_categoria="battle")
        self.assertEqual(res_battle["total_itens"], 1)

        # Busca por 'trait' (com _)
        res_trait = self.banco.buscar_segmentos(filtro_categoria="trait")
        self.assertEqual(res_trait["total_itens"], 1)


if __name__ == "__main__":
    unittest.main()

