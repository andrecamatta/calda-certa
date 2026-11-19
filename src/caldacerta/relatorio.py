"""Análise completa (o "dashboard" do app) e sua renderização em texto."""

from __future__ import annotations

from typing import Any, Mapping

from . import dados
from .jsnum import br
from .motor import avaliar, conformidade, escalonar, faixas_alvo


def analisar(
    receita: Mapping[str, Any],
    maquina: Mapping[str, Any],
    perfil: Mapping[str, Any],
    evaporada: float | None = None,
    lote: float | None = None,
    ingredientes: Mapping[str, Mapping] | None = None,
) -> dict:
    """Avalia a receita na máquina/perfil escolhidos.

    ``evaporada`` (g) sobrepõe ``receita["evaporada_g"]``. ``lote`` (g), se
    dado, escala a receita antes (como o botão "Escalonar" do app)."""
    ings = ingredientes if ingredientes is not None else dados.mapa_ingredientes()
    evap = receita.get("evaporada_g", 0) if evaporada is None else evaporada
    itens = [dict(i) for i in receita["itens"]]
    escalada = False
    if lote is not None:
        itens = escalonar(itens, ings, lote, evap)
        escalada = True
    z = avaliar(itens, ings, maquina["temp_servir"], evap)
    faixas = faixas_alvo(perfil, maquina)
    conf = conformidade(z["metricas"], faixas)
    rec = dict(receita)
    rec["itens"] = itens
    rec["evaporada_g"] = evap
    if escalada:
        rec["lote_g"] = lote
    return {
        "receita": rec,
        "escalonada_para_g": lote if escalada else None,
        "maquina": {k: maquina[k] for k in ("id", "nome", "nome_curto", "ajuste_pac", "temp_servir", "lote_g", "nota_lote")},
        "perfil": {k: perfil[k] for k in ("id", "grupo", "nome", "descricao")},
        "faixas": faixas,
        "linhas": [_linha_publica(l, z["totais"]["gramas"]) for l in z["linhas"]],
        "totais": z["totais"],
        "metricas": z["metricas"],
        "conformidade": conf,
        "arenosidade": z["arenosidade"],
        "ponto_congelamento_c": z["ponto_congelamento"],
        "temp_servir_maquina_c": z["temp_servir"],
        "fracao_agua_congelada_na_maquina": z["fracao_congelada"],
        "temp_servir_ideal_c": z["temp_servir_ideal"],
        "custo": {"por_kg": z["custo_kg"], "lote": z["totais"]["custo"]},
    }


def _linha_publica(l: Mapping, total: float) -> dict:
    out = {k: v for k, v in l.items() if k not in ("travado",)}
    out["travado"] = bool(l.get("travado"))
    out["pct"] = (l["gramas"] / (total or 1)) * 100
    return out


_SIMB = {"IDEAL": "ok", "ABAIXO": "BAIXO", "ACIMA": "ALTO"}


def texto(a: Mapping) -> str:
    """Dashboard em texto simples (para humanos no terminal)."""
    r, m, p = a["receita"], a["maquina"], a["perfil"]
    conf = a["conformidade"]
    t = a["totais"]
    out = [f"{r['nome']} ({r['versao']})", f"Perfil: {p['nome']}", f"Máquina: {m['nome']}"]
    aj = m["ajuste_pac"]
    out.append(f"PAC alvo {'+' + str(aj) if aj > 0 else '±0'} pts sobre a vitrine · referência {m['temp_servir']} °C")
    if a["escalonada_para_g"] is not None:
        out.append(f"Escalonada para {br(a['escalonada_para_g'])} g")
    out.append("")
    nome_w = max([len(l["nome"] or str(l["ingrediente"])) for l in a["linhas"]] + [11])
    out.append(f"{'Ingrediente'.ljust(nome_w)}  {'g':>8}  {'%':>6}  trav.")
    for l in a["linhas"]:
        nome = l["nome"] or f"{l['ingrediente']} (fora do banco)"
        out.append(f"{nome.ljust(nome_w)}  {br(l['gramas'], 1):>8}  {br(l['pct'], 1):>6}  {'sim' if l['travado'] else ''}")
    out.append(f"{'TOTAL'.ljust(nome_w)}  {br(t['gramas'], 1):>8}  {'100':>6}")
    if t["evaporada"] > 0:
        out.append(f"Água evaporada: {br(t['evaporada'], 1)} g (bruto {br(t['gramas_brutos'], 1)} g); os % já consideram a perda.")
    out.append("")
    out.append(f"Faixa verde: {conf['ideal']}/{conf['total']}")
    for q in conf["parametros"]:
        c = q["casas"]
        out.append(
            f"  {q['rotulo']:<24} {br(q['valor'], c):>7} {q['unidade']:<6}  faixa {br(q['min'], c)}–{br(q['max'], c)}  {_SIMB[q['status']]}"
        )
    out.append("")
    ar = a["arenosidade"]
    out.append(
        f"{'Sem risco de arenosidade' if ar['ok'] else 'Risco de arenosidade'}: SNLG pela lactose {br(ar['valor'], 1)}% · limite {br(ar['maximo'], 1)}%"
    )
    if a["metricas"]["alcool"] > 0.05:
        out.append(f"Álcool: {br(a['metricas']['alcool'], 1)}% do peso (já incluído no PAC). Acima de ~2–3% pode não firmar.")
    out.append(f"Ponto de congelamento: {br(a['ponto_congelamento_c'], 1)} °C")
    out.append(f"Bom para servir a: {br(a['temp_servir_ideal_c'], 1)} °C")
    out.append(f"A {m['temp_servir']} °C: {br(a['fracao_agua_congelada_na_maquina'] * 100, 0)}% da água em gelo")
    out.append(f"Custo: R$ {br(a['custo']['por_kg'], 2)}/kg · lote atual R$ {br(a['custo']['lote'], 2)}")
    dicas = [q for q in conf["parametros"] if q["dica"]]
    if dicas:
        out.append("")
        out.append("Ajustes sugeridos:")
        out += [f"  - {q['rotulo']}: {q['dica']}" for q in dicas]
        if not ar["ok"]:
            out.append("  - Arenosidade: reduza leite em pó ou doce de leite/leite condensado.")
    return "\n".join(out)
