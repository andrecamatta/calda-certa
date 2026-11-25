"""Testes das novidades (nutrição, Creami, adoçantes, estabilizantes,
proteínas, Brix, lembretes, perfil fit). Tudo aditivo: os testes de
equivalência garantem que o comportamento original não mudou."""

from __future__ import annotations

import json

import pytest

from caldacerta import dados, motor, nutricao
from caldacerta import receita as rec
from caldacerta.cli import main
from caldacerta.ficha import ficha_markdown, ficha_texto
from caldacerta.relatorio import analisar

TODOS = dados.mapa_ingredientes_todos()
MAQ = {m["id"]: m for m in dados.maquinas()}
PERF = {p["id"]: p for p in dados.perfis_todos()}


@pytest.fixture(autouse=True)
def dados_temporarios(tmp_path, monkeypatch):
    monkeypatch.setenv("CALDA_DADOS", str(tmp_path / "dados"))
    yield tmp_path / "dados"


def rodar(capsys, *args):
    code = main(list(args))
    out = capsys.readouterr()
    return code, out.out, out.err


def rodar_json(capsys, *args):
    code, out, err = rodar(capsys, "--json", *args)
    assert code == 0, err
    return json.loads(out)


def receita_com(itens, perfil="fam_branca", maquina="mac_vitrine", **extra):
    return {"nome": "Teste", "versao": "V1", "perfil": perfil, "maquina": maquina,
            "itens": [{"ingrediente": i, "gramas": g} for i, g in itens], **extra}


def gravar(tmp_path, r, nome="r.json"):
    p = tmp_path / nome
    p.write_text(json.dumps(r, ensure_ascii=False), encoding="utf-8")
    return str(p)


# ------------------------------------------------------------------ dados
def test_banco_complementar_separado():
    assert len(dados.ingredientes()) == 45 and len(dados.perfis()) == 11 and len(dados.receitas()) == 24
    assert len(dados.ingredientes_todos()) == 45 + len(dados.ingredientes_extra())
    assert "fam_creami_fit" in PERF
    assert {r["id"] for r in dados.receitas_extra()} == {"rec_creami_frosty_amendoas", "rec_creami_frosty_agua"}
    # ids novos não colidem com os do app nem com os ingredientes removidos (substituições)
    subs = dados.carregar_constantes()["substituicoes"]
    for i in dados.ingredientes_extra():
        assert i["id"] not in subs
        assert abs(motor.soma_composicao(i) - 100) <= 0.5


def test_sem_fruta_do_monge():
    texto = json.dumps(dados.novidades(), ensure_ascii=False).lower() + json.dumps(dados.carregar_constantes()).lower()
    assert "monge" not in texto and "mogros" not in texto and "monk" not in texto


def test_complementos_so_preenchem_o_ausente():
    assert "dose_max_pct" not in dados.mapa_ingredientes()["ing_goma_guar"]  # arquivo original intocado
    guar = TODOS["ing_goma_guar"]
    assert guar["dose_max_pct"] == 0.3 and guar["ativacao"] == "frio" and "fibrosa" in guar["defeito_excesso"]
    assert TODOS["ing_whey_iso"]["caseina"] == 0
    for k in ("agua", "pod", "pac", "custo_kg"):
        assert guar[k] == dados.mapa_ingredientes()["ing_goma_guar"][k]


def test_busca_com_extras_nao_cria_ambiguidade():
    base, extra = dados.receitas(), dados.receitas_extra()
    assert dados.achar_com_extras(base, extra, "rec_choc70", "receita")["id"] == "rec_choc70"
    assert dados.achar_com_extras(base, extra, "frosty fit balanceado", "receita")["id"] == "rec_creami_frosty_agua"
    with pytest.raises(KeyError, match="nada encontrado"):
        dados.achar_com_extras(base, extra, "zzz_nao_existe", "receita")


