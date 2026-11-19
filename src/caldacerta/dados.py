"""Leitura e gravação dos arquivos de dados (JSON).

Os dados padrão vêm em ``caldacerta/data``. Se a variável de ambiente
``CALDA_DADOS`` apontar para um diretório, cada arquivo é lido de lá quando
existir (senão, do pacote) e TODA gravação vai para lá. Sem ``CALDA_DADOS``,
as gravações alteram os arquivos do próprio pacote (útil num checkout do
repositório: as mudanças aparecem no ``git diff``).
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

PACOTE = Path(__file__).resolve().parent / "data"
ARQUIVOS = ("ingredientes.json", "receitas.json", "maquinas.json", "perfis.json", "constantes.json", "novidades.json")
NOVIDADES = "novidades.json"


def dir_usuario() -> Path | None:
    v = os.environ.get("CALDA_DADOS")
    return Path(v).expanduser() if v else None


def caminho_leitura(nome: str) -> Path:
    u = dir_usuario()
    if u is not None and (u / nome).exists():
        return u / nome
    return PACOTE / nome


def caminho_gravacao(nome: str) -> Path:
    u = dir_usuario()
    return (u / nome) if u is not None else (PACOTE / nome)


def ler(nome: str) -> Any:
    with open(caminho_leitura(nome), encoding="utf-8") as f:
        return json.load(f)


def gravar(nome: str, dados: Any) -> Path:
    p = caminho_gravacao(nome)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, p)
    carregar_constantes.cache_clear()
    return p


@lru_cache(maxsize=1)
def _constantes_cache(caminho: str, mtime: float) -> dict:
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)


def carregar_constantes() -> dict:
    p = caminho_leitura("constantes.json")
    return _constantes_cache(str(p), p.stat().st_mtime)


carregar_constantes.cache_clear = _constantes_cache.cache_clear  # type: ignore[attr-defined]


def ingredientes() -> list[dict]:
    return ler("ingredientes.json")


def mapa_ingredientes() -> dict[str, dict]:
    return {i["id"]: i for i in ingredientes()}


def receitas() -> list[dict]:
    return ler("receitas.json")


def maquinas() -> list[dict]:
    return ler("maquinas.json")


def perfis() -> list[dict]:
    return ler("perfis.json")


def achar(lista: list[dict], chave: str | None, tipo: str) -> dict:
    """Acha por id exato, ou por trecho único do id/nome (sem diferenciar maiúsculas)."""
    if chave is None:
        raise KeyError(f"{tipo} não informado")
    for x in lista:
        if x["id"] == chave:
            return x
    c = chave.lower()
    cand = [x for x in lista if c in x["id"].lower() or c in str(x.get("nome", "")).lower()
            or c in str(x.get("nome_curto", "")).lower()]
    if len(cand) == 1:
        return cand[0]
    if not cand:
        raise KeyError(f"nada encontrado para {tipo} '{chave}'")
    raise KeyError(f"busca ambígua para {tipo} '{chave}': {', '.join(x['id'] for x in cand)}")


# --------------------------------------------------------------------------
# Novidades (banco complementar)
# --------------------------------------------------------------------------
# Ingredientes, perfis, receitas e constantes adicionados depois do app
# original ficam em ``novidades.json``, separados dos arquivos do app. Assim:
# * as listas originais (``ingredientes()``, ``perfis()``, ``receitas()``)
#   continuam idênticas, e quem já tem cópias próprias em ``CALDA_DADOS``
#   não perde nada nem é sobrescrito;
# * campos novos de ingredientes existentes (``complementos_ingredientes``)
#   só preenchem o que estiver AUSENTE no ingrediente.
def novidades() -> dict:
    try:
        return ler(NOVIDADES)
    except FileNotFoundError:
        return {}


def constantes_novidades() -> dict:
    return novidades().get("constantes", {})


def ingredientes_extra() -> list[dict]:
    return list(novidades().get("ingredientes", []))


def _complementar(ings: list[dict], compl: dict) -> list[dict]:
    out = []
    for i in ings:
        c = compl.get(i["id"])
        if c:
            i = dict(i)
            for k, v in c.items():
                if k not in i:
                    i[k] = v
        out.append(i)
    return out


def ingredientes_todos() -> list[dict]:
    """Banco original + banco complementar (ids repetidos: vale o original),
    com os campos complementares preenchidos onde faltarem."""
    nov = novidades()
    base = ingredientes()
    ids = {i["id"] for i in base}
    todos = base + [i for i in nov.get("ingredientes", []) if i["id"] not in ids]
    return _complementar(todos, nov.get("complementos_ingredientes", {}))


def mapa_ingredientes_todos() -> dict[str, dict]:
    return {i["id"]: i for i in ingredientes_todos()}


def perfis_extra() -> list[dict]:
    return list(novidades().get("perfis", []))


def receitas_extra() -> list[dict]:
    return list(novidades().get("receitas", []))


def _juntar(base: list[dict], extra: list[dict]) -> list[dict]:
    ids = {x["id"] for x in base}
    return base + [x for x in extra if x["id"] not in ids]


def perfis_todos() -> list[dict]:
    return _juntar(perfis(), perfis_extra())


def receitas_todos() -> list[dict]:
    return _juntar(receitas(), receitas_extra())


def achar_com_extras(base: list[dict], extra: list[dict], chave: str | None, tipo: str) -> dict:
    """Como ``achar`` na lista original; só procura no complementar quando a
    original não tem NADA para a chave (buscas que já funcionavam continuam
    dando o mesmo resultado, sem novas ambiguidades)."""
    try:
        return achar(base, chave, tipo)
    except KeyError as e:
        if not extra or "nada encontrado" not in str(e.args[0] if e.args else ""):
            raise
    return achar(extra, chave, tipo)
