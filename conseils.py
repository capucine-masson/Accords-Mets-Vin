import json
import os
import sqlite3
from datetime import date

from groq import Groq

MODEL = "openai/gpt-oss-20b"

_client: Groq | None = None


def get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    return _client


def _decrire_bouteille(bottle: sqlite3.Row) -> str:
    parts = [bottle["nom"], bottle["couleur"]]
    if bottle["domaine"]:
        parts.append(bottle["domaine"])
    if bottle["millesime"]:
        parts.append(str(bottle["millesime"]))
    if bottle["region"] or bottle["pays"]:
        parts.append(", ".join(p for p in [bottle["region"], bottle["pays"]] if p))
    if bottle["cepages"]:
        parts.append(f"cépages: {bottle['cepages']}")
    return " - ".join(str(p) for p in parts if p)


def suggerer_accord(bottle: sqlite3.Row) -> str:
    description = _decrire_bouteille(bottle)
    response = get_client().chat.completions.create(
        model=MODEL,
        temperature=0.4,
        max_tokens=600,
        messages=[
            {
                "role": "user",
                "content": (
                    "Tu es sommelier. Pour ce vin, propose en 2-3 phrases maximum "
                    "un accord mets et vin concret (un ou deux plats précis). "
                    "Réponds UNIQUEMENT en français, avec le texte de la suggestion, "
                    "sans introduction.\n\n"
                    f"Vin : {description}"
                ),
            }
        ],
    )
    return response.choices[0].message.content.strip()


def _extract_json(content: str) -> dict:
    content = content.strip()
    if content.startswith("```"):
        content = content.strip("`")
        if content.lower().startswith("json"):
            content = content[4:]
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        start, end = content.find("{"), content.rfind("}")
        if start == -1 or end == -1:
            raise
        return json.loads(content[start : end + 1])


def estimer_apogee(bottle: sqlite3.Row) -> tuple[int, int]:
    description = _decrire_bouteille(bottle)
    annee_actuelle = date.today().year
    response = get_client().chat.completions.create(
        model=MODEL,
        temperature=0,
        max_tokens=500,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "user",
                "content": (
                    f"Nous sommes en {annee_actuelle}. Tu es sommelier. Estime la fenêtre "
                    "d'apogée (période idéale de consommation) de ce vin, en te basant sur "
                    "son type, son millésime et sa région. Réponds uniquement en français, "
                    "avec un objet JSON de la forme "
                    '{"apogee_debut": annee, "apogee_fin": annee}. '
                    "IMPORTANT : apogee_debut et apogee_fin doivent être des ANNÉES CALENDAIRES "
                    f"ABSOLUES à 4 chiffres (par exemple {annee_actuelle + 2}), jamais un nombre "
                    "d'années ou un décalage relatif. Si le millésime est inconnu, base-toi sur "
                    "une bouteille achetée récemment.\n\n"
                    f"Vin : {description}"
                ),
            }
        ],
    )
    data = _extract_json(response.choices[0].message.content)
    debut, fin = int(data["apogee_debut"]), int(data["apogee_fin"])
    if not (1900 <= debut <= 2200) or not (1900 <= fin <= 2200):
        raise ValueError(f"Années d'apogée invalides reçues du modèle : {debut}-{fin}")
    return debut, fin
