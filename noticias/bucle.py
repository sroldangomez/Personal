"""Bucle de producción: guion, voz clonada, foto fija, OmniHuman, subtítulos."""

from __future__ import annotations

import urllib.request
from dataclasses import dataclass
from pathlib import Path

from noticias.omnihuman import PROMPT_NOTICIERO, ClienteOmniHuman
from noticias.subtitulos import a_srt
from noticias.voces import sintetizar


@dataclass(frozen=True)
class Resultado:
    video: Path
    subtitulos: Path
    task_id: str


def producir(
    *,
    persona: str,
    guion: str,
    foto_url: str,
    audio_url: str | None,
    destino: Path,
    access_key: str,
    secret_key: str,
    eleven_key: str | None = None,
    voice_id: str | None = None,
    audio_local: Path | None = None,
    duracion_s: float = 15,
    cliente: ClienteOmniHuman | None = None,
    descargar=None,
) -> Resultado:
    del persona
    destino.mkdir(parents=True, exist_ok=True)
    if audio_url is None:
        if not (eleven_key and voice_id and audio_local is not None):
            raise RuntimeError("hace falta audio_url público, o ElevenLabs más un archivo local ya subido")
        sintetizar(api_key=eleven_key, voice_id=voice_id, texto=guion, destino=audio_local)
        raise RuntimeError(
            f"el audio quedó en {audio_local}; súbelo a una URL HTTPS y vuelve a llamar con audio_url"
        )
    motor = cliente or ClienteOmniHuman(access_key, secret_key)
    task_id = motor.enviar(foto_url, audio_url, PROMPT_NOTICIERO)
    video_url = motor.esperar(task_id)
    video = destino / "reel.mp4"
    subtitulos = destino / "reel.srt"
    bajar = descargar or urllib.request.urlopen
    with bajar(video_url) as respuesta:
        video.write_bytes(respuesta.read())
    subtitulos.write_text(a_srt(guion, duracion_s), encoding="utf-8")
    return Resultado(video=video, subtitulos=subtitulos, task_id=task_id)
