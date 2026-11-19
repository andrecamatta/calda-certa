"""Testes de unidade e casos de borda do motor."""

from __future__ import annotations

import math

import pytest

from caldacerta import dados, motor
from caldacerta.jsnum import br, js_round, numero, to_fixed

ING = dados.mapa_ingredientes()
PERF = {p["id"]: p for p in dados.perfis()}
MAQ = {m["id"]: m for m in dados.maquinas()}


def test_js_round_meio_para_cima():
    assert js_round(2.5) == 3
    assert js_round(-2.5) == -2
    assert js_round(0.49999999999999994) == 0
    assert js_round(1.45 * 10) / 10 == 1.5


def test_to_fixed_como_js():
    assert to_fixed(0.5, 0) == "1"  # Python format daria "0"
    assert to_fixed(0.25, 1) == "0.3"
    assert to_fixed(1.005, 2) == "1.00"  # 1.005 é 1.00499... em binário
    assert to_fixed(-0.0, 1) == "0.0"
    assert to_fixed(-0.04, 1) == "-0.0"
    assert br(12.345, 2) == "12,35" or br(12.345, 2) == "12,34"


def test_numero_coercao():
    assert numero(None) == 0 and numero("") == 0 and numero("abc") == 0
    assert numero("12.5") == 12.5 and numero(True) == 1 and numero(float("nan")) == 0


def test_receita_vazia():
    z = motor.avaliar([], ING)
    assert z["totais"]["gramas"] == 0
    assert all(v == 0 for v in z["metricas"].values())
    assert z["ponto_congelamento"] == 0 and z["fracao_congelada"] == 0 and z["temp_servir_ideal"] == 0
    assert z["custo_kg"] == 0


def test_ingrediente_desconhecido_conta_so_no_peso():
    z = motor.avaliar([{"ingrediente": "ing_sacarose", "gramas": 100}, {"ingrediente": "xyz", "gramas": 100}], ING)
    assert z["totais"]["gramas"] == 200
    assert z["metricas"]["acucares"] == 50
    assert z["linhas"][1]["conhecido"] is False


def test_gramas_negativas_ou_invalidas_viram_zero():
    z = motor.avaliar([{"ingrediente": "ing_sacarose", "gramas": -5}, {"ingrediente": "ing_agua", "gramas": "abc"}], ING)
    assert z["totais"]["gramas"] == 0


def test_agua_pura_congela_a_zero_e_sacarose_baixa_o_ponto():
    z = motor.avaliar([{"ingrediente": "ing_agua", "gramas": 1000}], ING)
    assert z["ponto_congelamento"] == 0
    assert z["fracao_congelada"] > 0.99
    z2 = motor.avaliar([{"ingrediente": "ing_agua", "gramas": 800}, {"ingrediente": "ing_sacarose", "gramas": 200}], ING)
    # PAC 200 pts/kg -> 25 g de sacarose equivalente por 100 g de água -> ~-1,54 °C
    assert z2["ponto_congelamento"] == pytest.approx(-1.5366666666666666)


def test_evaporacao_limitada_a_agua_total():
    itens = [{"ingrediente": "ing_sacarose", "gramas": 100}, {"ingrediente": "ing_agua", "gramas": 50}]
    z = motor.avaliar(itens, ING, evaporada=500)
    assert z["totais"]["evaporada"] == 50
    assert z["totais"]["gramas"] == 100
    assert z["metricas"]["agua"] == 0


def test_evaporacao_concentra_solidos():
    r = dados.receitas()[0]
    a = motor.avaliar(r["itens"], ING)
    b = motor.avaliar(r["itens"], ING, evaporada=100)
    assert b["metricas"]["solidos_totais"] > a["metricas"]["solidos_totais"]
    assert math.isclose(b["totais"]["custo"], a["totais"]["custo"])
    assert b["custo_kg"] > a["custo_kg"]


def test_arenosidade_limite():
    itens = [{"ingrediente": "ing_leite_po_desn", "gramas": 300}, {"ingrediente": "ing_agua", "gramas": 700}]
    z = motor.avaliar(itens, ING)
    assert z["arenosidade"]["ok"] is False
    assert z["arenosidade"]["maximo"] == pytest.approx((100 - z["metricas"]["outros_solidos"] - z["metricas"]["gordura"]) * 0.15)


