"""Cliente de OmniHuman 2.0 en BytePlus Vision."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import datetime
from decimal import Decimal

from noticias.firma import firmar_byteplus
from noticias.precios import OMNIHUMAN_2_USD_POR_SEGUNDO

HOST = "https://cv.byteplusapi.com/"
VERSION = "2024-06-06"
REQ_KEY = "realman_avatar_picture_omni20_cv"
PROMPT_NOTICIERO = (
    "La persona está de cuerpo entero, de frente a la cámara, con gestos naturales "
    "de presentador de noticias, manos visibles y pies en el suelo. La cámara no se mueve."
)

Abridor = Callable[[urllib.request.Request], object]


class OmniHumanError(RuntimeError):
    pass


def costo_usd(segundos: Decimal | int | float) -> Decimal:
    return (Decimal(segundos) * OMNIHUMAN_2_USD_POR_SEGUNDO).quantize(Decimal("0.01"))


def cuerpo_tarea(imagen_url: str, audio_url: str, prompt: str = PROMPT_NOTICIERO) -> dict:
    return {
        "audio_url": audio_url,
        "enable_watermark": False,
        "image_urls": [imagen_url],
        "prompt": prompt,
        "req_key": REQ_KEY,
    }


class ClienteOmniHuman:
    def __init__(
        self,
        access_key: str,
        secret_key: str,
        abridor: Abridor | None = None,
        ahora: datetime | None = None,
        espera: Callable[[float], None] = time.sleep,
    ) -> None:
        self.access_key = access_key
        self.secret_key = secret_key
        self.abridor = abridor or urllib.request.urlopen
        self.ahora = ahora
        self.espera = espera

    def _post(self, action: str, payload: dict) -> dict:
        cuerpo = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
        url = f"{HOST}?Action={action}&Version={VERSION}"
        cabeceras = firmar_byteplus(
            metodo="POST",
            url=url,
            cuerpo=cuerpo,
            access_key=self.access_key,
            secret_key=self.secret_key,
            ahora=self.ahora,
        )
        peticion = urllib.request.Request(url, data=cuerpo, headers=cabeceras, method="POST")
        try:
            with self.abridor(peticion) as respuesta:
                crudo = respuesta.read()
        except urllib.error.HTTPError as error:
            detalle = error.read().decode("utf-8", errors="replace")
            raise OmniHumanError(f"BytePlus respondió {error.code}: {detalle}") from error
        datos = json.loads(crudo.decode())
        if datos.get("code") != 10000:
            raise OmniHumanError(datos.get("message") or f"código {datos.get('code')}")
        return datos

    def enviar(self, imagen_url: str, audio_url: str, prompt: str = PROMPT_NOTICIERO) -> str:
        datos = self._post("CVSync2AsyncSubmitTask", cuerpo_tarea(imagen_url, audio_url, prompt))
        tarea = (datos.get("data") or {}).get("task_id") or datos.get("task_id")
        if not tarea:
            raise OmniHumanError("la respuesta no trajo task_id")
        return str(tarea)

    def consultar(self, task_id: str) -> dict:
        return self._post(
            "CVSync2AsyncGetResult",
            {"req_key": REQ_KEY, "task_id": task_id},
        )

    def esperar(self, task_id: str, intentos: int = 60, pausa: float = 5) -> str:
        for _ in range(intentos):
            datos = self.consultar(task_id)
            estado = str((datos.get("data") or {}).get("status") or "").lower()
            video = (datos.get("data") or {}).get("video_url") or ""
            if estado == "done" and video:
                return str(video)
            if estado == "done":
                raise OmniHumanError(f"la tarea {task_id} terminó sin video_url")
            if estado in {"not_found", "expired", "canceled", "cancelled", "failed"}:
                raise OmniHumanError(f"la tarea {task_id} quedó en {estado}")
            self.espera(pausa)
        raise OmniHumanError(f"la tarea {task_id} no terminó a tiempo")
