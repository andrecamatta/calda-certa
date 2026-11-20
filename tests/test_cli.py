"""Testes da CLI (com CALDA_DADOS num diretório temporário)."""

from __future__ import annotations

import json
import shutil

import pytest

from caldacerta import dados
from caldacerta.cli import main


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


def test_listas(capsys):
    assert len(rodar_json(capsys, "ingredientes")) == 45
    assert len(rodar_json(capsys, "receitas")) == 24
    assert len(rodar_json(capsys, "maquinas")) == 4
    assert len(rodar_json(capsys, "perfis")) == 11
    leites = rodar_json(capsys, "ingredientes", "--busca", "leite", "--familia", "lacteos")
    assert leites and all(i["categoria"] == "Lácteos" for i in leites)
    # --json também depois do subcomando
    code, out, _ = rodar(capsys, "maquinas", "--json")
    assert json.loads(out)[0]["id"] == "mac_kitchenaid_hora"


def test_analisar_json(capsys):
    a = rodar_json(capsys, "analisar", "rec_fiordilatte")
    assert a["conformidade"]["ideal"] == 8
    assert a["maquina"]["ajuste_pac"] == 40
    assert a["faixas"]["pac"] == [280, 320]
    assert a["custo"]["por_kg"] > 0
    b = rodar_json(capsys, "analisar", "rec_fiordilatte", "--maquina", "mac_vitrine", "--lote", "500", "--evaporada", "10")
    assert b["faixas"]["pac"] == [240, 280]
    assert b["totais"]["evaporada"] == 10
    assert b["escalonada_para_g"] == 500


def test_analisar_arquivo_formato_app(capsys, tmp_path):
    p = tmp_path / "r.json"
    p.write_text(json.dumps({
        "name": "X", "version": "V1", "familyId": "fam_sorbet", "machineId": "mac_creami",
        "items": [{"ingredientId": "ing_polpa_manga", "grams": 600, "locked": True},
                  {"ingredientId": "ing_sacarose", "grams": 200}, {"ingredientId": "ing_agua", "grams": 200}],
    }), encoding="utf-8")
    a = rodar_json(capsys, "analisar", str(p))
    assert a["perfil"]["id"] == "fam_sorbet"
    assert a["linhas"][0]["travado"] is True


def test_balancear_e_salvar(capsys, tmp_path):
    out = tmp_path / "bal.json"
    r = rodar_json(capsys, "balancear", "rec_choc70", "--maquina", "mac_kitchenaid_freezer", "--travar", "ing_leite_int", "-o", str(out))
    assert r["receita"]["itens"][0]["travado"] is True
    assert r["receita"]["itens"][0]["gramas"] == 278
    salvo = json.loads(out.read_text(encoding="utf-8"))
    assert salvo == r["receita"]
    s = rodar_json(capsys, "receita", "salvar", str(out), "--id", "rec_choc70_ka")
    assert s["receita"]["id"] == "rec_choc70_ka" and s["receita"]["status"] == "Em Teste"
    assert any(x["id"] == "rec_choc70_ka" for x in dados.receitas())
    # gravou só no diretório do usuário
    assert (dados.dir_usuario() / "receitas.json").exists()


def test_balancear_sem_destravados(capsys):
    code, out, err = rodar(capsys, "--json", "balancear", "rec_fiordilatte", "--travar",
                           "ing_leite_int,ing_creme_35,ing_leite_po_desn,ing_sacarose,ing_dextrose,ing_glicose_po")
    assert code == 1 and "Destrave" in json.loads(err)["erro"]


def test_ficha_texto_e_md(capsys, tmp_path):
    code, out, _ = rodar(capsys, "ficha", "rec_fiordilatte", "--formato", "texto")
    assert code == 0 and out.startswith("Fior di Latte (V1.0) — Gelato · Base Branca")
    assert "Custo\tR$ 13,00/kg" in out
    md = tmp_path / "f.md"
    code, out, _ = rodar(capsys, "ficha", "rec_fiordilatte", "-o", str(md))
    assert md.read_text(encoding="utf-8").startswith("# Fior di Latte (V1.0)")


def test_pagina_html_autocontida(capsys, tmp_path):
    p = tmp_path / "x.html"
    code, _, _ = rodar(capsys, "pagina", "rec_frances_baunilha", "--evaporada", "50", "-o", str(p))
    html = p.read_text(encoding="utf-8")
    assert code == 0
    assert "<script" not in html and "http://" not in html and "https://" not in html
    assert 'name="viewport"' in html and "prefers-color-scheme:dark" in html
    assert "Sorvete Francês" in html


def test_ingrediente_crud(capsys, dados_temporarios):
    r = rodar_json(capsys, "ingrediente", "adicionar", "--nome", "Xarope de Bordo", "--categoria", "Açúcares",
                   "--agua", "32", "--acucares", "67", "--outros-solidos", "1",
                   "--perfil-acucares", "sacarose=60,glicose=4,frutose=3", "--custo-kg", "120")
    ing = r["ingrediente"]
    assert ing["id"] == "ing_custom_xarope_de_bordo"
    assert (ing["pod"], ing["pac"]) == (67.9, 73.3)
    assert dados.ingredientes()[0]["id"] == ing["id"]
    # pacote não foi alterado
    assert all(i["id"] != ing["id"] for i in json.loads((dados.PACOTE / "ingredientes.json").read_text(encoding="utf-8")))
    e = rodar_json(capsys, "ingrediente", "editar", ing["id"], "--pod-pac-manual", "--pod", "70", "--pac", "80")
    assert (e["ingrediente"]["pod"], e["ingrediente"]["pac"]) == (70, 80)
    code, _, err = rodar(capsys, "ingrediente", "adicionar", "--nome", "Ruim", "--agua", "50")
    assert code == 1 and "precisa dar 100%" in err
    code, _, err = rodar(capsys, "ingrediente", "remover", "ing_sacarose")
    assert code == 1 and "--forcar" in err
    rodar_json(capsys, "ingrediente", "remover", ing["id"])
    assert len(dados.ingredientes()) == 45


def test_erro_receita_inexistente(capsys):
    code, _, err = rodar(capsys, "--json", "analisar", "nao_existe")
    assert code == 1 and "erro" in json.loads(err)
