"""Voz clonada con ElevenLabs. OmniHuman recibe el audio, no el texto."""

from __future__ import annotations

import json
import mimetypes
import urllib.request
import uuid
from collections.abc import Callable
from pathlib import Path

Abridor = Callable[..., object]


class VozError(RuntimeError):
    pass


def sintetizar(
    *,
    api_key: str,
    voice_id: str,
    texto: str,
    destino: Path,
    abridor: Abridor | None = None,
    modelo: str = "eleven_multilingual_v2",
) -> Path:
    abrir = abridor or urllib.request.urlopen
    cuerpo = json.dumps({"text": texto, "model_id": modelo}).encode()
    peticion = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
        data=cuerpo,
        headers={
            "xi-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        },
        method="POST",
    )
    with abrir(peticion) as respuesta:
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(respuesta.read())
    return destino


def clonar_muestra(
    *,
    api_key: str,
    nombre: str,
    muestra: Path,
    abridor: Abridor | None = None,
) -> str:
    abrir = abridor or urllib.request.urlopen
    limite = uuid.uuid4().hex
    tipo = mimetypes.guess_type(muestra.name)[0] or "audio/wav"
    archivo = muestra.read_bytes()
    prefijo = (
        f"--{limite}\r\n"
        f'Content-Disposition: form-data; name="name"\r\n\r\n{nombre}\r\n'
        f"--{limite}\r\n"
        f'Content-Disposition: form-data; name="files"; filename="{muestra.name}"\r\n'
        f"Content-Type: {tipo}\r\n\r\n"
    ).encode()
    cuerpo = prefijo + archivo + f"\r\n--{limite}--\r\n".encode()
    peticion = urllib.request.Request(
        "https://api.elevenlabs.io/v1/voices/add",
        data=cuerpo,
        headers={
            "xi-api-key": api_key,
            "Content-Type": f"multipart/form-data; boundary={limite}",
        },
        method="POST",
    )
    with abrir(peticion) as respuesta:
        datos = json.loads(respuesta.read().decode())
    voz = datos.get("voice_id")
    if not voz:
        raise VozError("ElevenLabs no devolvió voice_id")
    return str(voz)
