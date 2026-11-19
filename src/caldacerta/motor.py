"""Motor de cálculo do Calda Certa.

Reescrita fiel do motor JavaScript do app original (trecho preservado em
``tools/referencia/motor_original.js``). Cada função indica a função
minificada correspondente. A ordem das operações em ponto flutuante foi
mantida igual à do JS para que os resultados batam bit a bit.

Os dicionários usam as chaves em português dos arquivos de dados:

* ingrediente: ``agua, gordura, proteina, acucares, sng, lactose,
  outros_solidos, alcool, pod, pac, custo_kg, pod_pac_auto, perfil_acucares``
  (composição em % do ingrediente; POD/PAC em pontos por 100 g; custo em R$/kg);
* item de receita: ``{"ingrediente": id, "gramas": g, "travado": bool}``;
* faixas: ``{"gordura": [min, max], ...}`` para as 8 métricas balanceadas.
"""

from __future__ import annotations

import math
from typing import Any, Iterable, Mapping, Sequence

from .dados import carregar_constantes
from .jsnum import js_round, numero

Ingrediente = Mapping[str, Any]
Item = Mapping[str, Any]
Faixas = Mapping[str, Sequence[float]]

# Métricas balanceadas (ordem do app: Nl) e suas chaves.
CHAVES_BALANCO = (
    "gordura",
    "proteina",
    "acucares",
    "sng",
    "outros_solidos",
    "solidos_totais",
    "pod",
    "pac",
)
# Campos acumulados por linha (ordem do app: Bl).
_CAMPOS = (
    "agua",
    "gordura",
    "proteina",
    "acucares",
    "sng",
    "outros_solidos",
    "alcool",
    "lactose",
    "sng_lactose",
    "solidos_totais",
    "pod",
    "pac",
    "custo",
)

FRACAO_GELO_SERVIR = 0.72  # Sg: "servir a ~72% da água congelada"
TEMP_SERVIR_PADRAO = -12.0
# Pesos do otimizador (Fc: n).
PESOS_BALANCO = {
    "gordura": 2.5,
    "proteina": 0.8,
    "acucares": 2,
    "sng": 2,
    "outros_solidos": 1,
    "solidos_totais": 2.4,
    "pod": 2,
    "pac": 2.6,
}

MSG_POUCOS_DESTRAVADOS = "Destrave pelo menos 2 ingredientes para o otimizador trabalhar."
MSG_MASSA_ZERO = "A receita precisa ter massa maior que zero."
MSG_JA_OTIMO = "A fórmula já está no melhor ponto possível com os ingredientes destravados."
MSG_AJUSTADA = "Fórmula ajustada: ingredientes destravados movidos em direção ao centro das faixas."


# --------------------------------------------------------------------------
# POD/PAC automáticos a partir do perfil de açúcares (rr / Lg)
# --------------------------------------------------------------------------
def pod_pac_automatico(ing: Ingrediente, constantes: Mapping | None = None) -> dict:
    """POD e PAC (por 100 g) calculados pelo perfil de açúcares, lactose e álcool (``rr``)."""
    k = constantes or carregar_constantes()
    perfil = ing.get("perfil_acucares") or {}
    t = 0.0
    o = 0.0
    for a in k["acucares"]:
        n = numero(perfil.get(a["chave"]))
        t += n * a["pod"]
        o += n * a["pac"]
    r = numero(ing.get("lactose"))
    lalc = numero(ing.get("alcool"))
    t += r * k["lactose"]["pod"]
    o += r * k["lactose"]["pac"] + lalc * k["alcool"]["pac"]
    return {"pod": js_round(t * 10) / 10, "pac": js_round(o * 10) / 10}


def aplicar_pod_pac_auto(ing: Mapping, constantes: Mapping | None = None) -> dict:
    """Se ``pod_pac_auto`` estiver ligado, recalcula POD/PAC (``Lg``)."""
    novo = dict(ing)
    if novo.get("pod_pac_auto"):
        novo.update(pod_pac_automatico(novo, constantes))
    return novo


