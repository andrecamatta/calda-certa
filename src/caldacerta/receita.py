"""Arquivo de receita: leitura, normalização e resolução de máquina/perfil.

Formato (JSON)::

    {
      "nome": "Fior di Latte", "versao": "V1.0",
      "maquina": "mac_kitchenaid_freezer", "perfil": "fam_branca",
      "lote_g": 1000, "evaporada_g": 0,
      "itens": [{"ingrediente": "ing_leite_int", "gramas": 585, "travado": false}, ...]
    }

Também aceita o formato interno do app original (``name``, ``version``,
``familyId``, ``machineId``, ``evaporation``, ``items`` com ``ingredientId``,
``grams``, ``locked``), útil para receitas exportadas do navegador.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from . import dados
from .jsnum import js_round, numero


def normalizar(r: Mapping[str, Any]) -> dict:
    itens_brutos = r.get("itens", r.get("items")) or []
    itens = []
    for i in itens_brutos:
        item = {
            "ingrediente": i.get("ingrediente", i.get("ingredientId")),
            "gramas": i.get("gramas", i.get("grams", 0)),
            "travado": bool(i.get("travado", i.get("locked", False))),
        }
        if i.get("brix") is not None:  # novidade: Brix medido (só quando informado)
            item["brix"] = numero(i["brix"])
        itens.append(item)
    out = {
        "id": r.get("id"),
        "nome": r.get("nome", r.get("name")) or "Receita Sem Nome",
        "versao": r.get("versao", r.get("version")) or "V1.0",
        "perfil": r.get("perfil", r.get("familyId")),
        "maquina": r.get("maquina", r.get("machineId")),
        "status": r.get("status"),
        "notas": r.get("notas", r.get("notes")),
        "atualizada_em": r.get("atualizada_em", r.get("updatedAt")),
        "lote_g": r.get("lote_g"),
        "evaporada_g": numero(r.get("evaporada_g", r.get("evaporation", 0))),
        "itens": itens,
    }
    processo = r.get("processo")
    if processo is not None:  # novidade: "frio" | "quente"
        if processo not in ("frio", "quente"):
            raise ValueError(f"processo inválido: {processo!r} (use 'frio' ou 'quente')")
        out["processo"] = processo
    if out["lote_g"] is None:
        soma = 0
        for i in itens:
            soma += numero(i["gramas"])
        out["lote_g"] = js_round(soma) or 1000
    return {k: v for k, v in out.items() if v is not None or k in ("perfil", "maquina")}


def aplicar_substituicoes(receita: dict) -> list[str]:
    """Troca ingredientes removidos do banco pelos substitutos, como a migração
    do app (``bl``): gramas × fator, arredondado a 0,1 g. Devolve avisos."""
    subs = dados.carregar_constantes().get("substituicoes", {})
    avisos = []
    for item in receita["itens"]:
        s = subs.get(item["ingrediente"])
        if s:
            novo = js_round(numero(item["gramas"]) * s["fator"] * 10) / 10
            avisos.append(f"{item['ingrediente']} trocado por {s['para']} ({item['gramas']} g → {novo:g} g): {s['motivo']}")
            item["ingrediente"] = s["para"]
            item["gramas"] = novo
    return avisos


def carregar(arg: str) -> tuple[dict, list[str]]:
    """Carrega de um arquivo .json (ou ``-`` para stdin) ou da biblioteca (id/nome)."""
    import sys

    if arg == "-":
        bruto = json.load(sys.stdin)
    else:
        p = Path(arg)
        if p.suffix.lower() == ".json" or p.exists():
            if not p.exists():
                raise FileNotFoundError(f"arquivo de receita não encontrado: {arg}")
            bruto = json.loads(p.read_text(encoding="utf-8"))
        else:
            bruto = dados.achar_com_extras(dados.receitas(), dados.receitas_extra(), arg, "receita")
    if isinstance(bruto, list):
        raise ValueError("o arquivo deve conter UMA receita (objeto JSON), não uma lista")
    r = normalizar(bruto)
    avisos = aplicar_substituicoes(r)
    ings = dados.mapa_ingredientes_todos()
    for i in r["itens"]:
        if i["ingrediente"] not in ings:
            avisos.append(f"ingrediente fora do banco: {i['ingrediente']} (conta só no peso)")
    return r, avisos


def resolver_maquina(receita: Mapping, maquina: str | None) -> dict:
    lista = dados.maquinas()
    chave = maquina or receita.get("maquina")
    if not chave:
        return lista[0]  # como o app: ga.find(...) || ga[0]
    return dados.achar(lista, chave, "máquina")


def resolver_perfil(receita: Mapping, perfil: str | None) -> dict:
    lista = dados.perfis()
    chave = perfil or receita.get("perfil")
    if not chave:
        return lista[0]  # como o app: r.find(...) || r[0]
    return dados.achar_com_extras(lista, dados.perfis_extra(), chave, "perfil")


def para_arquivo(r: Mapping) -> dict:
    """Receita no formato do arquivo (sem campos vazios)."""
    ordem = ("id", "nome", "versao", "perfil", "maquina", "status", "notas", "atualizada_em", "lote_g", "evaporada_g")
    out = {k: r[k] for k in ordem if r.get(k) is not None}
    for k in ("lote_g", "evaporada_g"):
        if isinstance(out.get(k), float) and out[k].is_integer():
            out[k] = int(out[k])
    if r.get("processo") is not None:
        out["processo"] = r["processo"]
    out["itens"] = [_item_arquivo(i) for i in r["itens"]]
    return out


def _item_arquivo(i: Mapping) -> dict:
    out = {"ingrediente": i["ingrediente"], "gramas": i["gramas"], "travado": bool(i.get("travado"))}
    if i.get("brix") is not None:
        b = i["brix"]
        out["brix"] = int(b) if isinstance(b, float) and b.is_integer() else b
    return out
