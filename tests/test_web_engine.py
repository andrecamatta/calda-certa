"""Testes de integridade da interface web (bundle de dados e motor JS)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from caldacerta import dados, motor, nutricao, relatorio

RAIZ = Path(__file__).resolve().parent.parent
BUNDLE = RAIZ / "web" / "data" / "bundle.json"
ENGINE_JS = RAIZ / "web" / "engine.js"


def test_bundle_sincronizado_com_pacote():
    assert BUNDLE.exists(), "web/data/bundle.json ausente (rode tools/sync_web_data.py)"
    b = json.loads(BUNDLE.read_text(encoding="utf-8"))
    assert b["ingredientes"] == dados.ingredientes()
    assert b["receitas"] == dados.receitas()
    assert b["maquinas"] == dados.maquinas()
    assert b["perfis"] == dados.perfis()
    assert b["constantes"] == dados.carregar_constantes()
    assert b["novidades"] == dados.novidades()


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js não disponível")
def test_engine_js_equivalente_ao_python():
    esperado = {}
    for r in dados.receitas_todos():
        maq = dados.achar(dados.maquinas(), r.get("maquina"), "maquina")
        perf = dados.achar_com_extras(dados.perfis(), dados.perfis_extra(), r.get("perfil"), "perfil")
        a = relatorio.analisar(r, maq, perf)
        esperado[r["id"]] = {
            "ideal": a["conformidade"]["ideal"],
            "ponto": a["ponto_congelamento_c"],
            "servir": a["temp_servir_ideal_c"],
            "kcal": a["nutricao"]["kcal_100g"],
            "alertas": [x["codigo"] for x in a["alertas"]],
            "correcoes": [[c["metrica"], c["ingrediente"], c["gramas"]] for c in a["correcoes"]],
        }

    r_prot = dados.achar(dados.receitas_todos(), "rec_proteico_baunilha", "receita")
    ings = dados.mapa_ingredientes_todos()
    maq = dados.achar(dados.maquinas(), r_prot["maquina"], "maquina")
    perf = dados.achar_com_extras(dados.perfis(), dados.perfis_extra(), r_prot["perfil"], "perfil")
    fx = motor.faixas_alvo(perf, maq)
    obj, _ = nutricao.objetivo_light(r_prot["itens"], ings, fx, r_prot.get("evaporada_g", 0))
    bal = motor.balancear(r_prot["itens"], ings, fx, r_prot.get("evaporada_g", 0), funcao_objetivo=obj)
    esperado["_light_prot"] = [i["gramas"] for i in bal["itens"]]

    script = f"""
import fs from "node:fs";
import * as eng from {json.dumps(ENGINE_JS.as_uri())};
const bundle = JSON.parse(fs.readFileSync({json.dumps(str(BUNDLE))}, "utf8"));
const cat = eng.construirCatalogo(bundle);
const py = JSON.parse(fs.readFileSync(0, "utf8"));
for (const r of cat.receitas) {{
  const a = eng.analisarReceita(r, cat);
  const exp = py[r.id];
  if (a.conformidade.ideal !== exp.ideal) throw new Error(`ideal ${{r.id}}`);
  if (Math.abs(a.ponto_congelamento_c - exp.ponto) > 1e-6) throw new Error(`ponto ${{r.id}}`);
  if (Math.abs(a.temp_servir_ideal_c - exp.servir) > 1e-6) throw new Error(`servir ${{r.id}}`);
  if (Math.abs(a.nutricao.kcal_100g - exp.kcal) > 1e-4) throw new Error(`kcal ${{r.id}}`);
  if (JSON.stringify(a.alertas.map(x => x.codigo)) !== JSON.stringify(exp.alertas)) throw new Error(`alertas ${{r.id}}`);
  if (JSON.stringify(a.correcoes.map(c => [c.metrica, c.ingrediente, c.gramas])) !== JSON.stringify(exp.correcoes)) throw new Error(`correcoes ${{r.id}}`);
}}
const rp = cat.receitas.find(x => x.id === "rec_proteico_baunilha");
const fx = eng.faixasAlvo(cat.mapaPerfis[rp.perfil], cat.mapaMaquinas[rp.maquina]);
const {{ objetivo }} = eng.objetivoLight(rp.itens, cat.mapaIngredientes, fx, cat.constantes, cat.constantesNov, rp.evaporada_g || 0);
const bal = eng.balancear(rp.itens, cat.mapaIngredientes, fx, rp.evaporada_g || 0, objetivo);
if (JSON.stringify(bal.itens.map(i => i.gramas)) !== JSON.stringify(py._light_prot)) {{
  throw new Error("light mismatch");
}}
"""
    proc = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        input=json.dumps(esperado),
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