def sng_pela_lactose(ing: Ingrediente) -> float:
    """SNG equivalente pela lactose (``vg``): min(SNG, lactose / 0,545)."""
    a = numero(ing.get("sng"))
    t = numero(ing.get("lactose"))
    if a <= 0:
        return 0.0
    return min(a, t / 0.545) if t > 0 else a


# --------------------------------------------------------------------------
# Curva de congelamento (it / Ig / Dl / Cg / Sg)
# --------------------------------------------------------------------------
def depressao_curva(se: float, curva: Sequence[Sequence[float]] | None = None) -> float:
    """Depressão do ponto de congelamento (°C) para ``se`` g de sacarose
    equivalente por 100 g de água, interpolando a tabela (``Ig``)."""
    it = curva if curva is not None else carregar_constantes()["curva_congelamento"]
    if se <= 0:
        return 0
    a = it[-1]
    if se >= a[0]:
        t = it[-2]
        return a[1] + ((se - a[0]) * (a[1] - t[1])) / (a[0] - t[0])
    for idx in range(1, len(it)):
        o, r = it[idx]
        if se <= o:
            l, u = it[idx - 1]
            return u + ((se - l) * (r - u)) / (o - l)
    return a[1]


def depressao(pac10: float, sng: float, agua: float, curva=None) -> float:
    """Depressão total (°C) com ``agua`` g de água livre (``Dl``): curva da
    sacarose equivalente + contribuição dos sais do leite (2,37 × SNG / água)."""
    if agua <= 0:
        return math.inf
    return depressao_curva((pac10 / agua) * 100, curva) + (2.37 * sng) / agua


def fracao_congelada(pac10: float, sng: float, agua: float, temp: float, curva=None) -> float:
    """Fração da água congelada à temperatura ``temp`` (°C) (``Cg``), por bisseção."""
    if agua <= 0:
        return 0
    r = -temp
    if depressao(pac10, sng, agua, curva) >= r:
        return 0
    lo = 0.01
    hi = agua
    for _ in range(60):
        d = (lo + hi) / 2
        if depressao(pac10, sng, d, curva) > r:
            lo = d
        else:
            hi = d
    return (agua - (lo + hi) / 2) / agua


def temp_servir_ideal(pac10: float, sng: float, agua: float, fracao_gelo: float = FRACAO_GELO_SERVIR, curva=None) -> float:
    """Temperatura em que ``fracao_gelo`` da água está congelada (``Sg``)."""
    if agua <= 0:
        return 0
    return -depressao(pac10, sng, agua * (1 - fracao_gelo), curva)


# --------------------------------------------------------------------------
# Avaliação da receita (Bl)
# --------------------------------------------------------------------------
def _num_campo(ing: Ingrediente, chave: str) -> float:
    v = ing.get(chave)
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else numero(v)


