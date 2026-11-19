"""CLI ``calda``: interface de linha de comando do Calda Certa.

Todo comando aceita ``--json`` (saída estruturada em stdout; erros em stderr
como ``{"erro": ...}`` e código de saída 1). Pensada para humanos e para
agentes de IA.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

from . import dados, motor, nutricao
from . import receita as rec
from .ficha import ficha_markdown, ficha_texto
from .jsnum import br, js_round, numero, to_fixed
from .pagina import gerar_html
from .relatorio import analisar, texto


class ErroCLI(Exception):
    pass


# ---------------------------------------------------------------- utilidades
def _saida(args, obj: Any, humano: str | None = None) -> None:
    if getattr(args, "json", False):
        json.dump(obj, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    elif humano is not None:
        sys.stdout.write(humano.rstrip("\n") + "\n")


def _avisos(args, avisos: list[str]) -> None:
    if avisos and not getattr(args, "json", False):
        for a in avisos:
            sys.stderr.write(f"aviso: {a}\n")


def _sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn").lower()


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", _sem_acento(s)).strip("_") or "item"


def _gravar_arquivo(caminho: str, conteudo: str) -> None:
    p = Path(caminho)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(conteudo)


def _tabela(linhas: list[list[str]], cab: list[str]) -> str:
    larg = [max(len(str(x)) for x in col) for col in zip(cab, *linhas)] if linhas else [len(c) for c in cab]
    fmt = lambda row: "  ".join(str(v).ljust(w) for v, w in zip(row, larg)).rstrip()
    return "\n".join([fmt(cab), fmt(["-" * w for w in larg])] + [fmt(r) for r in linhas])


# ------------------------------------------------------------- ingredientes
CAMPOS_NUM = (
    ("agua", "água (%)"),
    ("gordura", "gordura (%)"),
    ("proteina", "proteína (%)"),
    ("acucares", "açúcares sem lactose (%)"),
    ("sng", "sólidos não gordurosos do leite, SNG/SNLG (%)"),
    ("lactose", "lactose (%, parte do SNG)"),
    ("outros_solidos", "outros sólidos (%)"),
    ("alcool", "álcool (%)"),
    ("pod", "POD por 100 g (sacarose = 100)"),
    ("pac", "PAC por 100 g (sacarose = 100)"),
    ("custo_kg", "custo em R$/kg"),
)


# Campos opcionais novos (ausentes = comportamento original).
CAMPOS_OPCIONAIS = (
    ("kcal_100g", float, "kcal por 100 g (sobrepõe o cálculo pela composição; útil para polióis e açúcares raros)"),
    ("fibra", float, "fibra alimentar (%, parte dos outros sólidos; 2 kcal/g)"),
    ("cinzas", float, "minerais/cinzas (%, parte dos outros sólidos; 0 kcal)"),
    ("caseina", float, "caseína (%; padrão em lácteos: 80%% da proteína)"),
    ("dose_max_pct", float, "estabilizante: dose máxima em %% da calda (alerta acima)"),
    ("ativacao", str, "estabilizante: 'frio' ou 'quente' (temperatura de hidratação)"),
    ("defeito_excesso", str, "estabilizante: defeito de textura quando passa da dose"),
    ("fonte", str, "fonte da composição"),
)


def _banco_de(iid: str) -> str:
    """'base' (ingredientes.json) ou 'extra' (novidades.json)."""
    if any(i["id"] == iid for i in dados.ingredientes()):
        return "base"
    return "extra"


def _gravar_extras(lista: list[dict]):
    nov = dados.novidades()
    nov["ingredientes"] = lista
    return dados.gravar(dados.NOVIDADES, nov)


def cmd_ingredientes(args):
    lista = dados.ingredientes_todos() if getattr(args, "todos", False) else dados.ingredientes()
    if args.busca:
        b = _sem_acento(args.busca.strip())
        lista = [i for i in lista if b in _sem_acento(i["nome"]) or b in _sem_acento(i["categoria"]) or b in i["id"].lower()]
    if args.familia:
        f = _sem_acento(args.familia)
        lista = [i for i in lista if _sem_acento(i["categoria"]) == f or f in _sem_acento(i["categoria"])]
    linhas = [[i["id"], i["nome"], i["categoria"], br(i["gordura"], 1), br(i["acucares"], 1),
               br(i["pod"], 1), br(i["pac"], 1), br(i["custo_kg"], 2)] for i in lista]
    cats = sorted({i["categoria"] for i in dados.ingredientes()})
    humano = _tabela(linhas, ["id", "nome", "categoria", "gord%", "açúc%", "POD", "PAC", "R$/kg"])
    humano += f"\n\n{len(lista)} ingrediente(s). Categorias: {', '.join(cats)}"
    if not getattr(args, "todos", False) and dados.ingredientes_extra():
        humano += f"\n(+{len(dados.ingredientes_extra())} no banco complementar de novidades: use --todos)"
    _saida(args, lista, humano)


def cmd_ingrediente_mostrar(args):
    i = dados.achar_com_extras(dados.ingredientes(), dados.ingredientes_extra(), args.id, "ingrediente")
    i = dados.mapa_ingredientes_todos().get(i["id"], i)
    av = motor.validar_ingrediente(i)
    usos = [r["id"] for r in dados.receitas() if any(it["ingrediente"] == i["id"] for it in r["itens"])]
    usos_extra = [r["id"] for r in dados.receitas_extra() if any(it["ingrediente"] == i["id"] for it in r["itens"])]
    obj = {"ingrediente": i, "avisos": av, "sng_pela_lactose": motor.sng_pela_lactose(i), "usado_em": usos}
    h = [f"{i['nome']}  [{i['id']}]", f"Categoria: {i['categoria']}"]
    for k, rot in CAMPOS_NUM:
        h.append(f"  {rot:<48} {i.get(k, 0)}")
    h.append(f"  POD/PAC automáticos pelo perfil de açúcares: {'sim' if i.get('pod_pac_auto') else 'não'}")
    if i.get("perfil_acucares"):
        h.append("  Perfil de açúcares: " + ", ".join(f"{k}={v}" for k, v in i["perfil_acucares"].items()))
    if i.get("nota"):
        h.append(f"  Nota: {i['nota']}")
    for a in av:
        h.append(f"  [{a['nivel']}] {a['texto']}")
    if usos:
        h.append(f"  Usado em: {', '.join(usos)}")
    extras = [(c, i[c]) for c, _, _ in CAMPOS_OPCIONAIS if i.get(c) is not None]
    if extras or usos_extra:
        h.append(f"  kcal/100 g (estimativa): {br(nutricao.kcal_100g(i), 0)}")
        h += [f"  {c}: {v}" for c, v in extras]
        if usos_extra:
            h.append(f"  Usado nas receitas de novidades: {', '.join(usos_extra)}")
    _saida(args, obj, "\n".join(h))


def _int_se_inteiro(v: float):
    return int(v) if float(v).is_integer() else float(v)


def _parse_perfil(s: str | None) -> dict | None:
    if s is None:
        return None
    s = s.strip()
    if s.startswith("{"):
        return {k: _int_se_inteiro(float(v)) for k, v in json.loads(s).items()}
    out = {}
    for parte in filter(None, (p.strip() for p in s.split(";" if ";" in s else ","))):
        k, _, v = parte.partition("=")
        out[k.strip()] = _int_se_inteiro(float(v.replace(",", ".")))
    return out


def _aplicar_campos(base: dict, args) -> dict:
    if getattr(args, "de_json", None):
        fonte = sys.stdin.read() if args.de_json == "-" else Path(args.de_json).read_text(encoding="utf-8")
        base.update(json.loads(fonte))
    if args.nome is not None:
        base["nome"] = args.nome
    if args.categoria is not None:
        base["categoria"] = args.categoria
    for k, _ in CAMPOS_NUM:
        v = getattr(args, k)
        if v is not None:
            base[k] = v
    p = _parse_perfil(args.perfil_acucares)
    if p is not None:
        chaves = {a["chave"] for a in dados.carregar_constantes()["acucares"]}
        ruins = sorted(set(p) - chaves)
        if ruins:
            raise ErroCLI(f"chave(s) de perfil de açúcar desconhecida(s): {', '.join(ruins)}. Válidas: {', '.join(sorted(chaves))}")
        base["perfil_acucares"] = p
    if args.pod_pac_auto is not None:
        base["pod_pac_auto"] = args.pod_pac_auto
    if args.nota is not None:
        if args.nota == "":
            base.pop("nota", None)
        else:
            base["nota"] = args.nota
    for c, tipo, _ in CAMPOS_OPCIONAIS:
        v = getattr(args, c, None)
        if v is None:
            continue
        if v == "" and tipo is str:
            base.pop(c, None)
        else:
            base[c] = v
    if base.get("ativacao") is not None and base["ativacao"] not in nutricao.PROCESSOS:
        raise ErroCLI("ativacao deve ser 'frio' ou 'quente'")
    return base


def _finalizar_ingrediente(i: dict, forcar: bool) -> tuple[dict, list[dict]]:
    """Normaliza como o formulário do app (Number(x)||0) e valida."""
    if not str(i.get("nome", "")).strip():
        raise ErroCLI("Informe o nome do ingrediente (--nome).")
    soma = motor.soma_composicao(i)
    if abs(soma - 100) > 0.5 and not forcar:
        raise ErroCLI(
            f"Água + gordura + açúcares + SNG + outros sólidos + álcool soma {to_fixed(soma, 1)}%; precisa dar 100%."
        )
    from .jsnum import numero

    k = {
        "id": i.get("id"),
        "nome": str(i["nome"]).strip(),
        "categoria": i.get("categoria") or "Outros",
    }
    for c, _ in CAMPOS_NUM:
        k[c] = numero(i.get(c))
        if k[c] == int(k[c]):
            k[c] = int(k[c])
    k["pod_pac_auto"] = bool(i.get("pod_pac_auto", True))
    k["perfil_acucares"] = dict(i.get("perfil_acucares") or {})
    if i.get("nota"):
        k["nota"] = i["nota"]
    for c, tipo, _ in CAMPOS_OPCIONAIS:  # novidades: preservados se presentes
        if i.get(c) is not None:
            k[c] = (_int_se_inteiro(numero(i[c])) if tipo is float else str(i[c]))
    if k["pod_pac_auto"]:
        k.update(motor.pod_pac_automatico(k))
    avisos = [a for a in motor.validar_ingrediente(k) if a["nivel"] != "error"]
    return k, avisos


def cmd_ingrediente_adicionar(args):
    lista = dados.ingredientes()
    novo = _aplicar_campos({"pod_pac_auto": True, "perfil_acucares": {}}, args)
    ing, avisos = _finalizar_ingrediente(novo, args.forcar)
    ids = {i["id"] for i in lista}
    if args.id or novo.get("id"):
        ing["id"] = args.id or novo["id"]
        if ing["id"] in ids:
            raise ErroCLI(f"já existe ingrediente com id {ing['id']} (use 'calda ingrediente editar')")
    else:
        base = f"ing_custom_{_slug(ing['nome'])}"
        ing["id"], n = base, 2
        while ing["id"] in ids:
            ing["id"], n = f"{base}_{n}", n + 1
    caminho = dados.gravar("ingredientes.json", [ing] + lista)  # como o app: novo no topo
    _avisos(args, [a["texto"] for a in avisos])
    _saida(args, {"ingrediente": ing, "avisos": avisos, "arquivo": str(caminho)},
           f'Ingrediente "{ing["nome"]}" cadastrado no banco como {ing["id"]} ({caminho}).')


def cmd_ingrediente_editar(args):
    atual = dados.achar_com_extras(dados.ingredientes(), dados.ingredientes_extra(), args.id, "ingrediente")
    banco = _banco_de(atual["id"])
    lista = dados.ingredientes() if banco == "base" else dados.ingredientes_extra()
    novo = _aplicar_campos(dict(atual), args)
    novo["id"] = atual["id"]
    ing, avisos = _finalizar_ingrediente(novo, args.forcar)
    nova_lista = [ing if i["id"] == atual["id"] else i for i in lista]
    caminho = dados.gravar("ingredientes.json", nova_lista) if banco == "base" else _gravar_extras(nova_lista)
    _avisos(args, [a["texto"] for a in avisos])
    _saida(args, {"ingrediente": ing, "avisos": avisos, "arquivo": str(caminho)},
           f'Ingrediente "{ing["nome"]}" atualizado ({caminho}).')


def cmd_ingrediente_remover(args):
    alvo = dados.achar_com_extras(dados.ingredientes(), dados.ingredientes_extra(), args.id, "ingrediente")
    banco = _banco_de(alvo["id"])
    lista = dados.ingredientes() if banco == "base" else dados.ingredientes_extra()
    receitas = dados.receitas() if banco == "base" else dados.receitas_todos()
    usos = [r["id"] for r in receitas if any(it["ingrediente"] == alvo["id"] for it in r["itens"])]
    if usos and not args.forcar:
        raise ErroCLI(f"{alvo['id']} é usado em: {', '.join(usos)}. Use --forcar para remover mesmo assim.")
    restante = [i for i in lista if i["id"] != alvo["id"]]
    caminho = dados.gravar("ingredientes.json", restante) if banco == "base" else _gravar_extras(restante)
    _saida(args, {"removido": alvo["id"], "usado_em": usos, "arquivo": str(caminho)},
           f'Ingrediente "{alvo["nome"]}" removido do banco ({caminho}).')


# ----------------------------------------------------------------- receitas
def cmd_receitas(args):
    todos = getattr(args, "todos", False)
    ings = dados.mapa_ingredientes_todos()
    maqs = {m["id"]: m for m in dados.maquinas()}
    perfs = {p["id"]: p for p in (dados.perfis_todos() if todos else dados.perfis())}
    lista = dados.receitas_todos() if todos else dados.receitas()
    if args.busca:
        b = _sem_acento(args.busca)
        lista = [r for r in lista if b in _sem_acento(r["nome"]) or b in r["id"].lower()]
    if args.perfil:
        lista = [r for r in lista if r.get("perfil") == args.perfil]
    out, linhas = [], []
    for r in lista:
        z = motor.avaliar(r["itens"], ings, -12, r.get("evaporada_g", 0))  # como a biblioteca do app (-12 °C)
        maq = maqs.get(r.get("maquina")) or dados.maquinas()[0]
        perf = perfs.get(r.get("perfil")) or dados.perfis()[0]
        zm = motor.avaliar(r["itens"], ings, maq["temp_servir"], r.get("evaporada_g", 0))
        conf = motor.conformidade(zm["metricas"], motor.faixas_alvo(perf, maq))
        resumo = {
            "id": r["id"], "nome": r["nome"], "versao": r["versao"], "perfil": r.get("perfil"), "maquina": r.get("maquina"),
            "status": r.get("status"), "peso_g": z["totais"]["gramas"], "gordura": z["metricas"]["gordura"],
            "solidos_totais": z["metricas"]["solidos_totais"], "pod": z["metricas"]["pod"], "pac": z["metricas"]["pac"],
            "custo_kg": z["custo_kg"], "faixa_verde": f"{conf['ideal']}/{conf['total']}",
        }
        out.append(resumo)
        linhas.append([r["id"], f"{r['nome']} ({r['versao']})", r.get("perfil") or "", r.get("maquina") or "",
                       br(resumo["peso_g"], 0), br(resumo["gordura"], 1), br(resumo["pod"], 0),
                       br(resumo["pac"], 0), br(resumo["custo_kg"], 2), resumo["faixa_verde"]])
    extra = ""
    if not todos and dados.receitas_extra():
        extra = f"\n(+{len(dados.receitas_extra())} receita(s) de novidades: use --todos)"
    _saida(args, out, _tabela(linhas, ["id", "nome", "perfil", "máquina", "g", "gord%", "POD", "PAC", "R$/kg", "verde"])
           + f"\n\n{len(out)} receita(s)." + extra)


def cmd_receita_mostrar(args):
    r, avisos = rec.carregar(args.id)
    _avisos(args, avisos)
    obj = rec.para_arquivo(r)
    if args.json or not args.resumo:
        json.dump(obj, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")


def cmd_receita_salvar(args):
    r, avisos = rec.carregar(args.arquivo)
    _avisos(args, avisos)
    if args.id:
        r["id"] = args.id
    lista = dados.receitas()
    hoje = _dt.date.today().isoformat()
    idx = next((k for k, x in enumerate(lista) if x["id"] == r.get("id")), -1)
    r["atualizada_em"] = hoje
    if idx >= 0:
        base = lista[idx]
        r["status"] = r.get("status") or base.get("status")
        r["notas"] = r.get("notas") if r.get("notas") is not None else base.get("notas")
        novo = rec.para_arquivo(r)
        lista[idx] = novo
        msg = f'Receita "{r["nome"]} ({r["versao"]})" atualizada na biblioteca.'
    else:
        r["id"] = r.get("id") or f"rec_{_slug(r['nome'])}_{_slug(r['versao'])}"
        ids = {x["id"] for x in lista}
        base_id, n = r["id"], 2
        while r["id"] in ids:
            r["id"], n = f"{base_id}_{n}", n + 1
        # como o app: receita nova entra "Em Teste" (o rótulo "Exemplo" é só das receitas de fábrica)
        r["status"] = r.get("status") if r.get("status") not in (None, "", "Exemplo") else "Em Teste"
        r["notas"] = r.get("notas") or "Formulada na bancada do Calda Certa."
        novo = rec.para_arquivo(r)
        lista = [novo] + lista
        msg = f'Nova receita "{r["nome"]} ({r["versao"]})" salva na biblioteca como {r["id"]}.'
    caminho = dados.gravar("receitas.json", lista)
    _saida(args, {"receita": novo, "arquivo": str(caminho)}, msg + f" ({caminho})")


def cmd_receita_remover(args):
    lista = dados.receitas()
    alvo = dados.achar(lista, args.id, "receita")
    caminho = dados.gravar("receitas.json", [r for r in lista if r["id"] != alvo["id"]])
    _saida(args, {"removida": alvo["id"], "arquivo": str(caminho)}, f'Receita "{alvo["nome"]}" excluída ({caminho}).')


def cmd_maquinas(args):
    lista = dados.maquinas()
    h = []
    for m in lista:
        aj = f"+{m['ajuste_pac']}" if m["ajuste_pac"] > 0 else "±0"
        h.append(f"{m['id']}: {m['nome']}\n  PAC alvo {aj} pts sobre a vitrine · referência {m['temp_servir']} °C · lote {m['lote_g']} g")
        h.append(f"  {m['nota_lote']}")
        h += [f"  - {d}" for d in m["dicas"]]
        h += [f"  * {o}" for o in nutricao.orientacoes_maquina(m)]
    _saida(args, lista, "\n".join(h))


def cmd_perfis(args):
    lista = dados.perfis_todos() if getattr(args, "todos", False) else dados.perfis()
    k = dados.carregar_constantes()
    h = []
    for p in lista:
        h.append(f"{p['id']}: {p['nome']}  [{p['grupo']}]\n  {p['descricao']}")
        h.append("  " + " · ".join(
            f"{m['rotulo'].split(' (')[0]} {p['faixas'][m['chave']][0]:g}–{p['faixas'][m['chave']][1]:g}" for m in k["metricas"]
        ))
    if not getattr(args, "todos", False) and dados.perfis_extra():
        h.append(f"\n(+{len(dados.perfis_extra())} perfil(is) de novidades: use --todos)")
    _saida(args, lista, "\n".join(h))


# ----------------------------------------------------------- análise & cia.
def _lote(args, maquina, receita=None, ings=None) -> float | None:
    v = getattr(args, "lote", None)
    if v is None:
        return None
    if str(v).lower() in ("maquina", "máquina"):
        return float(maquina["lote_g"])
    if str(v).lower().startswith("pote"):
        # novidade: gramas que cabem no pote da máquina (ml até a linha MAX × folga × densidade estimada)
        _, _, pid = str(v).partition(":")
        if pid:
            args.pote = pid  # a nutrição "por pote" usa o mesmo pote
        pid = pid or getattr(args, "pote", None)
        if not nutricao.potes(maquina):
            raise ErroCLI(f"a máquina {maquina['id']} não tem potes cadastrados (use --lote N ou 'maquina')")
        evap = receita.get("evaporada_g", 0) if args.evaporada is None else args.evaporada
        z = motor.avaliar(receita["itens"], ings, maquina["temp_servir"], evap)
        if z["totais"]["gramas"] <= 0:
            raise ErroCLI("Adicione ingredientes com peso maior que 0g antes de escalonar.")
        info = nutricao.info_pote(maquina, pid, z["metricas"])
        return js_round(info["gramas"])
    try:
        return float(str(v).replace(",", "."))
    except ValueError:
        raise ErroCLI("--lote deve ser um número de gramas ou 'maquina'")


def _carregar_contexto(args):
    r, avisos = rec.carregar(args.receita)
    travar = [s.strip() for s in (getattr(args, "travar", None) or "").split(",") if s.strip()]
    liberar = [s.strip() for s in (getattr(args, "liberar", None) or "").split(",") if s.strip()]
    ids = {i["ingrediente"] for i in r["itens"]}
    for t in travar + [x for x in liberar if x != "todos"]:
        if t not in ids:
            raise ErroCLI(f"ingrediente {t} não está na receita")
    for i in r["itens"]:
        if "todos" in liberar or i["ingrediente"] in liberar:
            i["travado"] = False
        if i["ingrediente"] in travar:
            i["travado"] = True
    for b in getattr(args, "brix", None) or []:
        for parte in filter(None, (x.strip() for x in b.split(";" if ";" in b else ","))):
            iid, _, val = parte.partition("=")
            iid = iid.strip()
            if not val:
                raise ErroCLI("--brix deve ser ingrediente=valor (ex.: ing_polpa_manga=15.5)")
            if iid not in ids:
                raise ErroCLI(f"ingrediente {iid} não está na receita")
            try:
                v = float(val.replace(",", "."))
            except ValueError:
                raise ErroCLI(f"Brix inválido: {val}")
            for i in r["itens"]:
                if i["ingrediente"] == iid:
                    i["brix"] = v
    if getattr(args, "processo", None):
        r["processo"] = args.processo
    maq = rec.resolver_maquina(r, args.maquina)
    perf = rec.resolver_perfil(r, args.perfil)
    r["maquina"], r["perfil"] = maq["id"], perf["id"]
    return r, maq, perf, avisos


def _ings(r) -> dict:
    """Banco completo com as leituras de Brix da receita aplicadas."""
    return nutricao.aplicar_brix(dados.mapa_ingredientes_todos(), r["itens"])[0]


def _analisar(args, r, maq, perf, lote=None, **kw):
    return analisar(r, maq, perf, args.evaporada, lote, porcao_g=getattr(args, "porcao", None),
                    pote=getattr(args, "pote", None), peso_kg=getattr(args, "peso_kg", None), **kw)


def cmd_analisar(args):
    r, maq, perf, avisos = _carregar_contexto(args)
    a = _analisar(args, r, maq, perf, _lote(args, maq, r, _ings(r)))
    a["avisos"] = avisos
    _avisos(args, avisos)
    _saida(args, a, texto(a))


def cmd_balancear(args):
    r, maq, perf, avisos = _carregar_contexto(args)
    ings_todos = dados.mapa_ingredientes_todos()
    presentes = {i["ingrediente"] for i in r["itens"]}
    for iid in [x.strip() for x in (getattr(args, "incluir", None) or "").split(",") if x.strip()]:
        if iid not in ings_todos:
            raise ErroCLI(f"ingrediente {iid} não existe no banco")
        if iid not in presentes:  # novidade: entra com 0 g, destravado, para o otimizador poder usar
            r["itens"].append({"ingrediente": iid, "gramas": 0, "travado": False})
            presentes.add(iid)
    ings = _ings(r)
    lote = _lote(args, maq, r, ings)
    antes = _analisar(args, r, maq, perf, lote)
    base = antes["receita"]
    faixas = antes["faixas"]
    objetivo = getattr(args, "objetivo", None) or "padrao"
    if objetivo == "padrao" and getattr(args, "proteina_min", None) is not None:
        raise ErroCLI("--proteina-min só vale com --objetivo light")
    funcao = None
    if objetivo == "light":
        funcao, _ = nutricao.objetivo_light(base["itens"], ings, faixas, base["evaporada_g"], args.proteina_min,
                                            porcao_g=args.porcao, peso_kg=args.peso_kg)
    res = motor.balancear(base["itens"], ings, faixas, base["evaporada_g"], funcao_objetivo=funcao)
    if not res["sucesso"]:
        raise ErroCLI(res["mensagem"])
    nova = dict(base)
    nova["itens"] = [{"ingrediente": i["ingrediente"], "gramas": i["gramas"], "travado": bool(i.get("travado"))} for i in res["itens"]]
    soma = 0
    for i in nova["itens"]:
        soma += i["gramas"]
    from .jsnum import js_round

    nova["lote_g"] = js_round(soma) or 1000
    depois = analisar(nova, maq, perf, base["evaporada_g"], porcao_g=getattr(args, "porcao", None),
                      pote=getattr(args, "pote", None), peso_kg=getattr(args, "peso_kg", None))
    arquivo = rec.para_arquivo(nova)
    if args.saida:
        _gravar_arquivo(args.saida, json.dumps(arquivo, ensure_ascii=False, indent=2) + "\n")
    _avisos(args, avisos)
    obj = {
        "mensagem": res["mensagem"],
        "receita": arquivo,
        "faixa_verde_antes": f"{antes['conformidade']['ideal']}/{antes['conformidade']['total']}",
        "faixa_verde_depois": f"{depois['conformidade']['ideal']}/{depois['conformidade']['total']}",
        "mudancas": [
            {"ingrediente": a["ingrediente"], "antes_g": a["gramas"], "depois_g": b["gramas"], "travado": bool(a.get("travado"))}
            for a, b in zip(base["itens"], nova["itens"])
        ],
        "analise": depois,
        "avisos": avisos,
        "arquivo": args.saida,
    }
    h = [res["mensagem"], f"Faixa verde: {obj['faixa_verde_antes']} → {obj['faixa_verde_depois']}", ""]
    if objetivo == "light":
        ka, kd = antes["nutricao"]["kcal_100g"], depois["nutricao"]["kcal_100g"]
        pa, pd = antes["nutricao"]["proteina_pct"], depois["nutricao"]["proteina_pct"]
        obj["objetivo"] = "light"
        obj["proteina_min"] = args.proteina_min
        obj["kcal_100g_antes"], obj["kcal_100g_depois"] = ka, kd
        obj["proteina_pct_antes"], obj["proteina_pct_depois"] = pa, pd
        h.insert(2, f"Objetivo light: {br(ka, 0)} → {br(kd, 0)} kcal/100 g · proteína {br(pa, 1)}% → {br(pd, 1)}%"
                 + (f" (mínimo {br(args.proteina_min, 1)}%{'' if pd >= args.proteina_min - 0.05 else ': NÃO atingido'})"
                    if args.proteina_min is not None else ""))
    for m in obj["mudancas"]:
        nome = ings.get(m["ingrediente"], {}).get("nome", m["ingrediente"])
        delta = m["depois_g"] - numero_seguro(m["antes_g"])
        h.append(f"  {nome:<40} {br(numero_seguro(m['antes_g']), 1):>8} → {br(m['depois_g'], 1):>8} g"
                 + (f"  ({'+' if delta > 0 else ''}{br(delta, 1)})" if abs(delta) > 1e-9 else "")
                 + ("  [travado]" if m["travado"] else ""))
    h += ["", texto(depois)]
    if args.saida:
        h.append(f"\nReceita balanceada gravada em {args.saida}")
    _saida(args, obj, "\n".join(h))


def numero_seguro(x) -> float:
    from .jsnum import numero

    return numero(x)


def cmd_ficha(args):
    r, maq, perf, avisos = _carregar_contexto(args)
    ings = _ings(r)
    a = _analisar(args, r, maq, perf, _lote(args, maq, r, ings))
    rr = a["receita"]
    if args.formato == "texto":
        conteudo = ficha_texto(rr["nome"], rr["versao"], rr["itens"], ings, perf, maq, rr["evaporada_g"]) + "\n"
    else:
        conteudo = ficha_markdown(rr["nome"], rr["versao"], rr["itens"], ings, perf, maq, rr["evaporada_g"], rr.get("notas"),
                                  porcao_g=getattr(args, "porcao", None), pote=getattr(args, "pote", None),
                                  processo=rr.get("processo"), peso_kg=getattr(args, "peso_kg", None))
    _avisos(args, avisos)
    if args.saida:
        _gravar_arquivo(args.saida, conteudo)
    obj = {"formato": args.formato, "conteudo": conteudo, "arquivo": args.saida}
    if args.saida and not args.json:
        sys.stdout.write(f"Ficha gravada em {args.saida}\n")
    else:
        _saida(args, obj, conteudo)


def cmd_pagina(args):
    r, maq, perf, avisos = _carregar_contexto(args)
    ings = _ings(r)
    a = _analisar(args, r, maq, perf, _lote(args, maq, r, ings))
    rr = a["receita"]
    ft = ficha_texto(rr["nome"], rr["versao"], rr["itens"], ings, perf, maq, rr["evaporada_g"])
    html = gerar_html(a, ft)
    _gravar_arquivo(args.saida, html)
    _avisos(args, avisos)
    _saida(args, {"arquivo": args.saida, "bytes": len(html.encode("utf-8"))}, f"Página gravada em {args.saida}")


# ------------------------------------------------------------------ parser
def _parser() -> argparse.ArgumentParser:
    comum = argparse.ArgumentParser(add_help=False)
    comum.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                       help="saída em JSON (para agentes e scripts)")

    p = argparse.ArgumentParser(
        prog="calda",
        description="Calda Certa: balanceamento de sorvetes, gelatos e sorbets.",
        epilog="Dados: variável CALDA_DADOS aponta um diretório com ingredientes.json, receitas.json, "
        "maquinas.json, perfis.json e constantes.json (lidos de lá quando existirem; gravações vão para lá).",
    )
    p.add_argument("--json", action="store_true", help="saída em JSON (para agentes e scripts)")
    sub = p.add_subparsers(dest="comando", metavar="comando", required=True)

    s = sub.add_parser("ingredientes", parents=[comum], help="lista o banco de ingredientes")
    s.add_argument("--busca", help="trecho do nome, categoria ou id")
    s.add_argument("--familia", "--categoria", dest="familia", help="categoria (ex.: Lácteos, Açúcares, Frutas)")
    s.add_argument("--todos", action="store_true", help="inclui o banco complementar de novidades")
    s.set_defaults(func=cmd_ingredientes)

    ing = sub.add_parser("ingrediente", parents=[comum], help="mostra, adiciona, edita ou remove um ingrediente")
    isub = ing.add_subparsers(dest="acao", metavar="ação", required=True)
    s = isub.add_parser("mostrar", parents=[comum], help="detalhes, avisos e receitas que usam")
    s.add_argument("id")
    s.set_defaults(func=cmd_ingrediente_mostrar)

    def campos(sp, novo: bool):
        sp.add_argument("--nome")
        sp.add_argument("--categoria")
        for k, rot in CAMPOS_NUM:
            sp.add_argument(f"--{k.replace('_', '-')}", dest=k, type=float, help=rot)
        sp.add_argument("--perfil-acucares", dest="perfil_acucares",
                        help="composição de açúcares em %% do ingrediente: 'sacarose=10,glicose=5' ou JSON")
        g = sp.add_mutually_exclusive_group()
        g.add_argument("--pod-pac-auto", dest="pod_pac_auto", action="store_const", const=True,
                       help="calcular POD/PAC pelo perfil de açúcares, lactose e álcool (padrão para novos)")
        g.add_argument("--pod-pac-manual", dest="pod_pac_auto", action="store_const", const=False,
                       help="usar --pod/--pac informados")
        sp.add_argument("--nota", help="observação ('' apaga)")
        sp.add_argument("--de-json", dest="de_json", help="lê os campos de um arquivo JSON (ou - para stdin)")
        sp.add_argument("--forcar", action="store_true", help="aceita composição que não soma 100%%")
        for c, tipo, ajuda in CAMPOS_OPCIONAIS:
            kw = {"choices": nutricao.PROCESSOS} if c == "ativacao" else {}
            sp.add_argument(f"--{c.replace('_', '-')}", dest=c, type=tipo, help=ajuda, **kw)
        if novo:
            sp.add_argument("--id", help="id (padrão: ing_custom_<nome>)")

    s = isub.add_parser("adicionar", parents=[comum], help="cadastra ingrediente (composição deve somar 100%%)")
    campos(s, True)
    s.set_defaults(func=cmd_ingrediente_adicionar)
    s = isub.add_parser("editar", parents=[comum], help="altera campos de um ingrediente")
    s.add_argument("id")
    campos(s, False)
    s.set_defaults(func=cmd_ingrediente_editar)
    s = isub.add_parser("remover", parents=[comum], help="remove um ingrediente do banco")
    s.add_argument("id")
    s.add_argument("--forcar", action="store_true", help="remove mesmo se usado em receitas")
    s.set_defaults(func=cmd_ingrediente_remover)

    s = sub.add_parser("receitas", parents=[comum], help="lista a biblioteca de receitas")
    s.add_argument("--busca")
    s.add_argument("--perfil", help="id do perfil (ex.: fam_branca)")
    s.add_argument("--todos", action="store_true", help="inclui as receitas de novidades")
    s.set_defaults(func=cmd_receitas)

    rc = sub.add_parser("receita", parents=[comum], help="mostra, salva ou remove uma receita da biblioteca")
    rsub = rc.add_subparsers(dest="acao", metavar="ação", required=True)
    s = rsub.add_parser("mostrar", parents=[comum], help="imprime a receita no formato de arquivo (JSON)")
    s.add_argument("id")
    s.set_defaults(func=cmd_receita_mostrar, resumo=False)
    s = rsub.add_parser("salvar", parents=[comum], help="grava um arquivo de receita na biblioteca (atualiza se o id existir)")
    s.add_argument("arquivo")
    s.add_argument("--id", help="id na biblioteca (padrão: o do arquivo, ou rec_<nome>_<versão>)")
    s.set_defaults(func=cmd_receita_salvar)
    s = rsub.add_parser("remover", parents=[comum], help="exclui uma receita da biblioteca")
    s.add_argument("id")
    s.set_defaults(func=cmd_receita_remover)

    s = sub.add_parser("maquinas", parents=[comum], help="lista máquinas (ajuste de PAC, temperatura, lote)")
    s.set_defaults(func=cmd_maquinas)
    s = sub.add_parser("perfis", parents=[comum], help="lista perfis/estilos com as faixas alvo")
    s.add_argument("--todos", action="store_true", help="inclui os perfis de novidades")
    s.set_defaults(func=cmd_perfis)

    def ctx(sp, travas=False):
        sp.add_argument("receita", help="arquivo .json, '-' (stdin) ou id/nome de receita da biblioteca")
        sp.add_argument("--maquina", help="id da máquina (padrão: a da receita)")
        sp.add_argument("--perfil", help="id do perfil (padrão: o da receita)")
        sp.add_argument("--lote", help="escala a receita para N gramas finais, 'maquina' (lote da máquina) ou "
                        "'pote[:ID]' (gramas que cabem no pote da máquina, pela densidade estimada)")
        sp.add_argument("--evaporada", type=float, help="água evaporada no cozimento, em g (padrão: a da receita)")
        sp.add_argument("--porcao", type=float, help="tamanho da porção em g para a nutrição (padrão: 100)")
        sp.add_argument("--pote", help="pote da máquina para nutrição/lote (ex.: padrao, deluxe; padrão: o primeiro)")
        sp.add_argument("--brix", action="append",
                        help="Brix medido: ingrediente=valor (repetível ou separado por vírgula), ex.: ing_polpa_manga=15.5")
        sp.add_argument("--peso-kg", dest="peso_kg", type=float,
                        help="peso corporal (kg) para o teto de eritritol por porção (1/3 da IDA da EFSA; padrão 70)")
        sp.add_argument("--processo", choices=nutricao.PROCESSOS,
                        help="processo da calda ('frio' ou 'quente'); sobrepõe o da receita (alerta de estabilizante)")
        if travas:
            sp.add_argument("--travar", help="ids de ingredientes a travar, separados por vírgula")
            sp.add_argument("--liberar", help="ids a destravar, separados por vírgula, ou 'todos'")

    s = sub.add_parser("analisar", parents=[comum], help="dashboard completo: métricas, faixas, congelamento, custo")
    ctx(s)
    s.set_defaults(func=cmd_analisar)
    s = sub.add_parser("balancear", parents=[comum], help="auto-balanceia os ingredientes destravados")
    ctx(s, travas=True)
    s.add_argument("-o", "--saida", help="grava a receita balanceada neste arquivo .json")
    s.add_argument("--objetivo", choices=("padrao", "light"), default="padrao",
                   help="padrao = algoritmo original; light = mesmas faixas verdes, penalizando kcal")
    s.add_argument("--proteina-min", dest="proteina_min", type=float,
                   help="com --objetivo light: proteína mínima em %% da calda")
    s.add_argument("--incluir", help="ids de ingredientes a acrescentar com 0 g (destravados) antes de balancear")
    s.set_defaults(func=cmd_balancear)
    s = sub.add_parser("ficha", parents=[comum], help="ficha técnica (Markdown ou o texto do botão copiar do app)")
    ctx(s)
    s.add_argument("--formato", choices=("md", "texto"), default="md")
    s.add_argument("-o", "--saida", help="grava neste arquivo")
    s.set_defaults(func=cmd_ficha)
    s = sub.add_parser("pagina", parents=[comum], help="relatório HTML estático e autocontido")
    ctx(s)
    s.add_argument("-o", "--saida", required=True, help="arquivo .html de saída")
    s.set_defaults(func=cmd_pagina)
    return p


def main(argv: list[str] | None = None) -> int:
    for fluxo in (sys.stdout, sys.stderr):
        try:
            fluxo.reconfigure(encoding="utf-8", newline="\n")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass
    p = _parser()
    args = p.parse_args(argv)
    try:
        args.func(args)
    except (ErroCLI, KeyError, ValueError, FileNotFoundError, json.JSONDecodeError) as e:
        msg = e.args[0] if isinstance(e, KeyError) and e.args else str(e)
        if getattr(args, "json", False):
            json.dump({"erro": msg}, sys.stderr, ensure_ascii=False)
            sys.stderr.write("\n")
        else:
            sys.stderr.write(f"erro: {msg}\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
