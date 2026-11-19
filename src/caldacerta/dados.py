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
ARQUIVOS = ("ingredientes.json", "receitas.json", "maquinas.json", "perfis.json", "constantes.json")


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
