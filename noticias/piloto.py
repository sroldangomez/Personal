"""Seis tomas de 15 segundos: tres por persona, el mismo guion y la misma foto."""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from noticias.precios import (
    PRESUPUESTO_PILOTO_USD,
    SEGUNDOS_POR_TOMA,
    TOMAS_POR_PERSONA,
)
from noticias.omnihuman import costo_usd
from noticias.rutas import GUION_PILOTO, PERSONA_IDS


@dataclass(frozen=True)
class TareaPiloto:
    persona: str
    toma: int
    guion: str
    segundos: int

    @property
    def costo(self) -> Decimal:
        return costo_usd(self.segundos)


def cargar_guion(ruta: Path = GUION_PILOTO) -> dict:
    return json.loads(ruta.read_text(encoding="utf-8"))


def tareas(ruta: Path = GUION_PILOTO) -> list[TareaPiloto]:
    datos = cargar_guion(ruta)
    guion = str(datos["guion"]).strip()
    segundos = int(datos.get("segundos_objetivo", SEGUNDOS_POR_TOMA))
    tomas = int(datos.get("tomas", TOMAS_POR_PERSONA))
    personas = list(datos.get("personas") or PERSONA_IDS)
    return [
        TareaPiloto(persona=persona, toma=toma, guion=guion, segundos=segundos)
        for persona in personas
        for toma in range(1, tomas + 1)
    ]


def costo_total(lista: list[TareaPiloto] | None = None) -> Decimal:
    trabajos = lista if lista is not None else tareas()
    return sum((trabajo.costo for trabajo in trabajos), Decimal("0.00"))


def cabe_en_presupuesto(lista: list[TareaPiloto] | None = None, tope: Decimal = PRESUPUESTO_PILOTO_USD) -> bool:
    return costo_total(lista) <= tope