def test_ajuste_pac_da_maquina():
    f = motor.faixas_alvo(PERF["fam_branca"], MAQ["mac_kitchenaid_freezer"])
    assert f["pac"] == [280, 320]
    assert motor.faixas_alvo(PERF["fam_branca"], MAQ["mac_vitrine"])["pac"] == [240, 280]
    assert motor.faixas_alvo(PERF["fam_branca"], None)["pac"] == [240, 280]


def test_conformidade_tolerancia_001():
    faixas = {k: [0, 1] for k in motor.CHAVES_BALANCO}
    m = {k: 1.01 for k in motor.CHAVES_BALANCO}
    assert motor.conformidade(m, faixas)["ideal"] == 8
    m = {k: 1.0101 for k in motor.CHAVES_BALANCO}
    c = motor.conformidade(m, faixas)
    assert c["ideal"] == 0 and all(p["status"] == "ACIMA" and p["dica"] for p in c["parametros"])


def test_receitas_exemplo_8_de_8_na_maquina_propria():
    for r in dados.receitas():
        z = motor.avaliar(r["itens"], ING, MAQ[r["maquina"]]["temp_servir"])
        c = motor.conformidade(z["metricas"], motor.faixas_alvo(PERF[r["perfil"]], MAQ[r["maquina"]]))
        assert c["ideal"] >= 7, r["id"]


def test_escalonar():
    r = dados.receitas()[0]
    novo = motor.escalonar(r["itens"], ING, 500)
    assert sum(i["gramas"] for i in novo) == pytest.approx(500, abs=0.5)
    with pytest.raises(ValueError):
        motor.escalonar(r["itens"], ING, 0)
    with pytest.raises(ValueError):
        motor.escalonar([], ING, 100)


def test_balancear_respeita_travas_e_massa():
    r = dados.receitas()[2]
    itens = [dict(i) for i in r["itens"]]
    itens[0]["travado"] = True
    faixas = motor.faixas_alvo(PERF["fam_branca"], MAQ["mac_vitrine"])
    res = motor.balancear(itens, ING, faixas)
    assert res["sucesso"]
    for a, b in zip(itens, res["itens"]):
        if a["travado"]:
            assert a["gramas"] == b["gramas"]
    assert sum(i["gramas"] for i in res["itens"]) == pytest.approx(sum(i["gramas"] for i in itens), abs=0.05)
    assert res["objetivo_final"] <= res["objetivo_inicial"]


def test_balancear_erros():
    faixas = motor.faixas_alvo(PERF["fam_branca"], MAQ["mac_vitrine"])
    one = [{"ingrediente": "ing_sacarose", "gramas": 100, "travado": False}, {"ingrediente": "ing_agua", "gramas": 100, "travado": True}]
    assert motor.balancear(one, ING, faixas)["mensagem"] == motor.MSG_POUCOS_DESTRAVADOS
    zero = [{"ingrediente": "ing_sacarose", "gramas": 0}, {"ingrediente": "ing_agua", "gramas": 0}]
    assert motor.balancear(zero, ING, faixas)["mensagem"] == motor.MSG_MASSA_ZERO
    # ingrediente fora do banco não é mexido pelo otimizador
    fora = [{"ingrediente": "xyz", "gramas": 10}, {"ingrediente": "ing_sacarose", "gramas": 100}]
    assert motor.balancear(fora, ING, faixas)["sucesso"] is False


def test_pod_pac_automatico_bate_com_banco():
    # todo ingrediente com pod_pac_auto tem POD/PAC iguais ao recalculado pelo perfil
    for i in ING.values():
        if i["pod_pac_auto"]:
            assert motor.pod_pac_automatico(i) == {"pod": i["pod"], "pac": i["pac"]}, i["id"]


def test_validar_ingrediente_soma():
    av = motor.validar_ingrediente({"agua": 50, "gordura": 10})
    assert av[0]["nivel"] == "error" and "60.0%" in av[0]["texto"]
    assert not [a for a in motor.validar_ingrediente(ING["ing_leite_int"]) if a["nivel"] == "error"]
