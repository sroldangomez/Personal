"""Kling Motion Control 2.6, solo si un gesto real no sale en OmniHuman."""

from __future__ import annotations

import json
import time
import urllib.request
from collections.abc import Callable
from decimal import Decimal

from noticias.precios import KLING_MOTION_1080_USD_POR_SEGUNDO

Abridor = Callable[..., object]

HOST = "https://api-singapore.klingai.com"


class KlingError(RuntimeError):
    pass


def costo_usd(segundos: Decimal | int | float) -> Decimal:
    return (Decimal(segundos) * KLING_MOTION_1080_USD_POR_SEGUNDO).quantize(Decimal("0.01"))


def cuerpo_gesto(imagen_url: str, video_url: str) -> dict:
    return {
        "contents": [
            {"type": "image", "url": imagen_url},
            {"type": "video", "url": video_url},
        ],
        "settings": {
            "character_orientation": "video",
            "audio": "off",
            "resolution": "1080p",
        },
        "options": {"watermark_info": {"enabled": False}},
    }


class ClienteKling:
    def __init__(self, api_key: str, abridor: Abridor | None = None, espera: Callable[[float], None] = time.sleep) -> None:
        self.api_key = api_key
        self.abridor = abridor or urllib.request.urlopen
        self.espera = espera

    def _llamar(self, metodo: str, url: str, cuerpo: bytes | None = None) -> dict:
        peticion = urllib.request.Request(
            url,
            data=cuerpo,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method=metodo,
        )
        with self.abridor(peticion) as respuesta:
            datos = json.loads(respuesta.read().decode())
        if datos.get("code") not in (0, None):
            raise KlingError(datos.get("message") or f"código {datos.get('code')}")
        return datos

    def enviar(self, imagen_url: str, video_url: str) -> str:
        datos = self._llamar(
            "POST",
            f"{HOST}/motion-control/kling-2.6",
            json.dumps(cuerpo_gesto(imagen_url, video_url)).encode(),
        )
        tarea = (datos.get("data") or {}).get("id")
        if not tarea:
            raise KlingError("Kling no devolvió el id de la tarea")
        return str(tarea)

    def esperar(self, task_id: str, intentos: int = 60, pausa: float = 5) -> str:
        for _ in range(intentos):
            datos = self._llamar("GET", f"{HOST}/tasks?task_ids={task_id}")
            filas = datos.get("data") or []
            if not filas:
                self.espera(pausa)
                continue
            fila = filas[0]
            estado = str(fila.get("status") or "").lower()
            if estado == "succeeded":
                for salida in fila.get("outputs") or []:
                    if salida.get("type") == "video" and salida.get("url"):
                        return str(salida["url"])
                raise KlingError(f"la tarea {task_id} terminó sin video")
            if estado == "failed":
                raise KlingError(fila.get("message") or f"la tarea {task_id} falló")
            self.espera(pausa)
        raise KlingError(f"la tarea {task_id} no terminó a tiempo")
