"""Relatório HTML estático e autocontido (CSS embutido, sem JS, sem
requisições externas), legível no celular e com tema claro/escuro."""

from __future__ import annotations

from html import escape
from typing import Mapping

from . import nutricao
from .jsnum import br

CSS = """
:root{--bg:#f6f7f9;--card:#fff;--tx:#17202a;--mut:#5d6b7a;--ln:#e3e7ec;--ok:#1f7a4d;--okbg:#e6f4ec;
--lo:#a15c00;--lobg:#fdf1de;--hi:#b0283b;--hibg:#fbe7ea;--band:#cfe9da;--mark:#17202a;--acc:#0b6fa4}
@media (prefers-color-scheme:dark){:root{--bg:#11161c;--card:#1a2129;--tx:#e7ecf1;--mut:#9aa8b6;--ln:#2a3440;
--ok:#6fd3a0;--okbg:#173527;--lo:#f0b55c;--lobg:#3a2b12;--hi:#f2899a;--hibg:#3d1c22;--band:#24503a;--mark:#e7ecf1;--acc:#6cc3f0}}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--tx);font:15px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:860px;margin:0 auto;padding:16px}
h1{font-size:1.45rem;margin:.2rem 0}h2{font-size:1.05rem;margin:0 0 .6rem}
.sub{color:var(--mut);font-size:.9rem;margin:0}
.card{background:var(--card);border:1px solid var(--ln);border-radius:14px;padding:14px 16px;margin:14px 0}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:14px 0}
.kpi{background:var(--card);border:1px solid var(--ln);border-radius:14px;padding:12px 14px}
.kpi b{display:block;font-size:1.35rem;font-variant-numeric:tabular-nums}
.kpi span{color:var(--mut);font-size:.78rem;text-transform:uppercase;letter-spacing:.04em}
.kpi small{color:var(--mut);display:block;font-size:.8rem}
table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}
th,td{padding:6px 4px;border-bottom:1px solid var(--ln);text-align:right;vertical-align:top}
th:first-child,td:first-child{text-align:left}th{color:var(--mut);font-weight:600;font-size:.8rem}
tfoot td{font-weight:700;border-bottom:0}
.scroll{overflow-x:auto}
.met{display:grid;grid-template-columns:1fr auto;gap:2px 10px;padding:9px 0;border-bottom:1px solid var(--ln)}
.met:last-child{border-bottom:0}.met .v{font-weight:700;font-variant-numeric:tabular-nums}
.bar{grid-column:1/3;position:relative;height:8px;border-radius:4px;background:var(--ln);margin:4px 0 2px}
.bar i{position:absolute;top:0;bottom:0;background:var(--band);border-radius:4px}
.bar u{position:absolute;top:-3px;width:3px;height:14px;background:var(--mark);border-radius:2px;margin-left:-1px}
.rng{grid-column:1/3;color:var(--mut);font-size:.8rem}
.tag{display:inline-block;font-size:.72rem;font-weight:700;padding:1px 8px;border-radius:99px;margin-left:6px}
.IDEAL{color:var(--ok);background:var(--okbg)}.ABAIXO{color:var(--lo);background:var(--lobg)}.ACIMA{color:var(--hi);background:var(--hibg)}
.alert{border-radius:12px;padding:10px 12px;margin:10px 0;font-size:.9rem}
.alert.ok{background:var(--okbg);color:var(--ok)}.alert.bad{background:var(--hibg);color:var(--hi)}
.score{font-size:1rem;font-weight:700;color:var(--acc)}
ul{padding-left:1.2rem;margin:.3rem 0}footer{color:var(--mut);font-size:.78rem;margin:18px 0 8px}
"""


def _f(x, c=1):
    return escape(br(x, c))


