# Noticiero de Instagram con OmniHuman 2.0

Dos dobles de cuerpo entero, el tuyo y el de un colaborador. El motor diario es OmniHuman 2.0: una foto de cuerpo entero y un audio. A 0,07 USD por segundo, el piloto de seis tomas de 15 segundos cuesta 6,30 USD, dentro de un tope de 20 USD. Precios del 25 de octubre de 2026.

HeyGen, Synthesia, D-ID, Elai y Colossyan quedan fuera: son cara o torso. Kling Motion Control entra solo si un gesto real no sale. Hour One está cerrado.

## Esta semana

1. Cada persona copia [la plantilla](consentimiento/plantilla.md) sobre `personas/tu/consentimiento.md` o `personas/colaborador/consentimiento.md`, quita los corchetes y firma.
2. Deja `foto.png` y `voz.wav` en esa carpeta. La foto va de pies a cabeza, de frente, en 9:16. La voz dura entre 30 y 60 segundos.
3. Marca las casillas de `captura.json`.
4. Revisa con `python -m noticias preparar`.
5. Graba el guion de `piloto/guion.json` en un WAV de unos 15 segundos, súbelo junto con la foto a una URL HTTPS y escribe `foto_url` y `audio_piloto_url`.
6. Carga unos 20 USD en BytePlus y pon las claves en el entorno, a partir de `.env.example`.
7. Simula el gasto con `python -m noticias piloto`. Envía las seis tomas con `python -m noticias piloto --ejecutar`.
8. Mira cara, manos, pies, labios y el recorte 9:16. Completa `revision/rubrica.json` y corre `python -m noticias decidir`.

## Después del piloto

- Si la cara se sostiene y las manos no se rompen, `python -m noticias producir --persona tu --texto "..." --audio-url https://...` arma el reel y los subtítulos.
- Si hace falta un gesto concreto, `python -m noticias gesto --persona tu` estima Kling 2.6 a 1080p (0,112 USD por segundo). El video de referencia dura de 3 a 30 segundos y va en `gesto_url`.
- OmniHuman no lee el guion. La voz clonada se hace en ElevenLabs y el MP3 tiene que quedar en una URL pública.

La simulación no llama a la API y no gasta crédito.
