from __future__ import annotations

import re
from decimal import Decimal


def _marca(segundos: Decimal) -> str:
    total_ms = int((segundos * 1000).to_integral_value())
    horas, resto = divmod(total_ms, 3_600_000)
    minutos, resto = divmod(resto, 60_000)
    segs, milis = divmod(resto, 1000)
    return f"{horas:02d}:{minutos:02d}:{segs:02d},{milis:03d}"


def a_srt(texto: str, duracion_s: float) -> str:
    partes = [parte.strip() for parte in re.split(r"(?<=[.!?])\s+", texto.strip()) if parte.strip()]
    if not partes:
        return ""
    duracion = Decimal(str(duracion_s))
    tramo = duracion / len(partes)
    lineas: list[str] = []
    for indice, parte in enumerate(partes, start=1):
        inicio = tramo * (indice - 1)
        fin = duracion if indice == len(partes) else tramo * indice
        lineas.append(f"{indice}\n{_marca(inicio)} --> {_marca(fin)}\n{parte}\n")
    return "\n".join(lineas)