def gerar_html(a: Mapping, ficha: str | None = None) -> str:
    """Gera o HTML a partir do resultado de ``relatorio.analisar``."""
    r, m, p, t = a["receita"], a["maquina"], a["perfil"], a["totais"]
    conf = a["conformidade"]
    ar = a["arenosidade"]
    e = escape
    h = ["<!doctype html>", '<html lang="pt-BR"><head><meta charset="utf-8">',
         '<meta name="viewport" content="width=device-width,initial-scale=1">',
         f"<title>{e(r['nome'])} ({e(r['versao'])}) · Calda Certa</title>", f"<style>{CSS}</style></head><body><main>"]
    h.append(f"<p class=\"sub\">Calda Certa · ficha de balanceamento</p><h1>{e(r['nome'])} <small>({e(r['versao'])})</small></h1>")
    h.append(f"<p class=\"sub\">{e(p['nome'])} · {e(m['nome'])}</p>")
    h.append(f"<p class=\"score\">Faixa verde: {conf['ideal']}/{conf['total']} parâmetros</p>")
    if r.get("notas"):
        h.append(f"<p class=\"sub\">{e(str(r['notas']))}</p>")

    h.append('<div class="kpis">')
    h.append(f'<div class="kpi"><span>Ponto de congelamento</span><b>{_f(a["ponto_congelamento_c"])} °C</b><small>Onde o primeiro gelo se forma</small></div>')
    h.append(f'<div class="kpi"><span>Bom para servir a</span><b>{_f(a["temp_servir_ideal_c"])} °C</b>'
             f'<small>A {e(str(m["temp_servir"]))} °C: {_f(a["fracao_agua_congelada_na_maquina"] * 100, 0)}% da água em gelo</small></div>')
    h.append(f'<div class="kpi"><span>Custo insumos</span><b>R$ {_f(a["custo"]["por_kg"], 2)}/kg</b><small>Lote atual: R$ {_f(a["custo"]["lote"], 2)}</small></div>')
    h.append(f'<div class="kpi"><span>Peso final</span><b>{_f(t["gramas"])} g</b>'
             + (f'<small>{_f(t["evaporada"])} g de água evaporada</small>' if t["evaporada"] > 0 else "<small>sem evaporação</small>")
             + "</div></div>")

    # Ingredientes
    h.append('<section class="card"><h2>Ingredientes</h2><div class="scroll"><table><thead><tr>'
             "<th>Ingrediente</th><th>g</th><th>%</th><th>Gord.</th><th>Açúc.</th><th>ST</th><th>R$</th></tr></thead><tbody>")
    for l in a["linhas"]:
        nome = e(l["nome"]) if l["nome"] else f"{e(str(l['ingrediente']))} <em>(fora do banco)</em>"
        trav = " <small>(travado)</small>" if l["travado"] else ""
        h.append(f"<tr><td>{nome}{trav}</td><td>{_f(l['gramas'])}</td><td>{_f(l['pct'])}</td><td>{_f(l['gordura'])}</td>"
                 f"<td>{_f(l['acucares'])}</td><td>{_f(l['solidos_totais'])}</td><td>{_f(l['custo'], 2)}</td></tr>")
    h.append(f"</tbody><tfoot><tr><td>TOTAL</td><td>{_f(t['gramas'])}</td><td>100</td><td>{_f(t['gordura'])}</td>"
             f"<td>{_f(t['acucares'])}</td><td>{_f(t['solidos_totais'])}</td><td>{_f(t['custo'], 2)}</td></tr></tfoot></table></div></section>")

    # Dashboard
    h.append(f'<section class="card"><h2>Balanceamento</h2><p class="sub">Faixa verde: <strong>{e(p["nome"])}</strong> na <strong>{e(m["nome_curto"])}</strong>.</p>')
    cls = "ok" if ar["ok"] else "bad"
    h.append(f'<div class="alert {cls}"><strong>{"Sem risco de arenosidade" if ar["ok"] else "Risco de arenosidade"}:</strong> '
             f'SNLG pela lactose {_f(ar["valor"])}% · limite desta receita {_f(ar["maximo"])}%.'
             + ("" if ar["ok"] else " Reduza leite em pó ou doce de leite/leite condensado.") + "</div>")
    if a["metricas"]["alcool"] > 0.05:
        h.append(f'<div class="alert bad">Álcool: {_f(a["metricas"]["alcool"])}% do peso (já incluído no PAC). Acima de ~2–3% o sorvete pode não firmar.</div>')
    for q in conf["parametros"]:
        c = q["casas"]
        lo, hi, v = q["min"], q["max"], q["valor"]
        span = max(hi - lo, 1e-9)
        a0, a1 = lo - span * 0.6, hi + span * 0.6
        pos = lambda x: max(0.0, min(100.0, (x - a0) / (a1 - a0) * 100))
        st = {"IDEAL": "na faixa", "ABAIXO": "abaixo", "ACIMA": "acima"}[q["status"]]
        h.append(f'<div class="met"><div>{e(q["rotulo"])}<span class="tag {q["status"]}">{st}</span></div>'
                 f'<div class="v">{_f(v, c)} {e(q["unidade"])}</div>'
                 f'<div class="bar"><i style="left:{pos(lo):.2f}%;width:{pos(hi) - pos(lo):.2f}%"></i><u style="left:{pos(v):.2f}%"></u></div>'
                 f'<div class="rng">faixa {_f(lo, c)}–{_f(hi, c)}' + (f" · {e(q['dica'])}" if q["dica"] else "") + "</div></div>")
    h.append("</section>")

    h.append(f'<section class="card"><h2>Máquina: {e(m["nome"])}</h2><p class="sub">PAC alvo '
             f'{"+" + str(m["ajuste_pac"]) if m["ajuste_pac"] > 0 else "±0"} pts sobre a vitrine · referência {e(str(m["temp_servir"]))} °C · {e(m["nota_lote"])}</p></section>')
    h += _secoes_novidades(a)
    if ficha:
        h.append(f'<section class="card"><h2>Ficha técnica (texto)</h2><div class="scroll"><pre>{e(ficha)}</pre></div></section>')
    h.append("<footer>Gerado pelo Calda Certa (CLI). Valores de composição são médias de referência: confira o rótulo dos seus insumos.</footer>")
    h.append("</main></body></html>")
    return "\n".join(h) + "\n"