def avaliar(
    itens: Iterable[Item],
    ingredientes: Mapping[str, Ingrediente],
    temp_servir: float = TEMP_SERVIR_PADRAO,
    evaporada: float = 0,
    curva=None,
) -> dict:
    """Avalia a receita (``Bl``): composição por linha, totais, métricas (% e
    pts/kg), arenosidade, ponto de congelamento, fração congelada na
    temperatura de serviço, temperatura ideal de servir e custo por kg."""
    it = curva if curva is not None else carregar_constantes()["curva_congelamento"]
    tot = {"gramas": 0.0}
    for c in _CAMPOS:
        tot[c] = 0.0
    linhas = []
    for item in itens:
        ing_id = item.get("ingrediente")
        c = ingredientes.get(ing_id) if ing_id is not None else None
        f = max(0, numero(item.get("gramas")))
        tot["gramas"] += f
        if not c:
            linha = {**item, "ingrediente": ing_id, "gramas": f, "conhecido": False, "nome": None}
            for k in _CAMPOS:
                linha[k] = 0
            linhas.append(linha)
            continue
        h = f / 100
        s = {
            "agua": h * _num_campo(c, "agua"),
            "gordura": h * _num_campo(c, "gordura"),
            "proteina": h * numero(c.get("proteina")),
            "acucares": h * _num_campo(c, "acucares"),
            "sng": h * _num_campo(c, "sng"),
            "outros_solidos": h * _num_campo(c, "outros_solidos"),
            "alcool": h * numero(c.get("alcool")),
            "lactose": h * numero(c.get("lactose")),
            "sng_lactose": h * sng_pela_lactose(c),
            "pod": h * _num_campo(c, "pod"),
            "pac": h * _num_campo(c, "pac"),
            "custo": (f * _num_campo(c, "custo_kg")) / 1e3,
        }
        s["solidos_totais"] = s["gordura"] + s["acucares"] + s["sng"] + s["outros_solidos"]
        for k in ("agua", "gordura", "proteina", "acucares", "sng", "outros_solidos", "alcool",
                  "lactose", "sng_lactose", "pod", "pac", "custo", "solidos_totais"):
            tot[k] += s[k]
        linhas.append({**item, "ingrediente": ing_id, "gramas": f, "conhecido": True, "nome": c.get("nome"), **s})

    n = max(0, min(numero(evaporada), tot["agua"]))
    tot["gramas_brutos"] = tot["gramas"]
    tot["evaporada"] = n
    tot["agua"] -= n
    tot["gramas"] -= n
    g = tot["gramas"]

    def pct(v):
        return (v / g) * 100 if g > 0 else 0

    def por_kg(v):
        return (v / g) * 1e3 if g > 0 else 0

    m = {
        "agua": pct(tot["agua"]),
        "gordura": pct(tot["gordura"]),
        "proteina": pct(tot["proteina"]),
        "acucares": pct(tot["acucares"]),
        "sng": pct(tot["sng"]),
        "outros_solidos": pct(tot["outros_solidos"]),
        "solidos_totais": pct(tot["solidos_totais"]),
        "alcool": pct(tot["alcool"]),
        "lactose": pct(tot["lactose"]),
        "sng_lactose": pct(tot["sng_lactose"]),
        "pod": por_kg(tot["pod"]),
        "pac": por_kg(tot["pac"]),
    }
    limite = max(0, (100 - (m["acucares"] + m["gordura"] + m["outros_solidos"])) * 0.15)
    arenosidade = {"valor": m["sng_lactose"], "maximo": limite, "ok": m["sng_lactose"] <= limite + 0.05}
    pac10 = m["pac"] / 10
    ponto = -depressao(pac10, m["sng_lactose"], m["agua"], it) if m["agua"] > 1 else 0
    congelada = fracao_congelada(pac10, m["sng_lactose"], m["agua"], temp_servir, it)
    servir = temp_servir_ideal(pac10, m["sng_lactose"], m["agua"], FRACAO_GELO_SERVIR, it) if m["agua"] > 1 else 0
    return {
        "linhas": linhas,
        "totais": tot,
        "metricas": m,
        "arenosidade": arenosidade,
        "ponto_congelamento": ponto,
        "temp_servir": temp_servir,
        "fracao_congelada": congelada,
        "temp_servir_ideal": servir,
        "custo_kg": por_kg(tot["custo"]),
    }


# --------------------------------------------------------------------------
# Faixas alvo, conformidade, escalonamento
# --------------------------------------------------------------------------
def faixas_alvo(perfil: Mapping, maquina: Mapping | None) -> dict:
    """Faixas do perfil com o ajuste de PAC da máquina (``Dc``)."""
    t = (maquina or {}).get("ajuste_pac") or 0
    f = {k: list(v) for k, v in perfil["faixas"].items()}
    pac = perfil["faixas"]["pac"]
    f["pac"] = [pac[0] + t, pac[1] + t]
    return f