# ---------------------------------------------------------------- energia
def test_kcal_por_100g():
    assert nutricao.kcal_100g(TODOS["ing_leite_int"]) == pytest.approx(3.5 * 9 + 3.2 * 4 + 4.8 * 4)
    assert nutricao.kcal_100g(TODOS["ing_sacarose"]) == pytest.approx(400)
    assert nutricao.kcal_100g(TODOS["ing_eritritol_puro"]) == 0
    assert nutricao.kcal_100g(TODOS["ing_alulose"]) == pytest.approx(40)
    assert nutricao.kcal_100g(TODOS["ing_destilado_40"]) == pytest.approx(33.4 * 7)
    assert nutricao.kcal_100g(TODOS["ing_sucralose_pura"]) == 0
    # sobreposição explícita
    assert nutricao.kcal_100g({**TODOS["ing_sacarose"], "kcal_100g": 123}) == 123
    # fibra (2 kcal/g) e cinzas (0) baixam o resto não especificado (4 kcal/g)
    cacau = TODOS["ing_cacau_po"]
    sem = {k: v for k, v in cacau.items() if k not in ("fibra", "cinzas")}
    assert nutricao.kcal_100g(cacau) == pytest.approx(nutricao.kcal_100g(sem) - 33 * 2 - 8 * 4)
    # tâmara ≈ USDA (277 kcal)
    assert 260 < nutricao.kcal_100g(TODOS["ing_tamara"]) < 300


def test_nutricao_por_porcao_pote_e_lote():
    r = dados.achar(dados.receitas(), "rec_fiordilatte", "receita")
    a = analisar(r, MAQ["mac_creami"], PERF["fam_branca"], porcao_g=80)
    n = a["nutricao"]
    assert n["lote"]["gramas"] == pytest.approx(a["totais"]["gramas"])
    assert n["porcao"]["gramas"] == 80
    assert n["porcao"]["kcal"] == pytest.approx(n["kcal_100g"] * 0.8)
    assert n["porcao"]["proteina_g"] == pytest.approx(a["metricas"]["proteina"] * 0.8)
    assert n["pote"]["gramas"] == pytest.approx(a["pote"]["gramas"])
    assert 150 < n["kcal_100g"] < 260
    # máquina sem pote: sem nutrição por pote
    b = analisar(r, MAQ["mac_vitrine"], PERF["fam_branca"])
    assert b["pote"] is None and b["nutricao"]["pote"] is None and b["nutricao"]["porcao"]["gramas"] == 100


def test_acucares_do_rotulo_sem_alulose():
    z = motor.avaliar([{"ingrediente": "ing_alulose", "gramas": 10}, {"ingrediente": "ing_sacarose", "gramas": 10},
                       {"ingrediente": "ing_agua", "gramas": 80}], TODOS)
    n = nutricao.nutricao(z, TODOS)
    assert n["por_100g"]["acucares_g"] == pytest.approx(10)
    assert n["por_100g"]["poliois_g"]["alulose"] == pytest.approx(10)
    assert n["kcal_100g"] == pytest.approx(40 + 4)


# --------------------------------------------------------- densidade/pote
def test_densidade_e_pote():
    assert nutricao.densidade({"agua": 100, "gordura": 0, "solidos_totais": 0, "alcool": 0}) == 1
    rho = nutricao.densidade({"agua": 63, "gordura": 8, "solidos_totais": 37, "alcool": 0})
    assert rho == pytest.approx(100 / (63 + 8 / 0.93 + 29 / 1.58))
    cr = MAQ["mac_creami"]
    assert [p["volume_ml"] for p in cr["potes"]] == [473, 709]
    assert cr["temp_freezer_c"] == -18 and cr["congelamento_h"] == {"minimo": 24, "base_aquecida": 36}
    assert nutricao.escolher_pote(cr, "deluxe")["volume_ml"] == 709
    assert nutricao.escolher_pote(cr)["id"] == "padrao"
    assert nutricao.gramas_pote(cr, cr["potes"][0], 1.1) == pytest.approx(473 * 0.95 * 1.1)
    with pytest.raises(ValueError):
        nutricao.escolher_pote(MAQ["mac_vitrine"], "deluxe")
    assert MAQ["mac_creami"]["lote_g"] == 450  # --lote maquina continua igual


