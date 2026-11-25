#!/usr/bin/env python3
"""Empacota os arquivos JSON de ``src/caldacerta/data/`` em ``web/data/bundle.json``.

Mantém ``src/caldacerta/data/`` como fonte única da verdade: tanto o checkout
local quanto o workflow do GitHub Pages executam este script para manter a
interface web sincronizada com a biblioteca e a CLI.
"""

from __future__ import annotations

import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ORIGEM = RAIZ / "src" / "caldacerta" / "data"
DESTINO = RAIZ / "web" / "data" / "bundle.json"


def ler_json(nome: str):
    return json.loads((ORIGEM / nome).read_text(encoding="utf-8"))


def gerar_bundle() -> dict:
    return {
        "ingredientes": ler_json("ingredientes.json"),
        "receitas": ler_json("receitas.json"),
        "maquinas": ler_json("maquinas.json"),
        "perfis": ler_json("perfis.json"),
        "constantes": ler_json("constantes.json"),
        "novidades": ler_json("novidades.json"),
    }


def main() -> None:
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    bundle = gerar_bundle()
    DESTINO.write_text(
        json.dumps(bundle, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    print(f"Gerado {DESTINO.relative_to(RAIZ)} ({DESTINO.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