def conformidade(metricas: Mapping[str, float], faixas: Faixas, constantes: Mapping | None = None) -> dict:
    """Status por métrica (IDEAL / ABAIXO / ACIMA, tolerância 0,01) e a contagem
    de métricas na faixa verde ("8/8" no app)."""
    k = constantes or carregar_constantes()
    params = []
    for md in k["metricas"]:
        chave = md["chave"]
        v = metricas.get(chave) or 0
        lo, hi = faixas[chave]
        st = "IDEAL"
        if v < lo - 0.01:
            st = "ABAIXO"
        elif v > hi + 0.01:
            st = "ACIMA"
        params.append({
            "chave": chave,
            "rotulo": md["rotulo"],
            "unidade": md["unidade"],
            "casas": md["casas"],
            "valor": v,
            "min": lo,
            "max": hi,
            "status": st,
            "dica": md["dica_baixo"] if st == "ABAIXO" else md["dica_alto"] if st == "ACIMA" else None,
        })
    ideal = sum(1 for p in params if p["status"] == "IDEAL")
    return {"parametros": params, "ideal": ideal, "total": len(params)}


def escalonar(itens: Sequence[Item], ingredientes: Mapping[str, Ingrediente], alvo: float, evaporada: float = 0) -> list[dict]:
    """Escala a receita para o peso alvo (botão "Escalonar" do app, ``Oc``).

    Como no app, o fator é ``alvo / peso final`` (já descontada a água
    evaporada) e cada item é arredondado a 0,1 g."""
    v = numero(alvo) if not isinstance(alvo, str) else _parse_float(alvo)
    if v is None or math.isnan(v) or v <= 0:
        raise ValueError("Informe um peso alvo válido maior que 0g.")
    total = avaliar(itens, ingredientes, TEMP_SERVIR_PADRAO, evaporada)["totais"]["gramas"]
    if total <= 0:
        raise ValueError("Adicione ingredientes com peso maior que 0g antes de escalonar.")
    e = v / total
    return [{**i, "gramas": js_round(i["gramas"] * e * 10) / 10} for i in itens]


def _parse_float(s: str):
    try:
        return float(s)
    except ValueError:
        return None


# --------------------------------------------------------------------------
# Auto-balanceamento (Fc)
# --------------------------------------------------------------------------
def _preparar_objetivo(itens, ingredientes, faixas, evaporada):
    """Monta a função objetivo do otimizador. Equivale a chamar ``avaliar`` e
    pontuar as métricas, mas só calcula o que o objetivo usa (sem a curva de
    congelamento), com a mesma ordem de operações do JS."""
    coef = []
    for item in itens:
        c = ingredientes.get(item.get("ingrediente"))
        if not c:
            coef.append(None)
            continue
        coef.append((
            _num_campo(c, "agua"),
            _num_campo(c, "gordura"),
            numero(c.get("proteina")),
            _num_campo(c, "acucares"),
            _num_campo(c, "sng"),
            _num_campo(c, "outros_solidos"),
            sng_pela_lactose(c),
            _num_campo(c, "pod"),
            _num_campo(c, "pac"),
        ))
    evap = numero(evaporada)
    alvos = []
    for chave in CHAVES_BALANCO:
        g, c = faixas[chave]
        f = (g + c) / 2
        h = max((c - g) / 2, 10 if chave in ("pod", "pac") else 0.5)
        alvos.append((PESOS_BALANCO[chave], g, c, f, h))

    def objetivo(gramas: Sequence[float]) -> float:
        tg = tw = tf = tp = ts = tm = to = tq = tpod = tpac = tts = 0.0
        for f, cf in zip(gramas, coef):
            tg += f
            if cf is None:
                continue
            h = f / 100
            w, fa, pr, su, ms, ot, eq, po, pa = cf
            sfa = h * fa
            ssu = h * su
            sms = h * ms
            sot = h * ot
            tw += h * w
            tf += sfa
            tp += h * pr
            ts += ssu
            tm += sms
            to += sot
            tq += h * eq
            tpod += h * po
            tpac += h * pa
            tts += sfa + ssu + sms + sot
        n = max(0, min(evap, tw))
        tg -= n
        if tg > 0:
            mf = (tf / tg) * 100
            mp = (tp / tg) * 100
            ms_ = (ts / tg) * 100
            mm = (tm / tg) * 100
            mo = (to / tg) * 100
            mts = (tts / tg) * 100
            mq = (tq / tg) * 100
            mpod = (tpod / tg) * 1e3
            mpac = (tpac / tg) * 1e3
        else:
            mf = mp = ms_ = mm = mo = mts = mq = mpod = mpac = 0
        lim = max(0, (100 - (ms_ + mf + mo)) * 0.15)
        y = 0
        if not (mq <= lim + 0.05):
            y += 30 * ((mq - lim) / 0.5) ** 2
        for (peso, g, c, f, h), s in zip(alvos, (mf, mp, ms_, mm, mo, mts, mpod, mpac)):
            p = (s - f) / h
            y += peso * 0.15 * p * p
            if s < g:
                y += peso * 10 * ((g - s) / h) ** 2
            elif s > c:
                y += peso * 10 * ((s - c) / h) ** 2
        return y

    return objetivo