def test_cli_lote_pote(capsys):
    a = rodar_json(capsys, "analisar", "rec_creami_baunilha", "--lote", "pote")
    assert a["escalonada_para_g"] == pytest.approx(round(a["pote"]["gramas"]), abs=1)
    assert a["totais"]["gramas"] == pytest.approx(a["escalonada_para_g"], abs=1)
    d = rodar_json(capsys, "analisar", "rec_creami_baunilha", "--lote", "pote:deluxe")
    assert d["pote"]["id"] == "deluxe" and d["escalonada_para_g"] > 700
    m = rodar_json(capsys, "analisar", "rec_creami_baunilha", "--lote", "maquina")
    assert m["escalonada_para_g"] == 450
    code, _, err = rodar(capsys, "analisar", "rec_fiordilatte", "--maquina", "mac_vitrine", "--lote", "pote")
    assert code == 1 and "potes" in err


def test_cli_porcao_e_texto(capsys):
    code, out, _ = rodar(capsys, "analisar", "rec_creami_baunilha", "--porcao", "150", "--pote", "deluxe")
    assert code == 0
    assert "Nutrição (estimativa):" in out and "Porção de 150 g" in out and "Pote Deluxe 24 oz" in out


# ------------------------------------------------------------- adoçantes
def test_adocantes_sem_acucar():
    erit, alu, suc = TODOS["ing_eritritol_puro"], TODOS["ing_alulose"], TODOS["ing_sucralose_pura"]
    assert (erit["pod"], erit["pac"]) == (65, 280)
    assert erit["pac"] > alu["pac"]  # massa molar: eritritol deprime mais que alulose
    assert suc["pod"] == 60000 and suc["pac"] < 100
    blend = TODOS["ing_eritritol_estevia"]
    assert 95 <= blend["pod"] <= 105
    chaves = {a["chave"] for a in dados.carregar_constantes()["acucares"]}
    assert {"sucralose", "esteviosideos"} <= chaves


def test_alerta_eritritol_e_tolerancia():
    itens = [{"ingrediente": "ing_leite_int", "gramas": 800}, {"ingrediente": "ing_eritritol_puro", "gramas": 150},
             {"ingrediente": "ing_creme_35", "gramas": 50}]
    ex = nutricao.complementos(itens, TODOS, MAQ["mac_creami"], PERF["fam_branca"], porcao_g=200)
    codigos = {a["codigo"] for a in ex["alertas"]}
    assert "eritritol_cristaliza" in codigos  # 15% > 6%
    assert "tolerancia_digestiva_porcao" in codigos  # 30 g de eritritol em 200 g > 25 g
    ex2 = nutricao.complementos(itens, TODOS, MAQ["mac_creami"], PERF["fam_branca"], porcao_g=50)
    c2 = {a["codigo"] for a in ex2["alertas"]}
    assert "tolerancia_digestiva_porcao" not in c2 and "tolerancia_digestiva_pote" in c2


def test_sem_alerta_com_pouco_eritritol():
    itens = [{"ingrediente": "ing_leite_int", "gramas": 940}, {"ingrediente": "ing_eritritol_puro", "gramas": 50},
             {"ingrediente": "ing_leite_po_desn", "gramas": 10}]
    ex = nutricao.complementos(itens, TODOS, MAQ["mac_vitrine"], PERF["fam_branca"])
    assert "eritritol_cristaliza" not in {a["codigo"] for a in ex["alertas"]}


# ------------------------------------------------------- estabilizantes
def test_estabilizantes_dose_e_ativacao():
    itens = [{"ingrediente": "ing_leite_int", "gramas": 995}, {"ingrediente": "ing_goma_xantana", "gramas": 3},
             {"ingrediente": "ing_goma_alfarroba", "gramas": 2}]
    frio = nutricao.complementos(itens, TODOS, MAQ["mac_vitrine"], PERF["fam_branca"], processo="frio")
    al = {(a["codigo"], a.get("ingrediente")) for a in frio["alertas"]}
    assert ("dose_maxima", "ing_goma_xantana") in al  # 0,3% > 0,1%
    assert ("dose_maxima", "ing_goma_alfarroba") not in al  # 0,2% < 0,3%
    assert ("ativacao", "ing_goma_alfarroba") in al
    texto = next(a["texto"] for a in frio["alertas"] if a["codigo"] == "dose_maxima")
    assert "babenta" in texto
    quente = nutricao.complementos(itens, TODOS, MAQ["mac_vitrine"], PERF["fam_branca"], processo="quente")
    assert "ativacao" not in {a["codigo"] for a in quente["alertas"]}
    desconhecido = nutricao.complementos(itens, TODOS, MAQ["mac_vitrine"], PERF["fam_branca"])
    assert "ativacao" not in {a["codigo"] for a in desconhecido["alertas"]}


