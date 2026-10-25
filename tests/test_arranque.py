import contextlib
import io
import json
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from noticias.activos import (
    ActivoInvalido,
    medir_foto,
    png_solido,
    validar_audio_de_reel,
    validar_muestra_de_voz,
    validar_persona,
    wav_silencio,
)
from noticias.bucle import producir
from noticias.decidir import siguiente_paso
from noticias.firma import firmar_byteplus
from noticias.kling import cuerpo_gesto
from noticias.omnihuman import ClienteOmniHuman, costo_usd, cuerpo_tarea
from noticias.piloto import cabe_en_presupuesto, costo_total, tareas
from noticias.precios import PRESUPUESTO_PILOTO_USD
from noticias.rutas import PERSONAS, RUBRICA
from noticias.subtitulos import a_srt
from noticias.__main__ import main


class Respuesta:
    def __init__(self, crudo: bytes):
        self._crudo = crudo

    def read(self) -> bytes:
        return self._crudo

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class Pruebas(unittest.TestCase):
    def test_el_piloto_son_seis_tomas_dentro_de_veinte_dolares(self):
        trabajos = tareas()
        self.assertEqual(len(trabajos), 6)
        self.assertEqual({trabajo.persona for trabajo in trabajos}, {"tu", "colaborador"})
        self.assertEqual(costo_total(trabajos), Decimal("6.30"))
        self.assertTrue(cabe_en_presupuesto(trabajos, PRESUPUESTO_PILOTO_USD))
        self.assertEqual(costo_usd(30), Decimal("2.10"))

    def test_la_foto_vertical_pasa_y_la_chica_no(self):
        grande = Path("/tmp/foto-ok.png")
        chica = Path("/tmp/foto-chica.png")
        grande.write_bytes(png_solido(320, 568))
        chica.write_bytes(png_solido(100, 180))
        foto = medir_foto(grande)
        self.assertTrue(foto.es_vertical_9_16)
        with self.assertRaises(ActivoInvalido):
            medir_foto(chica)

    def test_la_voz_de_muestra_dura_entre_30_y_60(self):
        buena = Path("/tmp/voz-ok.wav")
        corta = Path("/tmp/voz-corta.wav")
        buena.write_bytes(wav_silencio(45))
        corta.write_bytes(wav_silencio(15))
        self.assertAlmostEqual(validar_muestra_de_voz(buena), 45, places=2)
        with self.assertRaises(ActivoInvalido):
            validar_muestra_de_voz(corta)
        self.assertAlmostEqual(validar_audio_de_reel(corta), 15, places=2)

    def test_persona_lista_con_consentimiento_foto_y_voz(self):
        carpeta = Path("/tmp/persona-lista")
        carpeta.mkdir(exist_ok=True)
        (carpeta / "foto.png").write_bytes(png_solido(320, 568))
        (carpeta / "voz.wav").write_bytes(wav_silencio(45))
        (carpeta / "consentimiento.md").write_text("Firmado por Ana Pérez, documento 123, cuenta @noticias, fecha 25 de octubre de 2026, firma Ana.\n", encoding="utf-8")
        (carpeta / "captura.json").write_text(
            json.dumps(
                {
                    "confirmado": True,
                    "pies_a_cabeza": True,
                    "de_frente": True,
                    "luz_pareja": True,
                    "fondo_simple": True,
                    "manos_visibles": True,
                    "boca_cerrada": True,
                    "foto": "foto.png",
                    "voz": "voz.wav",
                }
            ),
            encoding="utf-8",
        )
        self.assertEqual(validar_persona(carpeta), [])

    def test_sin_firma_ni_foto_la_persona_no_esta_lista(self):
        pendientes = validar_persona(PERSONAS / "tu")
        self.assertTrue(any("consentimiento" in item or "[NOMBRE]" in item for item in pendientes))
        self.assertTrue(any("foto" in item for item in pendientes))

    def test_la_firma_es_estable(self):
        ahora = datetime(2026, 10, 25, 15, 0, 0, tzinfo=timezone.utc)
        cuerpo = b'{"req_key":"realman_avatar_picture_omni20_cv"}'
        url = "https://cv.byteplusapi.com/?Action=CVSync2AsyncSubmitTask&Version=2024-06-06"
        una = firmar_byteplus(
            metodo="POST", url=url, cuerpo=cuerpo, access_key="ak", secret_key="sk", ahora=ahora
        )
        otra = firmar_byteplus(
            metodo="POST", url=url, cuerpo=cuerpo, access_key="ak", secret_key="sk", ahora=ahora
        )
        self.assertEqual(una, otra)
        self.assertTrue(una["Authorization"].startswith("HMAC-SHA256 Credential=ak/20261025/ap-singapore-1/cv/request"))
        self.assertIn("SignedHeaders=content-type;host;x-content-sha256;x-date", una["Authorization"])

    def test_omnihuman_envia_y_espera_el_video(self):
        vistos = []

        def abridor(peticion):
            vistos.append(json.loads(peticion.data.decode()))
            if len(vistos) == 1:
                return Respuesta(b'{"code":10000,"data":{"task_id":"t-1"}}')
            return Respuesta(b'{"code":10000,"data":{"status":"done","video_url":"https://cdn.ejemplo/reel.mp4"}}')

        cliente = ClienteOmniHuman("ak", "sk", abridor=abridor, espera=lambda _segundos: None)
        self.assertEqual(cliente.enviar("https://cdn.ejemplo/foto.png", "https://cdn.ejemplo/voz.wav"), "t-1")
        self.assertEqual(cliente.esperar("t-1"), "https://cdn.ejemplo/reel.mp4")
        self.assertEqual(vistos[0]["req_key"], "realman_avatar_picture_omni20_cv")
        self.assertFalse(vistos[0]["enable_watermark"])
        self.assertEqual(cuerpo_tarea("https://a", "https://b")["image_urls"], ["https://a"])

    def test_el_bucle_guarda_el_mp4_y_los_subtitulos(self):
        class Cliente:
            def enviar(self, imagen, audio, prompt):
                self.imagen = imagen
                return "tarea"

            def esperar(self, task_id):
                return "https://cdn.ejemplo/reel.mp4"

        destino = Path("/tmp/reel-prueba")
        resultado = producir(
            persona="tu",
            guion="Buenas noches. El dólar cerró estable.",
            foto_url="https://cdn.ejemplo/foto.png",
            audio_url="https://cdn.ejemplo/voz.wav",
            destino=destino,
            access_key="ak",
            secret_key="sk",
            duracion_s=15,
            cliente=Cliente(),
            descargar=lambda _url: Respuesta(b"video"),
        )
        self.assertEqual(resultado.video.read_bytes(), b"video")
        texto = resultado.subtitulos.read_text(encoding="utf-8")
        self.assertIn("Buenas noches.", texto)
        self.assertIn("00:00:00,000", texto)

    def test_kling_pide_1080p_sin_marca(self):
        cuerpo = cuerpo_gesto("https://cdn.ejemplo/foto.png", "https://cdn.ejemplo/gesto.mp4")
        self.assertEqual(cuerpo["settings"]["resolution"], "1080p")
        self.assertFalse(cuerpo["options"]["watermark_info"]["enabled"])

    def test_la_rubrica_vacia_no_automatiza(self):
        self.assertEqual(siguiente_paso(json.loads(RUBRICA.read_text(encoding="utf-8"))), "incompleta")
        self.assertEqual(
            siguiente_paso(
                {
                    "cara_se_sostiene": True,
                    "manos_rotas": False,
                    "gesto_real_requerido": False,
                    "resolucion_baja": False,
                    "formato_ancla_sentada": False,
                }
            ),
            "automatizar",
        )
        self.assertEqual(
            siguiente_paso(
                {
                    "cara_se_sostiene": True,
                    "manos_rotas": True,
                    "gesto_real_requerido": False,
                    "resolucion_baja": False,
                    "formato_ancla_sentada": False,
                }
            ),
            "kling",
        )

    def test_la_simulacion_del_piloto_no_gasta(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            codigo = main(["piloto"])
        self.assertEqual(codigo, 0)
        self.assertIn("6.30 USD", buffer.getvalue())
        self.assertIn("Simulación", buffer.getvalue())

    def test_producir_no_llama_a_la_api_si_la_rubrica_esta_vacia(self):
        codigo = main(["producir", "--persona", "tu", "--texto", "Hola desde el noticiero de esta noche."])
        self.assertEqual(codigo, 1)


if __name__ == "__main__":
    unittest.main()