def balancear(
    itens: Sequence[Item],
    ingredientes: Mapping[str, Ingrediente],
    faixas: Faixas,
    evaporada: float = 0,
    funcao_objetivo=None,
) -> dict:
    """Auto-balanceamento (``Fc``): busca local que transfere massa entre pares
    de ingredientes destravados (passos de 5%, 2%, 0,8%, 0,2% da massa e 0,5 g),
    minimizando a distância ao centro das faixas e penalizando fortemente o
    que sai delas. Ingredientes travados (``travado``) não mudam e a massa
    total é preservada (arredondada a 0,1 g).

    ``funcao_objetivo`` (novidade, opcional): função ``gramas -> custo`` que
    substitui o objetivo original (ex.: ``nutricao.objetivo_light``). Sem ela,
    o comportamento é exatamente o do app."""
    itens = list(itens)
    r = [i for i, m in enumerate(itens) if not m.get("travado") and ingredientes.get(m.get("ingrediente"))]
    if len(r) < 2:
        return {"sucesso": False, "mensagem": MSG_POUCOS_DESTRAVADOS, "itens": itens}
    massa = 0
    for m in itens:
        massa += numero(m.get("gramas"))
    if massa <= 0:
        return {"sucesso": False, "mensagem": MSG_MASSA_ZERO, "itens": itens}
    u = [max(0, numero(m.get("gramas"))) for m in itens]
    d = funcao_objetivo if funcao_objetivo is not None else _preparar_objetivo(itens, ingredientes, faixas, evaporada)
    inicial = d(u)
    x = inicial
    for passo in (massa * 0.05, massa * 0.02, massa * 0.008, massa * 0.002, 0.5):
        mudou = True
        cont = 0
        while mudou and cont < 80:
            cont += 1
            mudou = False
            for y in r:
                for mm in r:
                    if y == mm or u[mm] < passo:
                        continue
                    g = list(u)
                    g[y] = u[y] + passo
                    g[mm] = u[mm] - passo
                    c = d(g)
                    if c < x - 1e-9:
                        u = g
                        x = c
                        mudou = True
    u = [js_round(v * 10) / 10 for v in u]
    soma = 0
    for v in u:
        soma += v
    ajuste = js_round((massa - soma) * 10) / 10
    if ajuste != 0:
        m = r[0]
        for k in r:
            if u[k] > u[m]:
                m = k
        u[m] = max(0, js_round((u[m] + ajuste) * 10) / 10)
    novos = [{**item, "gramas": g} for item, g in zip(itens, u)]
    msg = MSG_JA_OTIMO if x >= inicial - 1e-9 else MSG_AJUSTADA
    return {"sucesso": True, "mensagem": msg, "itens": novos, "objetivo_inicial": inicial, "objetivo_final": x}