def test_guar_existente_tem_regras(capsys, tmp_path):
    r = receita_com([("ing_leite_int", 990), ("ing_goma_guar", 5), ("ing_sacarose", 5)])
    a = rodar_json(capsys, "analisar", gravar(tmp_path, r))
    assert any(x["codigo"] == "dose_maxima" and "fibrosa" in x["texto"] for x in a["alertas"])


def test_cli_processo(capsys, tmp_path):
    r = receita_com([("ing_leite_int", 990), ("ing_goma_alfarroba", 2), ("ing_sacarose", 8)], processo="frio")
    p = gravar(tmp_path, r)
    a = rodar_json(capsys, "analisar", p)
    assert a["processo"] == "frio" and any(x["codigo"] == "ativacao" for x in a["alertas"])
    b = rodar_json(capsys, "analisar", p, "--processo", "quente")
    assert not any(x["codigo"] == "ativacao" for x in b["alertas"])
    code, _, err = rodar(capsys, "analisar", gravar(tmp_path, {**r, "processo": "morno"}, "x.json"))
    assert code == 1 and "processo" in err


# ------------------------------------------------------------- proteínas
def test_proteinas_e_caseina():
    assert nutricao.caseina_100g(TODOS["ing_leite_int"]) == pytest.approx(3.2 * 0.8)
    assert nutricao.caseina_100g(TODOS["ing_whey_iso"]) == 0
    assert nutricao.caseina_100g(TODOS["ing_whey_caseina"]) == 37.5
    assert nutricao.caseina_100g(TODOS["ing_proteina_ervilha"]) == 0
    for iid in ("ing_leite_uf_proteico", "ing_leite_1", "ing_bebida_amendoas", "ing_whey_caseina"):
        assert iid in TODOS
    itens = [{"ingrediente": "ing_leite_uf_proteico", "gramas": 850}, {"ingrediente": "ing_whey_caseina", "gramas": 60},
             {"ingrediente": "ing_alulose", "gramas": 90}]
    ex = nutricao.complementos(itens, TODOS, MAQ["mac_creami"], PERF["fam_proteico"])
    assert "caseina_alta" in {a["codigo"] for a in ex["alertas"]}
    whey = [{"ingrediente": "ing_leite_desn", "gramas": 850}, {"ingrediente": "ing_whey_iso", "gramas": 60},
            {"ingrediente": "ing_alulose", "gramas": 90}]
    ex2 = nutricao.complementos(whey, TODOS, MAQ["mac_creami"], PERF["fam_proteico"])
    assert "caseina_alta" not in {a["codigo"] for a in ex2["alertas"]}


def test_alerta_agua_livre():
    itens = [{"ingrediente": "ing_bebida_amendoas", "gramas": 900}, {"ingrediente": "ing_alulose", "gramas": 100}]
    ex = nutricao.complementos(itens, TODOS, MAQ["mac_creami"], PERF["fam_proteico"])
    assert "agua_livre" in {a["codigo"] for a in ex["alertas"]}


# ------------------------------------------------------------------ Brix
def test_ajustar_brix():
    manga = TODOS["ing_polpa_manga"]
    m = nutricao.ajustar_brix(manga, 12)
    assert m["acucares"] == pytest.approx(12 - 0.3)  # Brix menos os ácidos
    assert m["agua"] == pytest.approx(83 + (14 - 11.7))
    assert motor.soma_composicao(m) == pytest.approx(100)
    assert m["pac"] < manga["pac"] and m["pod"] < manga["pod"]
    assert sum(v for k, v in m["perfil_acucares"].items() if k != "acidos_fruta") == pytest.approx(11.7)
    with pytest.raises(ValueError):
        nutricao.ajustar_brix(TODOS["ing_leite_int"], 10)  # sem açúcar
    with pytest.raises(ValueError):
        nutricao.ajustar_brix(manga, 120)


