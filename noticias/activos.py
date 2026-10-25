"""Reglas de la foto de cuerpo entero y de la muestra de voz."""

from __future__ import annotations

import json
import struct
import wave
import zlib
from dataclasses import dataclass
from pathlib import Path

CAMPOS_CAPTURA = (
    "pies_a_cabeza",
    "de_frente",
    "luz_pareja",
    "fondo_simple",
    "manos_visibles",
    "boca_cerrada",
)
FOTO_MIN_PX = 300
FOTO_MAX_PX = 6000
FOTO_MAX_BYTES = 30 * 1024 * 1024
RELACION_MIN = 0.4
RELACION_MAX = 2.5
RELACION_VERTICAL = 9 / 16
VOZ_MIN_S = 30
VOZ_MAX_S = 60
AUDIO_API_MIN_S = 4
AUDIO_API_MAX_S = 300


class ActivoInvalido(ValueError):
    pass


@dataclass(frozen=True)
class Foto:
    ruta: Path
    ancho: int
    alto: int

    @property
    def relacion(self) -> float:
        return self.ancho / self.alto

    @property
    def es_vertical_9_16(self) -> bool:
        return abs(self.relacion - RELACION_VERTICAL) <= 0.04


def _png(data: bytes) -> tuple[int, int]:
    firma = b"\x89PNG\r\n\x1a\n"
    if not data.startswith(firma) or data[12:16] != b"IHDR":
        raise ActivoInvalido("el PNG no tiene cabecera IHDR")
    ancho, alto = struct.unpack(">II", data[16:24])
    return ancho, alto


def _jpeg(data: bytes) -> tuple[int, int]:
    if data[:2] != b"\xff\xd8":
        raise ActivoInvalido("el archivo no es JPEG")
    indice = 2
    marcadores = {
        0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
        0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF,
    }
    while indice + 3 < len(data):
        if data[indice] != 0xFF:
            raise ActivoInvalido("el JPEG está truncado")
        while indice < len(data) and data[indice] == 0xFF:
            indice += 1
        if indice >= len(data):
            break
        marcador = data[indice]
        indice += 1
        if marcador in (0xD8, 0xD9):
            continue
        if marcador == 0xDA or indice + 1 >= len(data):
            break
        largo = struct.unpack(">H", data[indice : indice + 2])[0]
        if marcador in marcadores and indice + 7 <= len(data):
            alto, ancho = struct.unpack(">HH", data[indice + 3 : indice + 7])
            return ancho, alto
        indice += largo
    raise ActivoInvalido("no se pudo leer el tamaño del JPEG")


def medir_foto(ruta: Path) -> Foto:
    if not ruta.is_file():
        raise ActivoInvalido(f"falta la foto: {ruta.name}")
    data = ruta.read_bytes()
    if len(data) > FOTO_MAX_BYTES:
        raise ActivoInvalido("la foto supera 30 MB")
    if ruta.suffix.lower() == ".png":
        ancho, alto = _png(data)
    elif ruta.suffix.lower() in {".jpg", ".jpeg"}:
        ancho, alto = _jpeg(data)
    else:
        raise ActivoInvalido("la foto debe ser PNG o JPEG")
    if not (FOTO_MIN_PX <= ancho <= FOTO_MAX_PX and FOTO_MIN_PX <= alto <= FOTO_MAX_PX):
        raise ActivoInvalido("cada lado de la foto debe medir entre 300 y 6000 px")
    relacion = ancho / alto
    if not (RELACION_MIN <= relacion <= RELACION_MAX):
        raise ActivoInvalido("la relación ancho/alto debe estar entre 0.4 y 2.5")
    return Foto(ruta, ancho, alto)


