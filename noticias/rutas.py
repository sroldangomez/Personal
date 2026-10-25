from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PERSONAS = RAIZ / "personas"
PLANTILLA_CONSENTIMIENTO = RAIZ / "consentimiento" / "plantilla.md"
GUION_PILOTO = RAIZ / "piloto" / "guion.json"
RUBRICA = RAIZ / "revision" / "rubrica.json"
SALIDA = RAIZ / "salida"

PERSONA_IDS = ("tu", "colaborador")