def test_brix_na_receita_e_cli(capsys, tmp_path):
    base = dados.achar(dados.receitas(), "rec_sorbet_manga", "receita")
    a0 = rodar_json(capsys, "analisar", "rec_sorbet_manga")
    a1 = rodar_json(capsys, "analisar", "rec_sorbet_manga", "--brix", "ing_polpa_manga=17")
    assert a1["metricas"]["acucares"] > a0["metricas"]["acucares"]
    assert a1["totais"]["gramas"] == a0["totais"]["gramas"]
    assert a1["ajustes_brix"][0]["brix"] == 17 and a0["ajustes_brix"] == []
    # mesmo efeito pelo arquivo de receita
    r = json.loads(json.dumps(base))
    for i in r["itens"]:
        if i["ingrediente"] == "ing_polpa_manga":
            i["brix"] = 17
    a2 = rodar_json(capsys, "analisar", gravar(tmp_path, r))
    assert a2["metricas"] == a1["metricas"]
    # ficha texto usa a composição corrigida
    _, ft, _ = rodar(capsys, "ficha", gravar(tmp_path, r, "b.json"), "--formato", "texto")
    _, ft0, _ = rodar(capsys, "ficha", "rec_sorbet_manga", "--formato", "texto")
    assert ft != ft0
    code, _, err = rodar(capsys, "analisar", "rec_sorbet_manga", "--brix", "ing_leite_int=10")
    assert code == 1 and "não está na receita" in err


def test_brix_roundtrip_arquivo():
    r = rec.normalizar({"nome": "X", "processo": "quente",
                        "itens": [{"ingrediente": "ing_polpa_manga", "gramas": 100, "brix": "15.5"},
                                  {"ingrediente": "ing_agua", "gramas": 10}]})
    arq = rec.para_arquivo(r)
    assert arq["processo"] == "quente"
    assert arq["itens"][0]["brix"] == 15.5 and "brix" not in arq["itens"][1]
    # receitas antigas: arquivo idêntico (sem chaves novas)
    for velha in dados.receitas():
        assert "processo" not in rec.para_arquivo(rec.normalizar(velha))
        assert all("brix" not in i for i in rec.para_arquivo(rec.normalizar(velha))["itens"])


def test_brix_conflitante():
    itens = [{"ingrediente": "ing_polpa_manga", "gramas": 10, "brix": 12},
             {"ingrediente": "ing_polpa_manga", "gramas": 10, "brix": 14}]
    with pytest.raises(ValueError):
        nutricao.aplicar_brix(TODOS, itens)


# ------------------------------------------------------ balanceamento light
def test_light_reduz_kcal_sem_sair_do_verde():
    for rid in ("rec_proteico_baunilha", "rec_fiordilatte"):
        r = dados.achar(dados.receitas(), rid, "receita")
        maq = MAQ[r["maquina"]]
        faixas = motor.faixas_alvo(PERF[r["perfil"]], maq)
        padrao = motor.balancear(r["itens"], TODOS, faixas)
        f, _ = nutricao.objetivo_light(r["itens"], TODOS, faixas)
        light = motor.balancear(r["itens"], TODOS, faixas, funcao_objetivo=f)

        def medir(itens):
            z = motor.avaliar(itens, TODOS)
            return motor.conformidade(z["metricas"], faixas)["ideal"], nutricao.nutricao(z, TODOS)["kcal_100g"]

        vp, kp = medir(padrao["itens"])
        vl, kl = medir(light["itens"])
        assert vl >= vp
        assert kl < kp
        assert sum(i["gramas"] for i in light["itens"]) == pytest.approx(sum(i["gramas"] for i in r["itens"]))


def test_objetivo_padrao_inalterado():
    r = dados.achar(dados.receitas(), "rec_choc70", "receita")
    faixas = motor.faixas_alvo(PERF[r["perfil"]], MAQ[r["maquina"]])
    a = motor.balancear(r["itens"], dados.mapa_ingredientes(), faixas)
    b = motor.balancear(r["itens"], TODOS, faixas, funcao_objetivo=None)
    assert a == b


def test_light_proteina_minima():
    r = dados.achar(dados.receitas(), "rec_proteico_baunilha", "receita")
    faixas = motor.faixas_alvo(PERF[r["perfil"]], MAQ[r["maquina"]])
    itens = [{**i, "travado": False} for i in r["itens"]]  # o whey vem travado na receita
    f, fx = nutricao.objetivo_light(itens, TODOS, faixas, proteina_min=10)
    assert fx["proteina"][0] == 10
    res = motor.balancear(itens, TODOS, faixas, funcao_objetivo=f)
    assert motor.avaliar(res["itens"], TODOS)["metricas"]["proteina"] >= 9.9


