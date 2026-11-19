"""Semântica numérica do JavaScript que o app original usa.

O motor original roda em JS; para reproduzir os números bit a bit precisamos
das mesmas regras de arredondamento (``Math.round`` e ``Number.prototype.toFixed``)
e da coerção ``Number(x) || 0``.
"""

from __future__ import annotations

import math
from decimal import ROUND_HALF_UP, Decimal


def js_round(x: float) -> float:
    """``Math.round``: arredonda meio para cima (em direção a +inf)."""
    if not math.isfinite(x):
        return x
    piso = math.floor(x)
    r = piso + 1 if x - piso >= 0.5 else piso
    if r == 0 and (x < 0 or math.copysign(1.0, x) < 0):
        return -0.0
    return float(r)


def numero(x) -> float:
    """``Number(x) || 0``: converte para float; NaN, vazio e inválidos viram 0."""
    if x is None:
        return 0.0
    if isinstance(x, bool):
        return 1.0 if x else 0.0
    if isinstance(x, (int, float)):
        v = float(x)
    elif isinstance(x, str):
        s = x.strip()
        if s == "":
            return 0.0
        try:
            v = float(s)
        except ValueError:
            return 0.0
    else:
        return 0.0
    if math.isnan(v):
        return 0.0
    return v + 0.0 if v == 0 else v


def to_fixed(x: float, casas: int = 0) -> str:
    """``Number.prototype.toFixed``: usa o valor decimal exato do double e
    arredonda meio para cima (o ``format`` do Python arredonda meio para par)."""
    if math.isnan(x):
        return "NaN"
    if math.isinf(x):
        return "Infinity" if x > 0 else "-Infinity"
    if abs(x) >= 1e21:
        return repr(x)
    d = Decimal(x)
    q = Decimal(1).scaleb(-casas)
    s = format(d.quantize(q, rounding=ROUND_HALF_UP), "f")
    if x == 0 or s.lstrip("-").strip("0.") == "":
        # JS: (-0).toFixed(1) == "0.0", mas (-0.04).toFixed(1) == "-0.0"
        if x == 0 or x > 0:
            s = s.lstrip("-")
    return s


def br(x: float, casas: int = 1) -> str:
    """Formato da ficha do app: ``toFixed`` com vírgula decimal."""
    return to_fixed(x, casas).replace(".", ",", 1)