# --------------------------------------------------------------------------
# Validação de ingrediente (Rl)
# --------------------------------------------------------------------------
def validar_ingrediente(e: Mapping, constantes: Mapping | None = None) -> list[dict]:
    """Avisos de consistência da composição (``Rl``). ``nivel`` = error | warn."""
    k = constantes or carregar_constantes()

    def a(n):
        return numero(e.get(n))

    def fx(v, casas=1):
        from .jsnum import to_fixed
        return to_fixed(v, casas)

    def js(v):  # interpolação de número em template string do JS
        return _js_str(v)

    t: list[dict] = []
    o = a("agua") + a("gordura") + a("acucares") + a("sng") + a("outros_solidos") + a("alcool")
    if abs(o - 100) > 0.5:
        t.append({"nivel": "error", "texto": f"Água + gordura + açúcares + SNLG + outros sólidos + álcool soma {fx(o)}%; precisa dar 100%."})
    r = a("sng")
    lac = a("lactose")
    u = a("proteina")
    if lac > 0 and r <= 0:
        t.append({"nivel": "warn", "texto": "Tem lactose mas o SNLG está zerado: a lactose faz parte do SNLG."})
    if r > 0 and lac > 0.58 * r:
        t.append({"nivel": "warn", "texto": f"Lactose ({js(lac)}%) passa de ~55% do SNLG ({js(r)}%). No leite a lactose é ~54,5% do SNLG."})
    if r > 0 and lac > 0:
        n = (u + lac) / r
        if n > 1.02:
            t.append({"nivel": "warn", "texto": "Proteína + lactose maior que o SNLG: algum desses valores está alto."})
        elif n < 0.8:
            t.append({"nivel": "warn", "texto": f"SNLG alto para a proteína e a lactose informadas (no leite, proteína + lactose ≈ 90% do SNLG). Pela lactose, o SNLG seria ~{fx(lac / 0.545)}%."})
    if e.get("pod_pac_auto"):
        perfil = e.get("perfil_acucares") or {}

        def soma_grupo(grupo):
            s = 0
            for ac in k["acucares"]:
                if ac["grupo"] == grupo:
                    s = s + numero(perfil.get(ac["chave"]))
            return s

        i = soma_grupo("acucares")
        if abs(i - a("acucares")) > 1:
            t.append({"nivel": "warn", "texto": f"Os açúcares listados na composição somam {fx(i)}%, mas o campo Açúcares diz {js(a('acucares'))}%."})
        x = soma_grupo("outros_solidos")
        if x > a("outros_solidos") + 0.5:
            t.append({"nivel": "warn", "texto": f"Polióis, fibras, ácidos e sal somam {fx(x)}%, mais que os outros sólidos ({js(a('outros_solidos'))}%)."})
        if soma_grupo("sng") + lac > a("sng") + 0.5:
            t.append({"nivel": "warn", "texto": "Lactose + ácido lático passam do SNLG."})
    if a("acucares") + lac > 1 and a("pac") == 0 and a("pod") == 0:
        t.append({"nivel": "warn", "texto": "Há açúcar, mas POD e PAC estão zerados."})
    if a("acucares") > 5 and a("pac") < 0.3 * a("acucares"):
        t.append({"nivel": "warn", "texto": "PAC muito baixo para a quantidade de açúcar (sacarose vale 1 por grama; maltodextrina ~0,34)."})
    if a("pac") > 0 and a("acucares") + lac + a("outros_solidos") + a("alcool") == 0:
        t.append({"nivel": "warn", "texto": "PAC informado, mas não há açúcar, sólido ou álcool que o justifique."})
    return t


def _js_str(v: float) -> str:
    """``String(number)`` do JS para valores comuns (inteiros sem ``.0``)."""
    if v == int(v) and abs(v) < 1e21:
        return str(int(v))
    return repr(float(v))


def soma_composicao(e: Mapping) -> float:
    """Água + gordura + açúcares + SNG + outros sólidos + álcool (deve dar 100)."""
    return sum(numero(e.get(k)) for k in ("agua", "gordura", "acucares", "sng", "outros_solidos", "alcool"))
