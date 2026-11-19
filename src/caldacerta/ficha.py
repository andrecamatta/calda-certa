"""Ficha técnica: o texto do botão "Copiar ficha" do app (``Vc``) e uma
versão em Markdown com o mesmo conteúdo, pronta para salvar como nota."""

from __future__ import annotations

from typing import Mapping, Sequence

from .dados import carregar_constantes
from .jsnum import br
from .motor import avaliar, conformidade, faixas_alvo


def ficha_texto(
    nome: str,
    versao: str,
    itens: Sequence[Mapping],
    ingredientes: Mapping[str, Mapping],
    perfil: Mapping,
    maquina: Mapping,
    evaporada: float = 0,
) -> str:
    """Reproduz exatamente o texto copiado pelo app (separado por tabulações)."""
    z = avaliar(itens, ingredientes, maquina["temp_servir"], evaporada)
    ct = faixas_alvo(perfil, maquina)
    k = carregar_constantes()
    linhas = [f"{nome} ({versao}) — {perfil['nome']} — {maquina['nome']}", "\t".join(["Ingrediente", "g", "%"])]
    e = z["totais"]["gramas"] or 1
    for row in z["linhas"]:
        if row["conhecido"]:
            linhas.append("\t".join([row["nome"], br(row["gramas"]), br((row["gramas"] / e) * 100)]))
    linhas.append("\t".join(["TOTAL", br(z["totais"]["gramas"]), "100"]))
    linhas.append("")
    for md in k["metricas"]:
        v = z["metricas"][md["chave"]]
        lo, hi = ct[md["chave"]]
        c = md["casas"]
        linhas.append("\t".join([md["rotulo"], f"{br(v, c)} {md['unidade']}", f"faixa {br(lo, c)}–{br(hi, c)}"]))
    if z["totais"]["evaporada"] > 0:
        linhas.append(
            f"Água evaporada no cozimento\t{br(z['totais']['evaporada'])} g (peso final {br(z['totais']['gramas'])} g)"
        )
    linhas.append(f"SNLG pela lactose (arenosidade)\t{br(z['arenosidade']['valor'])}%\tlimite {br(z['arenosidade']['maximo'])}%")
    linhas.append(f"Ponto de congelamento\t{br(z['ponto_congelamento'])} °C")
    linhas.append(f"Servir a (~72% da água congelada)\t{br(z['temp_servir_ideal'])} °C")
    linhas.append(f"Custo\tR$ {br(z['custo_kg'], 2)}/kg")
    return "\n".join(linhas)


def _md_cel(s: str) -> str:
    return str(s).replace("|", "\\|")


def ficha_markdown(
    nome: str,
    versao: str,
    itens: Sequence[Mapping],
    ingredientes: Mapping[str, Mapping],
    perfil: Mapping,
    maquina: Mapping,
    evaporada: float = 0,
    notas: str | None = None,
) -> str:
    """Mesmo conteúdo da ficha do app, em Markdown (tabelas + status da faixa)."""
    z = avaliar(itens, ingredientes, maquina["temp_servir"], evaporada)
    ct = faixas_alvo(perfil, maquina)
    conf = conformidade(z["metricas"], ct)
    out = [f"# {nome} ({versao})", "", f"- **Perfil:** {perfil['nome']}", f"- **Máquina:** {maquina['nome']}"]
    out.append(f"- **Faixa verde:** {conf['ideal']}/{conf['total']} parâmetros")
    if notas:
        out.append(f"- **Notas:** {notas}")
    out += ["", "## Ingredientes", "", "| Ingrediente | g | % |", "|---|---:|---:|"]
    e = z["totais"]["gramas"] or 1
    for row in z["linhas"]:
        if row["conhecido"]:
            out.append(f"| {_md_cel(row['nome'])} | {br(row['gramas'])} | {br((row['gramas'] / e) * 100)} |")
    out.append(f"| **TOTAL** | **{br(z['totais']['gramas'])}** | **100** |")
    desconhecidos = [r["ingrediente"] for r in z["linhas"] if not r["conhecido"]]
    if desconhecidos:
        out += ["", f"> Ingredientes fora do banco (só contam no peso): {', '.join(map(str, desconhecidos))}"]
    out += ["", "## Balanceamento", "", "| Parâmetro | Valor | Faixa | Status |", "|---|---:|---:|---|"]
    for p in conf["parametros"]:
        c = p["casas"]
        st = {"IDEAL": "ok", "ABAIXO": "abaixo", "ACIMA": "acima"}[p["status"]]
        out.append(f"| {p['rotulo']} | {br(p['valor'], c)} {p['unidade']} | {br(p['min'], c)}–{br(p['max'], c)} | {st} |")
    out += ["", "## Congelamento, arenosidade e custo", ""]
    if z["totais"]["evaporada"] > 0:
        out.append(f"- **Água evaporada no cozimento:** {br(z['totais']['evaporada'])} g (peso final {br(z['totais']['gramas'])} g)")
    a = z["arenosidade"]
    out.append(f"- **SNLG pela lactose (arenosidade):** {br(a['valor'])}% · limite {br(a['maximo'])}%"
               + ("" if a["ok"] else " — **risco de arenosidade**"))
    out.append(f"- **Ponto de congelamento:** {br(z['ponto_congelamento'])} °C")
    out.append(f"- **Servir a (~72% da água congelada):** {br(z['temp_servir_ideal'])} °C")
    out.append(f"- **Custo:** R$ {br(z['custo_kg'], 2)}/kg")
    dicas = [p for p in conf["parametros"] if p["dica"]]
    if dicas:
        out += ["", "## Ajustes sugeridos", ""]
        out += [f"- **{p['rotulo']}** ({'abaixo' if p['status'] == 'ABAIXO' else 'acima'}): {p['dica']}" for p in dicas]
    return "\n".join(out) + "\n"