def test_cli_balancear_light(capsys, tmp_path):
    out = tmp_path / "l.json"
    r = rodar_json(capsys, "balancear", "rec_creami_frosty_amendoas", "--objetivo", "light",
                   "--incluir", "ing_alulose,ing_polidextrose", "--liberar", "ing_tamara", "-o", str(out))
    assert r["objetivo"] == "light"
    assert r["kcal_100g_depois"] < r["kcal_100g_antes"]
    assert r["faixa_verde_depois"] == "8/8"
    ids = [i["ingrediente"] for i in r["receita"]["itens"]]
    assert ids[-2:] == ["ing_alulose", "ing_polidextrose"]
    assert json.loads(out.read_text(encoding="utf-8")) == r["receita"]
    p = rodar_json(capsys, "balancear", "rec_proteico_baunilha", "--objetivo", "light", "--proteina-min", "9",
                   "--liberar", "todos")
    assert p["proteina_pct_depois"] >= 8.95
    code, out_txt, _ = rodar(capsys, "balancear", "rec_proteico_baunilha", "--objetivo", "light", "--proteina-min", "9")
    assert "Objetivo light:" in out_txt and "NÃO atingido" in out_txt  # whey travado: inviável
    code, _, err = rodar(capsys, "balancear", "rec_proteico_baunilha", "--proteina-min", "9")
    assert code == 1 and "light" in err
    code, _, err = rodar(capsys, "balancear", "rec_fiordilatte", "--incluir", "ing_nao_existe")
    assert code == 1


# ------------------------------------------------- correções e perfil fit
def test_frosty_fit_e_correcoes(capsys):
    a = rodar_json(capsys, "analisar", "rec_creami_frosty_amendoas")
    assert a["perfil"]["id"] == "fam_creami_fit"
    st = {p["chave"]: p["status"] for p in a["conformidade"]["parametros"]}
    assert st["pac"] == "ABAIXO"
    comp = a["comparacao_classica"]
    assert comp["perfil"] == "fam_branca" and comp["ideal"] <= 2
    pac = [c for c in a["correcoes"] if c["metrica"] == "pac"]
    alu = next(c for c in pac if c["ingrediente"] == "ing_alulose")
    assert alu["valor_depois"] == pytest.approx(alu["alvo"], abs=1)
    assert 0 < alu["gramas"] < 30
    assert all(int(c["faixa_verde_depois"].split("/")[0]) >= a["conformidade"]["ideal"] for c in a["correcoes"])
    b = rodar_json(capsys, "analisar", "rec_creami_frosty_agua")
    assert b["conformidade"]["ideal"] == 8 and b["correcoes"] == []
    _, txt, _ = rodar(capsys, "analisar", "rec_creami_frosty_amendoas")
    assert "Pelos padrões de Gelato · Base Branca" in txt and "Correções de um ingrediente" in txt


def test_receitas_existentes_sem_comparacao_classica(capsys):
    a = rodar_json(capsys, "analisar", "rec_fiordilatte")
    assert a["comparacao_classica"] is None


# ------------------------------------------------- ficha, página, listas
def test_ficha_md_tem_novidades_e_texto_igual(capsys):
    r = dados.achar(dados.receitas(), "rec_choc70", "receita")
    maq, perf = MAQ["mac_creami"], PERF["fam_chocolate"]
    md = ficha_markdown(r["nome"], r["versao"], r["itens"], TODOS, perf, maq)
    for s in ("## Nutrição (estimativa)", "## Máquina", "## Lembretes de processo", "Prove a calda",
              "Misture os secos", "~90 s", "~15 min a espuma", "derreta com um pouco de óleo"):
        assert s in md
    antigo = ficha_markdown(r["nome"], r["versao"], r["itens"], TODOS, perf, maq, novidades=False)
    assert md.startswith(antigo.rstrip("\n"))
    assert ficha_texto(r["nome"], r["versao"], r["itens"], TODOS, perf, maq) == \
        ficha_texto(r["nome"], r["versao"], r["itens"], dados.mapa_ingredientes(), perf, maq)
    _, out, _ = rodar(capsys, "ficha", "rec_choc70", "--formato", "texto")
    assert "kcal" not in out and "Lembretes" not in out


