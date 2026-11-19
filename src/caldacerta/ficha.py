"""Ficha técnica: o texto do botão "Copiar ficha" do app (``Vc``) e uma
versão em Markdown com o mesmo conteúdo, pronta para salvar como nota."""

from __future__ import annotations

from typing import Mapping, Sequence

from . import nutricao
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
    porcao_g: float | None = None,
    pote: str | None = None,
    processo: str | None = None,
    novidades: bool = True,
    peso_kg: float | None = None,
) -> str:
    """Mesmo conteúdo da ficha do app, em Markdown (tabelas + status da faixa).

    Com ``novidades`` (padrão), acrescenta ao final: nutrição (porção
    ``porcao_g``, pote ``pote``), alertas, correções de um ingrediente,
    orientações da máquina e lembretes de processo."""
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
    if novidades:
        ex = nutricao.complementos(itens, ingredientes, maquina, perfil, evaporada, porcao_g, pote, processo, z=z,
                                   peso_kg=peso_kg)
        out += secoes_novidades_md(ex)
    return "\n".join(out) + "\n"


def secoes_novidades_md(ex) -> list[str]:
    """Seções novas da ficha em Markdown (depois das originais)."""
    out = []
    if ex.get("comparacao_classica"):
        out += ["", "## Comparação com o padrão clássico", "", nutricao.linha_comparacao(ex["comparacao_classica"]),
                "", "Estilo 'fit': no Creami a lâmina compensa o PAC baixo; em vitrine ficaria duro e cristalino."]
    out += ["", "## Nutrição (estimativa)", ""]
    out += [f"- {l}" for l in nutricao.linhas_nutricao(ex["nutricao"], ex.get("pote"), ex.get("limite_eritritol_porcao_g"))]
    out.append("- Fatores de Atwater (gordura 9, proteína 4, carboidratos 4, álcool 7 kcal/g; polióis, alulose e "
               "fibras com fatores próprios). Confira o rótulo dos seus insumos.")
    if ex.get("alertas"):
        out += ["", "## Alertas", ""] + [f"- {'**' + a['texto'] + '**' if a['nivel'] == 'forte' else a['texto']}"
                                         for a in ex["alertas"]]
    if ex.get("correcoes"):
        out += ["", "## Correções de um ingrediente (estimativa)", ""]
        out += [f"- {nutricao.linha_correcao(c)}" for c in ex["correcoes"]]
    if ex.get("orientacoes_maquina"):
        out += ["", "## Máquina", ""]
        if ex.get("pote"):
            p = ex["pote"]
            out.append(f"- **Pote:** {p['nome']}: ~{br(p['gramas'], 0)} g de calda "
                       f"({br(p['volume_ml'] * p['enchimento_max_fracao'], 0)} ml × {br(p['densidade_g_ml'], 2)} g/ml)")
        out += [f"- {o}" for o in ex["orientacoes_maquina"]]
    out += ["", "## Lembretes de processo", ""] + [f"- [ ] {l}" for l in ex["lembretes"]]
    return out
