"""Equivalência com o motor JavaScript original.

Os fixtures em ``tests/fixtures/referencia_js.json`` foram gerados por
``node tools/gerar_fixtures.mjs``, que executa o trecho original do app
(``tools/referencia/motor_original.js``) sobre os dados de referência.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from caldacerta import dados, motor
from caldacerta.ficha import ficha_texto

REF = json.loads((Path(__file__).parent / "fixtures" / "referencia_js.json").read_text(encoding="utf-8"))
TOL = 1e-6

# app (inglês) -> arquivos de dados (português)
METRICAS = {
    "water": "agua", "fat": "gordura", "protein": "proteina", "sugars": "acucares", "msnf": "sng",
    "otherSolids": "outros_solidos", "totalSolids": "solidos_totais", "alcohol": "alcool",
    "lactose": "lactose", "msnfEq": "sng_lactose", "pod": "pod", "pac": "pac", "cost": "custo",
}
PERFIL_ACUCAR = {
    "sucrose": "sacarose", "glucose": "glicose", "fructose": "frutose", "maltose": "maltose",
    "trehalose": "trealose", "allulose": "alulose", "glucoseSyrup": "solidos_glicose",
    "maltodextrin": "maltodextrina", "erythritol": "eritritol", "sorbitol": "sorbitol",
    "xylitol": "xilitol", "maltitol": "maltitol", "inulin": "inulina", "polydextrose": "polidextrose",
    "citricAcid": "acidos_fruta", "lacticAcid": "acido_latico", "salt": "sal", "soluble": "outros_soluveis",
}
CAMPOS_ING = {
    "water": "agua", "fat": "gordura", "protein": "proteina", "sugars": "acucares", "msnf": "sng",
    "lactose": "lactose", "otherSolids": "outros_solidos", "alcohol": "alcool", "pod": "pod", "pac": "pac",
    "cost": "custo_kg", "autoPodPac": "pod_pac_auto",
}

ING = dados.mapa_ingredientes()
MAQ = {m["id"]: m for m in dados.maquinas()}
PERF = {p["id"]: p for p in dados.perfis()}


def perto(a, b):
    if a is None or b is None:
        return a is b
    if isinstance(b, bool):
        return a is b
    if math.isinf(b):
        return a == b
    return math.isclose(a, b, rel_tol=1e-12, abs_tol=TOL)


def traduz_ing(e):
    o = {CAMPOS_ING[k]: v for k, v in e.items() if k in CAMPOS_ING}
    o["perfil_acucares"] = {PERFIL_ACUCAR[k]: v for k, v in (e.get("profile") or {}).items()}
    return o


def traduz_faixas(ct):
    return {METRICAS[k]: v for k, v in ct.items()}


def test_contagens_dos_dados():
    assert len(ING) == 45
    assert len(dados.receitas()) == 24
    assert len(MAQ) == 4
    assert len(PERF) == 11


@pytest.mark.parametrize("caso", REF["ingredientes"], ids=lambda c: c["id"])
def test_ingrediente_pod_pac_e_avisos(caso):
    ing = traduz_ing(caso["ingrediente"]) if "ingrediente" in caso else ING[caso["id"]]
    assert motor.pod_pac_automatico(ing) == caso["rr"]
    assert perto(motor.sng_pela_lactose(ing), caso["vg"])
    avisos = motor.validar_ingrediente(ing)
    assert [(a["nivel"], a["texto"]) for a in avisos] == [(a["level"], a["text"]) for a in caso["avisos"]]


def test_curva_congelamento():
    for c in REF["curva"]:
        assert perto(motor.depressao_curva(c["pac10"]), c["Ig"]), c
        assert perto(motor.depressao(c["pac10"], c["msnf"], c["water"]), c["Dl"] if c["Dl"] is not None else math.inf), c
        assert perto(motor.fracao_congelada(c["pac10"], c["msnf"], c["water"], c["temp"]), c["Cg"]), c
        sg = c["Sg"] if c["Sg"] is not None else -math.inf
        assert perto(motor.temp_servir_ideal(c["pac10"], c["msnf"], c["water"]), sg), c


@pytest.mark.parametrize("caso", REF["avaliacoes"], ids=lambda c: f'{c["receita"]}-{c["maquina"]}-{c["evaporada"]}')
def test_avaliacao(caso):
    maq = MAQ[caso["maquina"]]
    z = motor.avaliar(caso["itens"], ING, maq["temp_servir"], caso["evaporada"])
    tot = caso["totals"]
    assert perto(z["totais"]["gramas"], tot["grams"])
    assert perto(z["totais"]["gramas_brutos"], tot["rawGrams"])
    assert perto(z["totais"]["evaporada"], tot["evaporation"])
    for k, v in tot.items():
        if k in METRICAS:
            assert perto(z["totais"][METRICAS[k]], v), k
    for k, v in caso["metrics"].items():
        assert perto(z["metricas"][METRICAS[k]], v), k
    s = caso["sandiness"]
    assert perto(z["arenosidade"]["valor"], s["value"])
    assert perto(z["arenosidade"]["maximo"], s["max"])
    assert z["arenosidade"]["ok"] is s["ok"]
    assert perto(z["ponto_congelamento"], caso["freezingPoint"])
    assert perto(z["fracao_congelada"], caso["frozenAtServe"])
    assert perto(z["temp_servir_ideal"], caso["scoopTemp"])
    assert perto(z["custo_kg"], caso["costPerKg"])
    assert len(z["linhas"]) == len(caso["rows"])
    for lp, lj in zip(z["linhas"], caso["rows"]):
        assert lp["conhecido"] is lj["conhecido"]
        assert perto(lp["gramas"], lj["grams"])
        for k, v in lj.items():
            if k in METRICAS:
                assert perto(lp[METRICAS[k]], v), k


def test_conformidade():
    cache = {}
    for c in REF["conformidade"]:
        chave = (c["receita"], c["maquina"])
        if chave not in cache:
            av = next(a for a in REF["avaliacoes"] if a["receita"] == c["receita"] and a["maquina"] == c["maquina"] and a["evaporada"] == 0)
            cache[chave] = motor.avaliar(av["itens"], ING, MAQ[c["maquina"]]["temp_servir"], 0)
        faixas = motor.faixas_alvo(PERF[c["perfil"]], MAQ[c["maquina"]])
        assert faixas == traduz_faixas(c["faixas"])
        conf = motor.conformidade(cache[chave]["metricas"], faixas)
        assert [p["status"] for p in conf["parametros"]] == c["status"]
        assert conf["ideal"] == c["ideal"]


@pytest.mark.parametrize("caso", REF["escalonamentos"], ids=lambda c: f'{c["receita"]}-{c["alvo"]}')
def test_escalonamento(caso):
    if caso["erro"]:
        with pytest.raises(ValueError):
            motor.escalonar(caso["itens"], ING, caso["alvo"], caso["evaporada"])
        return
    novo = motor.escalonar(caso["itens"], ING, caso["alvo"], caso["evaporada"])
    assert [i["gramas"] for i in novo] == [i["gramas"] for i in caso["resultado"]]


@pytest.mark.parametrize("caso", REF["fichas"], ids=lambda c: f'{c["receita"]}-{c["evaporada"]}')
def test_ficha_texto_identica(caso):
    txt = ficha_texto(
        caso["nome"], caso["versao"], caso["itens"], ING, PERF[caso["perfil"]], MAQ[caso["maquina"]], caso["evaporada"]
    )
    assert txt == caso["texto"]


@pytest.mark.parametrize(
    "caso", REF["balanceamentos"], ids=lambda c: f'{c["receita"]}-{c["maquina"]}-{c["perfil"]}-{c["evaporada"]}'
)
def test_balanceamento(caso):
    faixas = motor.faixas_alvo(PERF[caso["perfil"]], MAQ[caso["maquina"]])
    res = motor.balancear(caso["itens"], ING, faixas, caso["evaporada"])
    assert res["sucesso"] is caso["success"]
    assert res["mensagem"] == caso["message"]
    assert [i["gramas"] for i in res["itens"]] == [i["gramas"] for i in caso["resultado"]]