def duracion_wav(ruta: Path) -> float:
    if not ruta.is_file():
        raise ActivoInvalido(f"falta el audio: {ruta.name}")
    if ruta.suffix.lower() != ".wav":
        raise ActivoInvalido("la muestra de voz del piloto local debe ser WAV")
    with wave.open(str(ruta), "rb") as audio:
        if audio.getframerate() == 0:
            raise ActivoInvalido("el WAV no tiene frecuencia de muestreo")
        return audio.getnframes() / audio.getframerate()


def validar_muestra_de_voz(ruta: Path) -> float:
    segundos = duracion_wav(ruta)
    if not (VOZ_MIN_S <= segundos <= VOZ_MAX_S):
        raise ActivoInvalido("la muestra de voz debe durar entre 30 y 60 segundos")
    return segundos


def validar_audio_de_reel(ruta: Path) -> float:
    segundos = duracion_wav(ruta)
    if not (AUDIO_API_MIN_S <= segundos <= AUDIO_API_MAX_S):
        raise ActivoInvalido("OmniHuman 2.0 exige un audio de 4 a 300 segundos")
    return segundos


def leer_captura(ruta: Path) -> dict:
    if not ruta.is_file():
        raise ActivoInvalido(f"falta {ruta.name}")
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    faltan = [campo for campo in ("confirmado", "foto", "voz", *CAMPOS_CAPTURA) if campo not in datos]
    if faltan:
        raise ActivoInvalido("captura.json no trae: " + ", ".join(faltan))
    return datos


def validar_persona(carpeta: Path) -> list[str]:
    """Devuelve los pendientes. Lista vacía significa que la persona está lista."""
    pendientes: list[str] = []
    captura_ruta = carpeta / "captura.json"
    try:
        captura = leer_captura(captura_ruta)
    except (ActivoInvalido, json.JSONDecodeError) as error:
        return [str(error)]
    if not captura.get("confirmado"):
        pendientes.append("marca confirmado=true en captura.json después de revisar la foto")
    for campo in CAMPOS_CAPTURA:
        if captura.get(campo) is not True:
            pendientes.append(f"falta confirmar {campo}")
    foto = carpeta / str(captura.get("foto") or "foto.png")
    voz = carpeta / str(captura.get("voz") or "voz.wav")
    try:
        medida = medir_foto(foto)
        if not medida.es_vertical_9_16:
            pendientes.append("la foto no está en 9:16; OmniHuman sigue el encuadre de la imagen")
    except ActivoInvalido as error:
        pendientes.append(str(error))
    try:
        validar_muestra_de_voz(voz)
    except ActivoInvalido as error:
        pendientes.append(str(error))
    consentimiento = carpeta / "consentimiento.md"
    if not consentimiento.is_file():
        pendientes.append("falta consentimiento.md firmado")
    else:
        texto = consentimiento.read_text(encoding="utf-8")
        for token in ("[NOMBRE]", "[DOCUMENTO]", "[FECHA]", "[FIRMA]", "[CUENTA_DE_INSTAGRAM]"):
            if token in texto:
                pendientes.append(f"el consentimiento todavía tiene {token}")
    return pendientes


def png_solido(ancho: int, alto: int, color: tuple[int, int, int] = (20, 20, 20)) -> bytes:
    """PNG RGB pequeño, solo para pruebas."""

    def trozo(etiqueta: bytes, datos: bytes) -> bytes:
        crc = zlib.crc32(etiqueta + datos) & 0xFFFFFFFF
        return struct.pack(">I", len(datos)) + etiqueta + datos + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", ancho, alto, 8, 2, 0, 0, 0)
    fila = b"\x00" + bytes(color) * ancho
    crudo = fila * alto
    return b"\x89PNG\r\n\x1a\n" + trozo(b"IHDR", ihdr) + trozo(b"IDAT", zlib.compress(crudo)) + trozo(b"IEND", b"")


def wav_silencio(segundos: float, frecuencia: int = 8000) -> bytes:
    import io

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(frecuencia)
        audio.writeframes(b"\x00\x00" * int(frecuencia * segundos))
    return buffer.getvalue()
