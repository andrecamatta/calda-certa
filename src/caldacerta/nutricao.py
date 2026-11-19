"""Funções novas (não existiam no app original): nutrição, densidade e pote
da máquina, Brix medido, alertas de formulação, correções de um ingrediente
e o objetivo "light" do auto-balanceamento.

Nada aqui altera os cálculos do motor original (``motor.py``): são
informações extras, calculadas a partir do resultado de ``motor.avaliar``.
As constantes ficam em ``novidades.json`` (seção ``constantes``), com as
fontes de cada número.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from . import dados, motor
from .dados import carregar_constantes
from .jsnum import br, js_round, numero

PROCESSOS = ("frio", "quente")


def _k() -> dict:
    return dados.constantes_novidades()


def _grupos() -> dict[str, str]:
    return {a["chave"]: a["grupo"] for a in carregar_constantes()["acucares"]}


# --------------------------------------------------------------------------
# Energia e caseína por 100 g de ingrediente
# --------------------------------------------------------------------------
def kcal_100g(ing: Mapping, k: Mapping | None = None) -> float:
    """kcal por 100 g do ingrediente.

    Usa ``kcal_100g`` do ingrediente quando houver. Senão, fatores de Atwater
    sobre a composição: gordura 9, proteína 4, lactose 4, álcool 7; açúcares e
    polióis/fibras/ácidos do perfil de açúcares com o fator de cada um
    (alulose 0,4; eritritol 0; polióis 2,4...); o que sobra dos açúcares vale
    4; o que sobra dos outros sólidos (tirando a proteína que não está no
    SNG, ``fibra`` a 2 kcal/g e ``cinzas`` a 0) vale 4. Os minerais do SNG
    valem 0."""
    if ing.get("kcal_100g") is not None:
        return numero(ing.get("kcal_100g"))
    e = (k or _k())["energia"]
    fat = e["por_acucar"]
    grupos = _grupos()
    perfil = ing.get("perfil_acucares") or {}
    g = lambda c: numero(ing.get(c))
    proteina, sng, lactose = g("proteina"), g("sng"), g("lactose")
    kcal = g("gordura") * e["gordura"] + proteina * e["proteina"] + lactose * e["carboidrato"] + g("alcool") * e["alcool"]
    listado = {"acucares": 0.0, "outros_solidos": 0.0, "sng": 0.0}
    for chave, v in perfil.items():
        v = numero(v)
        grp = grupos.get(chave, "outros_solidos")
        listado[grp] = listado.get(grp, 0.0) + v
        kcal += v * fat.get(chave, e["carboidrato"])
    kcal += max(0.0, g("acucares") - listado["acucares"]) * e["carboidrato"]
    proteina_fora_sng = max(0.0, proteina - max(0.0, sng - lactose))
    fibra, cinzas = g("fibra"), g("cinzas")
    resto = max(0.0, g("outros_solidos") - listado["outros_solidos"] - proteina_fora_sng - fibra - cinzas)
    kcal += fibra * e["fibra"] + cinzas * e["cinzas"] + resto * e["outros_nao_especificados"]
    return kcal


def caseina_100g(ing: Mapping, k: Mapping | None = None) -> float:
    """Caseína (g/100 g): campo ``caseina`` ou, em lácteos (SNG > 0), ~80% da proteína."""
    if ing.get("caseina") is not None:
        return numero(ing.get("caseina"))
    if numero(ing.get("sng")) > 0:
        return numero(ing.get("proteina")) * (k or _k())["caseina_fracao_proteina_leite"]
    return 0.0


# --------------------------------------------------------------------------
# Densidade da calda e pote da máquina
# --------------------------------------------------------------------------
def densidade(metricas: Mapping[str, float], k: Mapping | None = None) -> float:
    """Densidade estimada da calda (g/ml) pela composição (Goff, Univ. of Guelph)."""
    d = (k or _k())["densidade"]
    agua = metricas.get("agua", 0)
    gord = metricas.get("gordura", 0)
    alc = metricas.get("alcool", 0)
    snf = max(0.0, metricas.get("solidos_totais", 0) - gord)
    vol = agua / d["agua"] + gord / d["gordura"] + snf / d["solidos_nao_gordurosos"] + alc / d["alcool"]
    return 100 / vol if vol > 0 else 1.0


def potes(maquina: Mapping) -> list[dict]:
    return list(maquina.get("potes") or [])


def escolher_pote(maquina: Mapping, pote_id: str | None = None) -> dict | None:
    """Pote da máquina (o primeiro, ou o de id/trecho de nome ``pote_id``)."""
    lista = potes(maquina)
    if pote_id is None:
        return lista[0] if lista else None
    if not lista:
        raise ValueError(f"a máquina {maquina['id']} não tem potes cadastrados")
    return dados.achar(lista, pote_id, "pote")


def gramas_pote(maquina: Mapping, pote: Mapping, rho: float) -> float:
    """Gramas de calda que cabem no pote: volume até a linha MAX × fração de
    enchimento (folga para espuma) × densidade estimada."""
    return pote["volume_ml"] * numero(maquina.get("enchimento_max_fracao") or 1) * rho


def info_pote(maquina: Mapping, pote_id: str | None, metricas: Mapping) -> dict | None:
    pote = escolher_pote(maquina, pote_id)
    if pote is None:
        return None
    rho = densidade(metricas)
    return {**pote, "densidade_g_ml": rho, "enchimento_max_fracao": numero(maquina.get("enchimento_max_fracao") or 1),
            "gramas": gramas_pote(maquina, pote, rho)}


# --------------------------------------------------------------------------
# Brix medido (refratômetro)
# --------------------------------------------------------------------------
def ajustar_brix(ing: Mapping, brix: float) -> dict:
    """Ingrediente com o teor de açúcar corrigido por uma leitura de Brix.

    °Brix ≈ g de sólidos solúveis por 100 g. Os ácidos da fruta também
    contam na leitura, então açúcares = Brix − ácidos do perfil. A diferença
    sai (ou entra) da água; os açúcares do perfil são escalados na mesma
    proporção e POD/PAC recalculados (ou escalados, se POD/PAC são manuais)."""
    b = numero(brix)
    if not (0 < b < 100):
        raise ValueError(f"Brix inválido para {ing['id']}: {brix} (use 0–100)")
    antigo = numero(ing.get("acucares"))
    if antigo <= 0:
        raise ValueError(f"{ing['id']} não tem açúcares na composição: Brix não se aplica")
    perfil = dict(ing.get("perfil_acucares") or {})
    acidos = numero(perfil.get("acidos_fruta"))
    novo = max(0.0, b - acidos)
    delta = novo - antigo
    agua = numero(ing.get("agua")) - delta
    if agua < 0:
        raise ValueError(f"Brix {br(b)} impossível para {ing['nome']}: não há água suficiente na composição")
    f = novo / antigo
    grupos = _grupos()
    for chave, v in list(perfil.items()):
        if grupos.get(chave) == "acucares":
            perfil[chave] = numero(v) * f
    out = dict(ing)
    out.update({"acucares": novo, "agua": agua, "perfil_acucares": perfil, "brix": b})
    if out.get("pod_pac_auto"):
        out.update(motor.pod_pac_automatico(out))
    else:
        out["pod"] = numero(ing.get("pod")) * f
        out["pac"] = numero(ing.get("pac")) * f
    if ing.get("kcal_100g") is not None:
        out["kcal_100g"] = numero(ing["kcal_100g"]) + delta * _k()["energia"]["carboidrato"]
    return out


def aplicar_brix(ingredientes: Mapping[str, Mapping], itens: Sequence[Mapping]) -> tuple[dict, list[dict]]:
    """Mapa de ingredientes com as leituras de Brix dos itens aplicadas.
    Sem ``brix`` em nenhum item, devolve o mesmo mapa (sem cópia)."""
    leituras: dict[str, float] = {}
    for it in itens:
        if it.get("brix") is None:
            continue
        b = numero(it["brix"])
        iid = it.get("ingrediente")
        if iid in leituras and leituras[iid] != b:
            raise ValueError(f"leituras de Brix diferentes para {iid} na mesma receita")
        leituras[iid] = b
    if not leituras:
        return ingredientes, []  # type: ignore[return-value]
    novo = dict(ingredientes)
    ajustes = []
    for iid, b in leituras.items():
        if iid not in novo:
            raise ValueError(f"Brix informado para ingrediente fora do banco: {iid}")
        antes = novo[iid]
        depois = ajustar_brix(antes, b)
        novo[iid] = depois
        ajustes.append({
            "ingrediente": iid, "brix": b,
            "acucares_antes": numero(antes.get("acucares")), "acucares_depois": depois["acucares"],
            "agua_antes": numero(antes.get("agua")), "agua_depois": depois["agua"],
            "pod": depois["pod"], "pac": depois["pac"],
            "texto": (f"{antes['nome']}: Brix {br(b)} → açúcares {br(numero(antes.get('acucares')))}% → "
                      f"{br(depois['acucares'])}%, água {br(numero(antes.get('agua')))}% → {br(depois['agua'])}%"),
        })
    return novo, ajustes


# --------------------------------------------------------------------------
# Nutrição
# --------------------------------------------------------------------------
def nutricao(z: Mapping, ingredientes: Mapping[str, Mapping], porcao_g: float | None = None,
             pote_g: float | None = None) -> dict:
    """kcal e macros por 100 g, por porção, por pote e no lote (peso final,
    já sem a água evaporada; a água evaporada não tem caloria)."""
    k = _k()
    porcao = numero(porcao_g) if porcao_g is not None else k["porcao_padrao_g"]
    tol = {c: v for c, v in k["tolerancia_digestiva_g_porcao"].items() if not c.startswith("_")}
    kcal = 0.0
    caseina = 0.0
    poliois = {c: 0.0 for c in tol}
    for l in z["linhas"]:
        ing = ingredientes.get(l["ingrediente"]) if l.get("conhecido") else None
        if not ing:
            continue
        h = l["gramas"] / 100
        kcal += h * kcal_100g(ing, k)
        caseina += h * caseina_100g(ing, k)
        perfil = ing.get("perfil_acucares") or {}
        for c in poliois:
            poliois[c] += h * numero(perfil.get(c))
    t = z["totais"]
    peso = t["gramas"]
    alulose = 0.0
    for l in z["linhas"]:
        ing = ingredientes.get(l["ingrediente"]) if l.get("conhecido") else None
        if ing:
            alulose += l["gramas"] / 100 * numero((ing.get("perfil_acucares") or {}).get("alulose"))
    lote = {
        "gramas": peso,
        "kcal": kcal,
        "proteina_g": t["proteina"],
        "gordura_g": t["gordura"],
        # açúcares do rótulo: sem a alulose, que a FDA não conta como açúcar (conta à parte, em polióis/alulose)
        "acucares_g": max(0.0, t["acucares"] + t["lactose"] - alulose),
        "alcool_g": t["alcool"],
        "caseina_g": caseina,
        "poliois_g": {c: v for c, v in poliois.items() if v > 0},
    }

    def fatia(g: float) -> dict:
        f = g / peso if peso > 0 else 0
        out = {c: (v * f if isinstance(v, float) else v) for c, v in lote.items() if c != "poliois_g"}
        out["gramas"] = g
        out["poliois_g"] = {c: v * f for c, v in lote["poliois_g"].items()}
        return out

    por100 = fatia(100.0)
    return {
        "kcal_100g": por100["kcal"],
        "proteina_pct": por100["proteina_g"],
        "caseina_pct": por100["caseina_g"],
        "por_100g": por100,
        "porcao": fatia(porcao),
        "pote": fatia(pote_g) if pote_g else None,
        "lote": lote,
    }


# --------------------------------------------------------------------------
# Eritritol: limites de saúde
# --------------------------------------------------------------------------
def limite_eritritol_porcao(peso_kg: float | None = None) -> float:
    """1/3 da IDA da EFSA (0,5 g/kg/dia) para o peso dado (padrão 70 kg → ~11,7 g)."""
    e = _k()["eritritol"]
    peso = numero(peso_kg) if peso_kg is not None else e["peso_kg_padrao"]
    return e["ida_g_kg_dia"] * peso * e["fracao_ida_porcao"]


def _alertas_eritritol(nutri: Mapping, peso_kg: float | None) -> list[dict]:
    e = _k()["eritritol"]
    out = []
    onde = []
    for chave, rot in (("porcao", "na porção"), ("pote", "no pote"), ("lote", "no lote")):
        fat = nutri.get(chave)
        g = (fat or {}).get("poliois_g", {}).get("eritritol", 0.0)
        if fat and g >= e["alerta_forte_g"]:
            onde.append(f"{br(g, 1)} g {rot} ({br(fat['gramas'], 0)} g)")
    if onde:
        out.append({"codigo": "eritritol_30g", "nivel": "forte",
                    "texto": f"ATENÇÃO: eritritol ≥ {br(e['alerta_forte_g'], 0)} g: {'; '.join(onde)}. É a dose que aumentou "
                             "a reatividade das plaquetas em estudo de intervenção (Nature Medicine 2023; replicado em "
                             "2024). Associação, não causalidade provada; evite se tiver risco cardiovascular e "
                             "prefira alulose."})
    lim = limite_eritritol_porcao(peso_kg)
    gp = nutri["porcao"]["poliois_g"].get("eritritol", 0.0)
    if gp > lim:
        peso = numero(peso_kg) if peso_kg is not None else e["peso_kg_padrao"]
        out.append({"codigo": "eritritol_ida", "nivel": "warn",
                    "texto": f"Eritritol na porção: {br(gp, 1)} g, mais de 1/3 da ingestão diária aceitável da EFSA "
                             f"(0,5 g/kg/dia → {br(lim, 1)} g por porção para {br(peso, 0)} kg). Reduza a porção ou "
                             "troque parte por alulose."})
    return out


# --------------------------------------------------------------------------
# Alertas de formulação
# --------------------------------------------------------------------------
def alertas(z: Mapping, ingredientes: Mapping[str, Mapping], nutri: Mapping, processo: str | None = None,
            peso_kg: float | None = None) -> list[dict]:
    k = _k()
    lim = k["limites"]
    tol = {c: v for c, v in k["tolerancia_digestiva_g_porcao"].items() if not c.startswith("_")}
    out: list[dict] = []
    peso = z["totais"]["gramas"]
    m = z["metricas"]
    # estabilizantes: dose máxima e ativação
    for l in z["linhas"]:
        ing = ingredientes.get(l["ingrediente"]) if l.get("conhecido") else None
        if not ing or l["gramas"] <= 0:
            continue
        dmax = ing.get("dose_max_pct")
        if dmax is not None and peso > 0:
            pct = l["gramas"] / peso * 100
            if pct > numero(dmax) + 1e-9:
                defeito = ing.get("defeito_excesso") or "textura estranha"
                out.append({"codigo": "dose_maxima", "nivel": "warn", "ingrediente": ing["id"],
                            "texto": f"{ing['nome']}: {br(pct, 2)}% da calda passa da dose máxima de {br(numero(dmax), 2)}% "
                                     f"(≈ {br(numero(dmax) * peso / 100, 1)} g neste lote). Em excesso fica {defeito}."})
        if processo == "frio" and ing.get("ativacao") == "quente":
            out.append({"codigo": "ativacao", "nivel": "warn", "ingrediente": ing["id"],
                        "texto": f"{ing['nome']} só hidrata a quente (~80 °C), mas o processo é a frio: "
                                 "aqueça a calda ou troque por um estabilizante de ativação a frio (guar, xantana)."})
    # eritritol: recristalização
    erit = nutri["por_100g"]["poliois_g"].get("eritritol", 0.0)
    if erit > lim["eritritol_pct_max"]:
        out.append({"codigo": "eritritol_cristaliza", "nivel": "warn",
                    "texto": f"Eritritol a {br(erit, 1)}% da calda (acima de ~{br(lim['eritritol_pct_max'], 0)}%): pouco "
                             "solúvel no frio, recristaliza e deixa a massa arenosa e dura, apesar do PAC teórico alto. "
                             "Troque parte por alulose."})
    out += _alertas_eritritol(nutri, peso_kg)
    # caseína
    cas = nutri["caseina_pct"]
    if cas > lim["caseina_pct_max"]:
        out.append({"codigo": "caseina_alta", "nivel": "warn",
                    "texto": f"Caseína ~{br(cas, 1)}% da calda (acima de ~{br(lim['caseina_pct_max'], 0)}%, heurística): "
                             "a massa tende a ficar pastosa/borrachuda. Troque parte da proteína por whey isolado."})
    # água livre / sólidos baixos
    if peso > 0 and m["solidos_totais"] < lim["solidos_totais_min_pct"]:
        out.append({"codigo": "agua_livre", "nivel": "warn",
                    "texto": f"Sólidos totais {br(m['solidos_totais'], 1)}% (água {br(m['agua'], 1)}%): muita água livre, "
                             "tende a cristais grandes de gelo (textura de raspadinha). Suba sólidos (proteína, fibras, "
                             "oleaginosas, alulose) ou, no Creami, faça Re-spin com 1 colher de leite."})
    # tolerância digestiva por porção
    for chave, rot in (("porcao", "porção"), ("pote", "pote inteiro")):
        fat = nutri.get(chave)
        if not fat:
            continue
        pol = fat["poliois_g"]
        soma = sum(pol.get(c, 0) / tol[c] for c in tol)
        if soma >= 1:
            partes = ", ".join(f"{br(g, 1)} g de {c}" for c, g in pol.items() if g > 0.05)
            out.append({"codigo": f"tolerancia_digestiva_{chave}", "nivel": "warn",
                        "texto": f"Na {rot} ({br(fat['gramas'], 0)} g): {partes}. Acima da dose que costuma ser bem "
                                 "tolerada de uma vez (gases, inchaço, efeito laxativo); reduza ou sirva porções menores."})
            break  # se a porção já passa, o pote inteiro também
    return out


# --------------------------------------------------------------------------
# Correções de um ingrediente
# --------------------------------------------------------------------------
def _total_metrica(t: Mapping, chave: str) -> float:
    return t[chave]


def _conteudo(ing: Mapping, chave: str) -> float:
    if chave == "solidos_totais":
        return sum(numero(ing.get(c)) for c in ("gordura", "acucares", "sng", "outros_solidos"))
    return numero(ing.get(chave))


def correcoes(z: Mapping, itens: Sequence[Mapping], ingredientes: Mapping[str, Mapping], faixas: Mapping,
              conf: Mapping, temp: float, evaporada: float) -> list[dict]:
    """Para cada métrica fora da faixa (com candidatos em ``novidades.json``),
    quantos gramas de UM ingrediente a trazem a 1/4 da faixa, e como fica a
    receita (faixa verde e kcal) com essa adição. Estimativa de primeira ordem:
    a adição mexe nas outras métricas também (o resultado mostra quanto)."""
    k = _k()
    cand = k["correcoes"]
    t = z["totais"]
    G = t["gramas"]
    out = []
    if G <= 0:
        return out
    kcal0 = nutricao(z, ingredientes)["kcal_100g"]
    for p in conf["parametros"]:
        chave, st = p["chave"], p["status"]
        ids = (cand.get(chave) or {}).get(st)
        if st == "IDEAL" or not ids:
            continue
        lo, hi = p["min"], p["max"]
        alvo = lo + (hi - lo) * 0.25 if st == "ABAIXO" else hi - (hi - lo) * 0.25
        escala = 1000 if chave in ("pod", "pac") else 100
        for iid in ids:
            ing = ingredientes.get(iid)
            if not ing:
                continue
            c = _conteudo(ing, chave)
            den = c * escala / 100 - alvo
            if den == 0:
                continue
            x = (alvo * G - _total_metrica(t, chave) * escala) / den
            if not (x > 0) or x > 2 * G:
                continue
            x = js_round(x * 10) / 10
            novos = [dict(i) for i in itens] + [{"ingrediente": iid, "gramas": x, "travado": False}]
            z2 = motor.avaliar(novos, ingredientes, temp, evaporada)
            conf2 = motor.conformidade(z2["metricas"], faixas)
            if conf2["ideal"] < conf["ideal"]:
                continue  # conserta uma métrica estragando outras: não sugerimos
            out.append({
                "metrica": chave, "rotulo": p["rotulo"], "status": st, "valor": p["valor"], "alvo": alvo,
                "ingrediente": iid, "nome": ing["nome"], "gramas": x,
                "valor_depois": z2["metricas"][chave], "faixa_verde_depois": f"{conf2['ideal']}/{conf2['total']}",
                "kcal_100g_antes": kcal0, "kcal_100g_depois": nutricao(z2, ingredientes)["kcal_100g"],
            })
    return out


# --------------------------------------------------------------------------
# Lembretes de processo
# --------------------------------------------------------------------------
def tem_chocolate(itens: Sequence[Mapping], ingredientes: Mapping[str, Mapping]) -> bool:
    for i in itens:
        ing = ingredientes.get(i.get("ingrediente"))
        if ing and (ing.get("categoria") == "Chocolates" or "chocolate" in str(ing.get("nome", "")).lower()):
            return True
    return False


def lembretes(maquina: Mapping, itens: Sequence[Mapping], ingredientes: Mapping[str, Mapping]) -> list[str]:
    lp = _k()["lembretes_processo"]
    out = list(lp["geral"])
    creami = bool(potes(maquina))
    if creami:
        out += lp["creami"]
    if creami or tem_chocolate(itens, ingredientes):
        out.append(lp["chocolate"])
    return out


def orientacoes_maquina(maquina: Mapping) -> list[str]:
    """Orientações extras da máquina (pote, freezer, congelamento, programas)."""
    out = []
    for p in potes(maquina):
        out.append(f"{p['nome']}: até a linha MAX (~{p['volume_ml']} ml).")
    if maquina.get("temp_freezer_c") is not None:
        out.append(f"Freezer a {maquina['temp_freezer_c']} °C ou mais frio.")
    ch = maquina.get("congelamento_h")
    if ch:
        out.append(f"Congelar por pelo menos {ch['minimo']} h; ~{ch['base_aquecida']} h se a base foi aquecida.")
    out += list(maquina.get("orientacoes") or [])
    return out


# --------------------------------------------------------------------------
# Pacote completo (usado pela análise, ficha e página)
# --------------------------------------------------------------------------
def complementos(
    itens: Sequence[Mapping],
    ingredientes: Mapping[str, Mapping],
    maquina: Mapping,
    perfil: Mapping,
    evaporada: float = 0,
    porcao_g: float | None = None,
    pote_id: str | None = None,
    processo: str | None = None,
    z: Mapping | None = None,
    peso_kg: float | None = None,
) -> dict:
    """Nutrição, pote, alertas, correções e lembretes de uma receita."""
    if z is None:
        z = motor.avaliar(itens, ingredientes, maquina["temp_servir"], evaporada)
    faixas = motor.faixas_alvo(perfil, maquina)
    conf = motor.conformidade(z["metricas"], faixas)
    pote = info_pote(maquina, pote_id, z["metricas"]) if z["totais"]["gramas"] > 0 else None
    nutri = nutricao(z, ingredientes, porcao_g, pote["gramas"] if pote else None)
    return {
        "comparacao_classica": comparacao_classica(z, perfil, maquina),
        "processo": processo,
        "pote": pote,
        "nutricao": nutri,
        "alertas": alertas(z, ingredientes, nutri, processo, peso_kg),
        "limite_eritritol_porcao_g": limite_eritritol_porcao(peso_kg),
        "correcoes": correcoes(z, itens, ingredientes, faixas, conf, maquina["temp_servir"], evaporada),
        "lembretes": lembretes(maquina, itens, ingredientes),
        "orientacoes_maquina": orientacoes_maquina(maquina),
    }


def comparacao_classica(z: Mapping, perfil: Mapping, maquina: Mapping) -> dict | None:
    """Se o perfil indica ``referencia_classica`` (ex.: estilos 'fit'), mostra
    a mesma receita contra as faixas desse perfil clássico."""
    ref_id = perfil.get("referencia_classica")
    if not ref_id:
        return None
    ref = dados.achar_com_extras(dados.perfis(), dados.perfis_extra(), ref_id, "perfil")
    conf = motor.conformidade(z["metricas"], motor.faixas_alvo(ref, maquina))
    return {
        "perfil": ref["id"], "nome": ref["nome"], "ideal": conf["ideal"], "total": conf["total"],
        "fora": [{k: p[k] for k in ("chave", "rotulo", "unidade", "casas", "valor", "min", "max", "status")}
                 for p in conf["parametros"] if p["status"] != "IDEAL"],
    }


def linha_comparacao(c: Mapping) -> str:
    partes = [f"{p['rotulo']} {br(p['valor'], p['casas'])} (faixa {br(p['min'], p['casas'])}–{br(p['max'], p['casas'])})"
              for p in c["fora"]]
    return (f"Pelos padrões de {c['nome']}: faixa verde {c['ideal']}/{c['total']}"
            + (f". Fora: {'; '.join(partes)}." if partes else "."))


def linhas_nutricao(n: Mapping, pote: Mapping | None, limite_eritritol: float | None = None) -> list[str]:
    """Linhas de texto (sem marcação) do resumo nutricional."""
    def fx(f: Mapping) -> str:
        return (f"{br(f['kcal'], 0)} kcal · {br(f['proteina_g'], 1)} g proteína · {br(f['gordura_g'], 1)} g gordura · "
                f"{br(f['acucares_g'], 1)} g açúcares")
    out = [f"{br(n['kcal_100g'], 0)} kcal/100 g · proteína {br(n['proteina_pct'], 1)}%"]
    out.append(f"Porção de {br(n['porcao']['gramas'], 0)} g: {fx(n['porcao'])}")
    if n.get("pote") and pote:
        out.append(f"{pote['nome'].split(' (')[0]} (~{br(pote['gramas'], 0)} g): {fx(n['pote'])}")
    out.append(f"Lote ({br(n['lote']['gramas'], 0)} g): {fx(n['lote'])}")
    pol = n["porcao"]["poliois_g"]
    if any(v > 0.05 for v in pol.values()):
        out.append("Polióis/alulose/fibras na porção: " + ", ".join(f"{br(v, 1)} g de {c}" for c, v in pol.items() if v > 0.05))
    erit = n["lote"]["poliois_g"].get("eritritol", 0.0)
    if erit > 0:
        lim = limite_eritritol if limite_eritritol is not None else limite_eritritol_porcao()
        out.append(f"Eritritol: {br(pol.get('eritritol', 0.0), 1)} g por porção (teto sugerido {br(lim, 1)} g = 1/3 da IDA "
                   f"da EFSA) · {br(erit, 1)} g no lote"
                   + (f" · {br(n['pote']['poliois_g'].get('eritritol', 0.0), 1)} g no pote" if n.get("pote") else ""))
    return out


def linha_correcao(c: Mapping) -> str:
    st = "abaixo" if c["status"] == "ABAIXO" else "acima"
    casas = 0 if c["metrica"] in ("pod", "pac") else 1
    return (f"{c['rotulo']} {br(c['valor'], casas)} ({st} da faixa): +{br(c['gramas'], 1)} g de {c['nome']} → "
            f"{br(c['valor_depois'], casas)}, faixa verde {c['faixa_verde_depois']}, "
            f"{br(c['kcal_100g_antes'], 0)} → {br(c['kcal_100g_depois'], 0)} kcal/100 g")


# --------------------------------------------------------------------------
# Objetivo "light" do auto-balanceamento
# --------------------------------------------------------------------------
def objetivo_light(itens: Sequence[Mapping], ingredientes: Mapping[str, Mapping], faixas: Mapping,
                   evaporada: float = 0, proteina_min: float | None = None, porcao_g: float | None = None,
                   peso_kg: float | None = None) -> tuple[Any, dict]:
    """Função objetivo para ``motor.balancear(..., funcao_objetivo=...)``.

    Objetivo original + (fator − 1) × a penalidade de sair das faixas (as faixas
    verdes continuam mandando) + ``peso_kcal`` × kcal/100 g relativas à receita
    inicial + penalidade forte se a proteína ficar abaixo de ``proteina_min``
    (% da calda; também sobe a faixa de proteína para incluí-la).
    Eritritol: pequena penalidade por % da calda (prefere alulose e outros
    açúcares) e teto rígido de 1/3 da IDA da EFSA por porção (``porcao_g``,
    ``peso_kg``). Devolve ``(funcao, faixas_efetivas)``."""
    k = _k()
    cfg = k["light"]
    fx = {c: list(v) for c, v in faixas.items()}
    if proteina_min is not None:
        pmin = numero(proteina_min)
        lo, hi = fx["proteina"]
        fx["proteina"] = [max(lo, pmin), max(hi, pmin)]
    else:
        pmin = None
    base = motor._preparar_objetivo(itens, ingredientes, fx, evaporada)
    coef = []
    for item in itens:
        c = ingredientes.get(item.get("ingrediente"))
        if not c:
            coef.append(None)
            continue
        st = sum(numero(c.get(x)) for x in ("gordura", "acucares", "sng", "outros_solidos"))
        coef.append({
            "agua": numero(c.get("agua")), "kcal": kcal_100g(c, k),
            "erit": numero((c.get("perfil_acucares") or {}).get("eritritol")),
            "v": [numero(c.get("gordura")), numero(c.get("proteina")), numero(c.get("acucares")), numero(c.get("sng")),
                  numero(c.get("outros_solidos")), st, numero(c.get("pod")), numero(c.get("pac"))],
        })
    alvos = []
    for chave in motor.CHAVES_BALANCO:
        lo, hi = fx[chave]
        h = max((hi - lo) / 2, 10 if chave in ("pod", "pac") else 0.5)
        alvos.append((motor.PESOS_BALANCO[chave], lo, hi, h, 1e3 if chave in ("pod", "pac") else 100))
    evap = numero(evaporada)
    extra_faixa = cfg["fator_fora_da_faixa"] - 1

    porcao = numero(porcao_g) if porcao_g is not None else k["porcao_padrao_g"]
    teto_erit = limite_eritritol_porcao(peso_kg)

    def medir(gramas):
        tg = tw = tk = te = 0.0
        tv = [0.0] * 8
        for f, c in zip(gramas, coef):
            tg += f
            if c is None:
                continue
            h = f / 100
            tw += h * c["agua"]
            tk += h * c["kcal"]
            te += h * c["erit"]
            for j, v in enumerate(c["v"]):
                tv[j] += h * v
        tg -= max(0, min(evap, tw))
        return tg, tk, tv, te

    g0, k0, _, _ = medir([max(0, numero(i.get("gramas"))) for i in itens])
    kcal_ref = (k0 / g0 * 100) if g0 > 0 and k0 > 0 else 1.0

    def objetivo(gramas):
        y = base(gramas)
        tg, tk, tv, te = medir(gramas)
        if tg <= 0:
            return y
        for (peso, lo, hi, h, esc), tot in zip(alvos, tv):
            s = tot / tg * esc
            if s < lo:
                y += extra_faixa * peso * 10 * ((lo - s) / h) ** 2
            elif s > hi:
                y += extra_faixa * peso * 10 * ((s - hi) / h) ** 2
        y += cfg["peso_kcal"] * (tk / tg * 100) / kcal_ref
        if pmin is not None:
            mp = tv[1] / tg * 100
            if mp < pmin:
                d = (pmin - mp) / 0.5
                y += cfg["peso_proteina_min"] * (d + d * d)  # termo linear: restrição quase rígida
        if te > 0:
            y += cfg["peso_preferencia_eritritol"] * (te / tg * 100)
            na_porcao = te / tg * porcao
            if na_porcao > teto_erit:
                excesso = na_porcao - teto_erit
                y += cfg["peso_teto_eritritol"] * (excesso + excesso * excesso)
        return y

    return objetivo, fx
