import base64
import json
import os
from pathlib import Path

from groq import Groq

from enums import Couleur

MODEL = "qwen/qwen3.8-27b"

_client: Groq | None = None

MIME_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
}

PROMPT = """Tu regardes une photo d'une ou plusieurs bouteilles de vin.
Identifie chaque bouteille visible et réponds UNIQUEMENT avec un objet JSON de cette forme,
sans texte autour, sans balises markdown :

{
  "bouteilles": [
    {
      "nom": "nom ou cuvee de la bouteille, ou null si illisible",
      "domaine": "domaine/producteur/chateau, ou null",
      "millesime": annee en nombre entier ou null,
      "couleur": "rouge" ou "blanc" ou "rose" ou "effervescent",
      "region": "region, ou null",
      "pays": "pays, ou null",
      "cepages": "cepage(s) separes par des virgules, ou null"
    }
  ]
}

Si tu ne vois aucune bouteille de vin, reponds {"bouteilles": []}.
Si une bouteille est floue ou partiellement visible, fais ton meilleur essai plutot que de l'ignorer."""


def get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    return _client


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


def analyser_photo(photo_file: Path) -> list[dict]:
    image_bytes = photo_file.read_bytes()
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    mime = MIME_TYPES.get(photo_file.suffix.lower(), "image/jpeg")

    response = get_client().chat.completions.create(
        model=MODEL,
        temperature=0,
        max_tokens=1500,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{b64}"},
                    },
                ],
            }
        ],
    )
    data = _extract_json(response.choices[0].message.content)
    couleurs_valides = {c.value for c in Couleur}

    drafts = []
    for b in data.get("bouteilles", []):
        couleur = b.get("couleur")
        if couleur not in couleurs_valides:
            couleur = Couleur.ROUGE.value
        drafts.append(
            {
                "nom": b.get("nom") or "",
                "domaine": b.get("domaine") or "",
                "millesime": b.get("millesime") or "",
                "couleur": couleur,
                "region": b.get("region") or "",
                "pays": b.get("pays") or "",
                "cepages": b.get("cepages") or "",
                "photo_path": photo_file.name,
            }
        )
    return drafts
