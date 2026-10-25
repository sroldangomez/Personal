"""Qué hacer después de mirar las seis tomas del piloto."""

from __future__ import annotations

import json
from pathlib import Path

CAMPOS = (
    "cara_se_sostiene",
    "manos_rotas",
    "gesto_real_requerido",
    "resolucion_baja",
    "formato_ancla_sentada",
)


def leer_rubrica(ruta: Path) -> dict:
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    faltan = [campo for campo in CAMPOS if campo not in datos]
    if faltan:
        raise ValueError("la rúbrica no trae: " + ", ".join(faltan))
    return datos


def siguiente_paso(rubrica: dict) -> str:
    if any(rubrica[campo] is None for campo in CAMPOS):
        return "incompleta"
    if rubrica["formato_ancla_sentada"]:
        return "heygen"
    if rubrica["gesto_real_requerido"] or rubrica["manos_rotas"]:
        return "kling"
    if not rubrica["cara_se_sostiene"]:
        return "repetir_captura"
    if rubrica["resolucion_baja"]:
        return "omnihuman_1_5"
    return "automatizar"


MENSAJES = {
    "incompleta": "Mira las seis tomas y completa revision/rubrica.json. Todavía hay campos en null.",
    "heygen": "El formato quedó en ancla sentada. Pasa a HeyGen Business. No es un doble de cuerpo entero.",
    "kling": "Haz una prueba aparte con Kling Motion Control 2.6: la misma foto más un video del gesto, de 3 a 30 segundos.",
    "repetir_captura": "La cara no se sostiene. Repite la foto de cuerpo entero antes de gastar más crédito.",
    "omnihuman_1_5": "La cara aguanta y 720p se ve blando. Prueba OmniHuman 1.5 a 0.12 USD por segundo, clips de menos de 60 segundos.",
    "automatizar": "La cara se sostiene y las manos no se rompen. Automatiza el bucle guion, voz y foto con OmniHuman 2.0.",
}
