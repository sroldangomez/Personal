"""Comandos para el arranque del noticiero."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

from noticias.activos import validar_persona
from noticias.bucle import producir
from noticias.decidir import MENSAJES, leer_rubrica, siguiente_paso
from noticias.kling import ClienteKling, costo_usd as costo_kling
from noticias.piloto import cabe_en_presupuesto, costo_total, tareas
from noticias.precios import PRESUPUESTO_PILOTO_USD
from noticias.rutas import PERSONA_IDS, PERSONAS, RUBRICA, SALIDA


def _persona(nombre: str) -> Path:
    if nombre not in PERSONA_IDS:
        raise SystemExit(f"persona desconocida: {nombre}. Usa tu o colaborador.")
    return PERSONAS / nombre


def cmd_preparar(_args: argparse.Namespace) -> int:
    listo = True
    for nombre in PERSONA_IDS:
        pendientes = validar_persona(_persona(nombre))
        if pendientes:
            listo = False
            print(f"{nombre}:")
            for pendiente in pendientes:
                print(f"  - {pendiente}")
        else:
            print(f"{nombre}: lista")
    if not listo:
        print("Cuando las dos personas estén listas, corre: python -m noticias piloto")
        return 1
    print("Consentimiento, foto y voz listos para las dos personas.")
    return 0


def cmd_piloto(args: argparse.Namespace) -> int:
    trabajos = tareas()
    total = costo_total(trabajos)
    print(f"Piloto: {len(trabajos)} tomas, {total} USD. Tope {PRESUPUESTO_PILOTO_USD} USD.")
    for trabajo in trabajos:
        print(f"  {trabajo.persona} toma {trabajo.toma}: {trabajo.segundos}s, {trabajo.costo} USD")
    if not cabe_en_presupuesto(trabajos):
        print("El piloto pasa el presupuesto. No se envía nada.")
        return 1
    if not args.ejecutar:
        print("Simulación. Para gastar crédito: python -m noticias piloto --ejecutar")
        return 0
    pendientes = []
    for nombre in PERSONA_IDS:
        pendientes.extend(validar_persona(_persona(nombre)))
    if pendientes:
        print("Faltan fotos, voces o consentimientos. Corre python -m noticias preparar")
        return 1
    access_key = os.environ.get("BYTEPLUS_ACCESS_KEY", "")
    secret_key = os.environ.get("BYTEPLUS_SECRET_KEY", "")
    if not access_key or not secret_key:
        print("Faltan BYTEPLUS_ACCESS_KEY y BYTEPLUS_SECRET_KEY.")
        return 1
    from noticias.omnihuman import ClienteOmniHuman

    cliente = ClienteOmniHuman(access_key, secret_key)
    for trabajo in trabajos:
        captura = json.loads((_persona(trabajo.persona) / "captura.json").read_text(encoding="utf-8"))
        imagen = captura.get("foto_url") or ""
        audio = captura.get("audio_piloto_url") or ""
        if not imagen or not audio:
            print(f"{trabajo.persona}: sube la foto y el audio de 15 segundos y pon foto_url y audio_piloto_url.")
            return 1
        destino = SALIDA / "piloto" / trabajo.persona / f"toma-{trabajo.toma}"
        print(f"Enviando {trabajo.persona} toma {trabajo.toma}")
        producir(
            persona=trabajo.persona,
            guion=trabajo.guion,
            foto_url=imagen,
            audio_url=audio,
            destino=destino,
            access_key=access_key,
            secret_key=secret_key,
            duracion_s=trabajo.segundos,
            cliente=cliente,
        )
        print(f"  {destino / 'reel.mp4'}")
    return 0


def cmd_decidir(_args: argparse.Namespace) -> int:
    paso = siguiente_paso(leer_rubrica(RUBRICA))
    print(MENSAJES[paso])
    return 0 if paso != "incompleta" else 1


def cmd_producir(args: argparse.Namespace) -> int:
    paso = siguiente_paso(leer_rubrica(RUBRICA))
    if paso != "automatizar" and not args.forzar:
        print(MENSAJES[paso])
        print("El bucle automático espera la rúbrica en automatizar, o --forzar.")
        return 1
    guion = Path(args.guion).read_text(encoding="utf-8").strip() if args.guion else args.texto
    if not guion:
        print("Pasa --texto o --guion.")
        return 1
    captura = json.loads((_persona(args.persona) / "captura.json").read_text(encoding="utf-8"))
    destino = SALIDA / "produccion" / args.persona
    try:
        resultado = producir(
            persona=args.persona,
            guion=guion,
            foto_url=captura.get("foto_url") or "",
            audio_url=args.audio_url,
            destino=destino,
            access_key=os.environ.get("BYTEPLUS_ACCESS_KEY", ""),
            secret_key=os.environ.get("BYTEPLUS_SECRET_KEY", ""),
            eleven_key=os.environ.get("ELEVENLABS_API_KEY"),
            voice_id=(os.environ.get(f"ELEVENLABS_VOICE_{args.persona.upper()}") or captura.get("voice_id")),
            audio_local=destino / "voz.mp3",
            duracion_s=args.segundos,
        )
    except RuntimeError as error:
        print(error)
        return 1
    print(resultado.video)
    print(resultado.subtitulos)
    return 0


def cmd_gesto(args: argparse.Namespace) -> int:
    paso = siguiente_paso(leer_rubrica(RUBRICA))
    if paso != "kling" and not args.forzar:
        print(MENSAJES[paso])
        print("La prueba de gesto espera la rúbrica en kling, o --forzar.")
        return 1
    if not args.ejecutar:
        print(
            "Prueba Kling Motion Control 2.6 a 1080p: "
            f"un video de gesto de 10 s costaría {costo_kling(10)} USD. "
            "Para enviarla: python -m noticias gesto --persona "
            f"{args.persona} --ejecutar"
        )
        return 0
    api_key = os.environ.get("KLING_API_KEY", "")
    if not api_key:
        print("Falta KLING_API_KEY.")
        return 1
    captura = json.loads((_persona(args.persona) / "captura.json").read_text(encoding="utf-8"))
    imagen = captura.get("foto_url") or ""
    video = captura.get("gesto_url") or ""
    if not imagen or not video:
        print("Pon foto_url y gesto_url (video HTTPS de 3 a 30 segundos) en captura.json.")
        return 1
    cliente = ClienteKling(api_key)
    tarea = cliente.enviar(imagen, video)
    url = cliente.esperar(tarea)
    destino = SALIDA / "gesto" / args.persona
    destino.mkdir(parents=True, exist_ok=True)
    archivo = destino / "gesto.mp4"
    with urllib.request.urlopen(url) as respuesta:
        archivo.write_bytes(respuesta.read())
    print(archivo)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="noticias")
    sub = parser.add_subparsers(dest="comando", required=True)
    sub.add_parser("preparar")
    piloto = sub.add_parser("piloto")
    piloto.add_argument("--ejecutar", action="store_true")
    sub.add_parser("decidir")
    producir_cmd = sub.add_parser("producir")
    producir_cmd.add_argument("--persona", required=True, choices=PERSONA_IDS)
    producir_cmd.add_argument("--texto", default="")
    producir_cmd.add_argument("--guion", default="")
    producir_cmd.add_argument("--audio-url", default=None)
    producir_cmd.add_argument("--segundos", type=float, default=15)
    producir_cmd.add_argument("--forzar", action="store_true")
    gesto = sub.add_parser("gesto")
    gesto.add_argument("--persona", required=True, choices=PERSONA_IDS)
    gesto.add_argument("--ejecutar", action="store_true")
    gesto.add_argument("--forzar", action="store_true")
    args = parser.parse_args(argv)
    comandos = {
        "preparar": cmd_preparar,
        "piloto": cmd_piloto,
        "decidir": cmd_decidir,
        "producir": cmd_producir,
        "gesto": cmd_gesto,
    }
    return comandos[args.comando](args)


if __name__ == "__main__":
    sys.exit(main())