def _secoes_novidades(a: Mapping) -> list[str]:
    """Cartões novos: nutrição, alertas, correções, máquina e lembretes."""
    e = escape
    h: list[str] = []
    if "nutricao" not in a:
        return h
    n = a["nutricao"]
    h.append('<section class="card"><h2>Nutrição (estimativa)</h2><div class="kpis">')
    h.append(f'<div class="kpi"><span>Energia</span><b>{_f(n["kcal_100g"], 0)} kcal</b><small>por 100 g</small></div>')
    h.append(f'<div class="kpi"><span>Porção {_f(n["porcao"]["gramas"], 0)} g</span><b>{_f(n["porcao"]["kcal"], 0)} kcal</b>'
             f'<small>{_f(n["porcao"]["proteina_g"])} g de proteína</small></div>')
    if n.get("pote") and a.get("pote"):
        h.append(f'<div class="kpi"><span>Pote (~{_f(a["pote"]["gramas"], 0)} g)</span><b>{_f(n["pote"]["kcal"], 0)} kcal</b>'
                 f'<small>{_f(n["pote"]["proteina_g"])} g de proteína</small></div>')
    h.append("</div><ul>" + "".join(f"<li>{e(l)}</li>" for l in nutricao.linhas_nutricao(n, a.get("pote"), a.get("limite_eritritol_porcao_g"))) + "</ul></section>")
    if a.get("comparacao_classica"):
        h.append(f'<section class="card"><h2>Comparação com o padrão clássico</h2><p>{e(nutricao.linha_comparacao(a["comparacao_classica"]))}</p></section>')
    if a.get("ajustes_brix"):
        h.append('<section class="card"><h2>Brix medido</h2><ul>'
                 + "".join(f"<li>{e(x['texto'])}</li>" for x in a["ajustes_brix"]) + "</ul></section>")
    if a.get("alertas"):
        h.append('<section class="card"><h2>Alertas</h2>'
                 + "".join(f'<div class="alert bad">{"<strong>" + e(x["texto"]) + "</strong>" if x["nivel"] == "forte" else e(x["texto"])}</div>'
                         for x in a["alertas"]) + "</section>")
    if a.get("correcoes"):
        h.append('<section class="card"><h2>Correções de um ingrediente</h2><p class="sub">Estimativa: cada linha é uma alternativa.</p><ul>'
                 + "".join(f"<li>{e(nutricao.linha_correcao(c))}</li>" for c in a["correcoes"]) + "</ul></section>")
    if a.get("orientacoes_maquina"):
        h.append('<section class="card"><h2>Pote e congelamento</h2><ul>'
                 + "".join(f"<li>{e(o)}</li>" for o in a["orientacoes_maquina"]) + "</ul></section>")
    if a.get("lembretes"):
        h.append('<section class="card"><h2>Lembretes de processo</h2><ul>'
                 + "".join(f"<li>{e(l)}</li>" for l in a["lembretes"]) + "</ul></section>")
    return h