def test_lembretes_condicionais():
    sem = nutricao.lembretes(MAQ["mac_vitrine"], [{"ingrediente": "ing_leite_int"}], TODOS)
    assert len(sem) == 3 and not any("espuma" in l or "chocolate" in l.lower() for l in sem)
    choc = nutricao.lembretes(MAQ["mac_vitrine"], [{"ingrediente": "ing_choc_70"}], TODOS)
    assert any("chocolate" in l.lower() for l in choc)
    cr = nutricao.lembretes(MAQ["mac_creami"], [{"ingrediente": "ing_leite_int"}], TODOS)
    assert any("espuma" in l for l in cr) and any("36 h" in l for l in cr)


def test_pagina_tem_novidades(capsys, tmp_path):
    p = tmp_path / "x.html"
    code, _, _ = rodar(capsys, "pagina", "rec_creami_frosty_amendoas", "-o", str(p))
    html = p.read_text(encoding="utf-8")
    assert code == 0 and "<script" not in html and "https://" not in html
    for s in ("Nutrição (estimativa)", "kcal", "Lembretes de processo", "Pote e congelamento",
              "Comparação com o padrão clássico", "Correções de um ingrediente"):
        assert s in html


def test_listas_todos(capsys):
    assert len(rodar_json(capsys, "ingredientes")) == 45
    assert len(rodar_json(capsys, "ingredientes", "--todos")) == 45 + len(dados.ingredientes_extra())
    assert len(rodar_json(capsys, "receitas", "--todos")) == 26
    assert len(rodar_json(capsys, "perfis", "--todos")) == 12
    _, out, _ = rodar(capsys, "ingredientes")
    assert "use --todos" in out
    _, out, _ = rodar(capsys, "maquinas")
    assert "709 ml" in out and "24 h" in out


def test_ingrediente_extra_mostrar_editar_remover(capsys, dados_temporarios):
    m = rodar_json(capsys, "ingrediente", "mostrar", "ing_goma_xantana")
    assert m["ingrediente"]["dose_max_pct"] == 0.1
    _, txt, _ = rodar(capsys, "ingrediente", "mostrar", "ing_tamara")
    assert "kcal/100 g" in txt
    e = rodar_json(capsys, "ingrediente", "editar", "ing_goma_xantana", "--custo-kg", "99")
    assert e["ingrediente"]["custo_kg"] == 99 and e["ingrediente"]["dose_max_pct"] == 0.1
    assert e["ingrediente"]["ativacao"] == "frio"
    assert (dados_temporarios / "novidades.json").exists()
    assert not (dados_temporarios / "ingredientes.json").exists()
    assert TODOS["ing_goma_xantana"]["custo_kg"] == 100  # pacote intocado
    g = rodar_json(capsys, "ingrediente", "editar", "ing_goma_guar", "--kcal-100g", "190", "--dose-max-pct", "0.25")
    assert g["ingrediente"]["kcal_100g"] == 190 and g["ingrediente"]["dose_max_pct"] == 0.25
    assert dados.mapa_ingredientes()["ing_goma_guar"]["dose_max_pct"] == 0.25
    code, _, err = rodar(capsys, "ingrediente", "remover", "ing_tamara")
    assert code == 1 and "--forcar" in err
    rodar_json(capsys, "ingrediente", "remover", "ing_goma_xantana")
    assert "ing_goma_xantana" not in dados.mapa_ingredientes_todos()
    assert len(dados.ingredientes()) == 45
    n = rodar_json(capsys, "ingrediente", "adicionar", "--nome", "Goma Teste", "--outros-solidos", "90", "--agua", "10",
                   "--ativacao", "quente", "--dose-max-pct", "0.2", "--defeito-excesso", "elástica")
    assert n["ingrediente"]["ativacao"] == "quente" and n["ingrediente"]["dose_max_pct"] == 0.2


# ------------------------------------------- eritritol: limites de saúde
def _erit(gramas, total=1000):
    return [{"ingrediente": "ing_leite_int", "gramas": total - gramas - 100},
            {"ingrediente": "ing_creme_35", "gramas": 100}, {"ingrediente": "ing_eritritol_puro", "gramas": gramas}]


