"""Firma HMAC-SHA256 de BytePlus Vision, servicio cv, región ap-singapore-1."""

from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timezone
from urllib.parse import parse_qsl, quote, urlencode, urlparse


def _cadena_consulta(query: str) -> str:
    pares = parse_qsl(query, keep_blank_values=True)
    pares.sort(key=lambda par: (par[0], par[1]))
    return urlencode(pares, quote_via=lambda valor, *_args: quote(str(valor), safe="-_.~"))


def firmar_byteplus(
    *,
    metodo: str,
    url: str,
    cuerpo: bytes,
    access_key: str,
    secret_key: str,
    ahora: datetime | None = None,
    region: str = "ap-singapore-1",
    servicio: str = "cv",
) -> dict[str, str]:
    momento = ahora or datetime.now(timezone.utc)
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=timezone.utc)
    fecha = momento.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dia = fecha[:8]
    analizada = urlparse(url)
    ruta = analizada.path or "/"
    consulta = _cadena_consulta(analizada.query)
    resumen = hashlib.sha256(cuerpo).hexdigest()
    host = analizada.hostname or ""
    cabeceras = {
        "content-type": "application/json",
        "host": host,
        "x-content-sha256": resumen,
        "x-date": fecha,
    }
    firmadas = ";".join(sorted(cabeceras))
    canonicas = "".join(f"{clave}:{cabeceras[clave]}\n" for clave in sorted(cabeceras))
    solicitud = "\n".join([metodo, ruta, consulta, canonicas, firmadas, resumen])
    alcance = f"{dia}/{region}/{servicio}/request"
    a_firmar = "\n".join(
        [
            "HMAC-SHA256",
            fecha,
            alcance,
            hashlib.sha256(solicitud.encode()).hexdigest(),
        ]
    )
    clave = secret_key.encode()
    for tramo in (dia, region, servicio, "request"):
        clave = hmac.new(clave, tramo.encode(), hashlib.sha256).digest()
    firma = hmac.new(clave, a_firmar.encode(), hashlib.sha256).hexdigest()
    autorizacion = (
        f"HMAC-SHA256 Credential={access_key}/{alcance}, "
        f"SignedHeaders={firmadas}, Signature={firma}"
    )
    return {
        "Content-Type": "application/json",
        "Host": host,
        "X-Content-Sha256": resumen,
        "X-Date": fecha,
        "Authorization": autorizacion,
    }