def test_eritritol_limite_por_porcao():
    assert nutricao.limite_eritritol_porcao() == pytest.approx(0.5 * 70 / 3)
    assert nutricao.limite_eritritol_porcao(90) == pytest.approx(15)


def test_eritritol_alerta_forte_30g():
    # 30 g no lote (1 kg): alerta forte; porção de 100 g = 3 g, abaixo do teto
    ex = nutricao.complementos(_erit(30), TODOS, MAQ["mac_vitrine"], PERF["fam_branca"])
    forte = [a for a in ex["alertas"] if a["codigo"] == "eritritol_30g"]
    assert forte and forte[0]["nivel"] == "forte" and "no lote" in forte[0]["texto"]
    assert "eritritol_ida" not in {a["codigo"] for a in ex["alertas"]}
    ex = nutricao.complementos(_erit(29), TODOS, MAQ["mac_vitrine"], PERF["fam_branca"])
    assert "eritritol_30g" not in {a["codigo"] for a in ex["alertas"]}


def test_eritritol_alerta_ida_e_peso():
    # 120 g/kg → 12 g por porção de 100 g > 11,7 g (70 kg), mas < 15 g (90 kg)
    ex = nutricao.complementos(_erit(120), TODOS, MAQ["mac_vitrine"], PERF["fam_branca"])
    assert "eritritol_ida" in {a["codigo"] for a in ex["alertas"]}
    ex = nutricao.complementos(_erit(120), TODOS, MAQ["mac_vitrine"], PERF["fam_branca"], peso_kg=90)
    assert "eritritol_ida" not in {a["codigo"] for a in ex["alertas"]}


def test_eritritol_na_ficha_md_e_pagina(capsys, tmp_path):
    p = gravar(tmp_path, receita_com([("ing_leite_int", 850), ("ing_creme_35", 100), ("ing_eritritol_estevia", 50)]))
    _, md, _ = rodar(capsys, "ficha", p)
    assert "Eritritol: 5,0 g por porção" in md
    _, md2, _ = rodar(capsys, "ficha", p, "--peso-kg", "45")
    assert "teto sugerido 7,5 g" in md2
    h = tmp_path / "e.html"
    rodar(capsys, "pagina", p, "-o", str(h))
    assert "Eritritol: 5,0 g por porção" in h.read_text(encoding="utf-8")
    _, txt, _ = rodar(capsys, "ficha", p, "--formato", "texto")
    assert "ritritol:" not in txt and "kcal" not in txt
    # sem eritritol: nenhuma linha de eritritol
    _, md3, _ = rodar(capsys, "ficha", "rec_fiordilatte")
    assert "Eritritol:" not in md3


def test_light_teto_de_eritritol_e_preferencia_por_alulose():
    itens = [{"ingrediente": "ing_leite_desn", "gramas": 800, "travado": True},
             {"ingrediente": "ing_whey_iso", "gramas": 40, "travado": True},
             {"ingrediente": "ing_eritritol_puro", "gramas": 160},
             {"ingrediente": "ing_alulose", "gramas": 0}]
    faixas = motor.faixas_alvo(PERF["fam_proteico"], MAQ["mac_creami"])
    f, _ = nutricao.objetivo_light(itens, TODOS, faixas)
    res = motor.balancear(itens, TODOS, faixas, funcao_objetivo=f)
    z = motor.avaliar(res["itens"], TODOS)
    erit_porcao = nutricao.nutricao(z, TODOS)["porcao"]["poliois_g"].get("eritritol", 0)
    assert erit_porcao <= nutricao.limite_eritritol_porcao() + 0.1
    g = {i["ingrediente"]: i["gramas"] for i in res["itens"]}
    assert g["ing_alulose"] > g["ing_eritritol_puro"]
    # porção maior = teto mais apertado em % da calda
    f2, _ = nutricao.objetivo_light(itens, TODOS, faixas, porcao_g=200)
    res2 = motor.balancear(itens, TODOS, faixas, funcao_objetivo=f2)
    z2 = motor.avaliar(res2["itens"], TODOS)
    assert nutricao.nutricao(z2, TODOS, 200)["porcao"]["poliois_g"].get("eritritol", 0) <= nutricao.limite_eritritol_porcao() + 0.1
