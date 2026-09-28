import os
import re
import uuid
from datetime import date
from itertools import groupby
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from database import (
    fusionner_doublons,
    get_bottle,
    init_db,
    insert_bottle,
    list_a_boire_bientot,
    list_bottles,
    list_millesimes,
    list_regions,
    list_used_photo_paths,
    update_bottle,
)
from enums import COULEUR_LABELS, Couleur, StatutBouteille
from conseils import estimer_apogee, suggerer_accord
from vision import analyser_photo

load_dotenv()

app = FastAPI(title="Apogée Wine")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

init_db()

PUBLIC_PATHS = {"/login"}


@app.middleware("http")
async def require_login(request: Request, call_next):
    path = request.url.path
    if path in PUBLIC_PATHS or path.startswith("/static/"):
        return await call_next(request)
    if not request.session.get("authenticated"):
        return RedirectResponse(url="/login", status_code=303)
    return await call_next(request)


# Starlette exécute le DERNIER middleware ajouté en PREMIER : SessionMiddleware
# doit donc être ajouté après require_login pour que request.session existe
# quand require_login s'exécute.
app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get("APP_SECRET_KEY", "dev-secret-a-changer"),
)


def cle_utilisateur(request: Request) -> str:
    """Identifiant normalisé qui sépare la cave (et les photos) de chaque
    personne : deux identifiants qui ne diffèrent que par la casse ou des
    espaces partagent la même cave, deux identifiants différents ont chacun
    la leur."""
    brut = request.session.get("utilisateur", "")
    cle = re.sub(r"[^a-z0-9_-]+", "_", brut.strip().lower())
    return cle or "invite"


@app.get("/login")
def login_form(request: Request, erreur: Optional[str] = None):
    return templates.TemplateResponse(request, "login.html", {"erreur": erreur})


@app.post("/login")
def login(request: Request, identifiant: str = Form(...)):
    identifiant = identifiant.strip()
    if not identifiant:
        return RedirectResponse(url="/login?erreur=1", status_code=303)
    request.session["authenticated"] = True
    request.session["utilisateur"] = identifiant
    return RedirectResponse(url="/", status_code=303)


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)


UPLOAD_ROOT = Path(__file__).parent / "static" / "uploads"
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)


def _migrer_photos_historiques() -> None:
    """Photos importées avant l'introduction des caves séparées : déplacées
    une bonne fois pour toutes vers le dossier de l'identifiant historique."""
    destination = UPLOAD_ROOT / "capucine"
    a_deplacer = [f for f in UPLOAD_ROOT.iterdir() if f.is_file() and not f.name.startswith(".")]
    if not a_deplacer:
        return
    destination.mkdir(parents=True, exist_ok=True)
    for fichier in a_deplacer:
        fichier.rename(destination / fichier.name)


_migrer_photos_historiques()


def upload_dir(cle: str) -> Path:
    dossier = UPLOAD_ROOT / cle
    dossier.mkdir(parents=True, exist_ok=True)
    return dossier


def safe_next(url: str) -> str:
    if not url.startswith("/") or url.startswith("//"):
        return "/"
    return url


@app.get("/")
def index(
    request: Request,
    couleur: Optional[str] = None,
    millesime: Optional[str] = None,
    region: Optional[str] = None,
    cepage: Optional[str] = None,
    erreur: Optional[str] = None,
    info: Optional[str] = None,
):
    cle = cle_utilisateur(request)
    couleur = couleur or None
    region = region or None
    cepage = cepage or None
    millesime_int = int(millesime) if millesime else None

    bottles = list_bottles(
        cle,
        couleur=couleur,
        millesime=millesime_int,
        region=region,
        cepage=cepage,
    )
    groupes = [
        {"couleur": c, "label": COULEUR_LABELS.get(c, c), "bottles": list(items)}
        for c, items in groupby(bottles, key=lambda b: b["couleur"])
    ]
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "bottles": bottles,
            "groupes": groupes,
            "couleurs": list(Couleur),
            "regions": list_regions(cle),
            "millesimes": list_millesimes(cle),
            "filters": {
                "couleur": couleur or "",
                "millesime": millesime_int or "",
                "region": region or "",
                "cepage": cepage or "",
            },
            "a_boire_bientot": list_a_boire_bientot(cle),
            "erreur": erreur,
            "info": info,
        },
    )


@app.get("/bouteilles/nouvelle")
def nouvelle_bouteille(request: Request):
    return templates.TemplateResponse(
        request, "nouvelle_bouteille.html", {"couleurs": list(Couleur)}
    )


@app.post("/bouteilles/nouvelle/photos")
async def ajouter_par_photo(request: Request, photos: List[UploadFile] = File(...)):
    cle = cle_utilisateur(request)
    drafts = []
    erreurs = []
    for photo in photos:
        destination = await _sauver_photo(photo, cle)
        if destination is None:
            erreurs.append({"photo": photo.filename or "?", "erreur": "Fichier non reconnu comme une image."})
            continue
        try:
            drafts.extend(analyser_photo(destination))
        except Exception as exc:
            erreurs.append({"photo": destination.name, "erreur": str(exc)})

    return templates.TemplateResponse(
        request,
        "brouillons.html",
        {"drafts": drafts, "erreurs": erreurs, "couleurs": list(Couleur), "upload_prefix": cle},
    )


@app.post("/bouteilles")
def create_bottle(
    request: Request,
    nom: str = Form(...),
    domaine: str = Form(""),
    millesime: str = Form(""),
    couleur: Couleur = Form(...),
    region: str = Form(""),
    pays: str = Form(""),
    cepages: str = Form(""),
    prix_achat: str = Form(""),
    quantite: int = Form(1),
    date_achat: str = Form(""),
    note: str = Form(""),
    photo_path: str = Form(""),
):
    cle = cle_utilisateur(request)
    bottle_id = insert_bottle(
        {
            "proprietaire": cle,
            "nom": nom,
            "domaine": domaine or None,
            "millesime": int(millesime) if millesime else None,
            "couleur": couleur.value,
            "region": region or None,
            "pays": pays or None,
            "cepages": cepages or None,
            "prix_achat": float(prix_achat) if prix_achat else None,
            "quantite": quantite,
            "date_achat": date_achat or None,
            "note": note or None,
            "statut": "en_cave",
            "photo_path": photo_path or None,
        }
    )
    bottle = get_bottle(cle, bottle_id)
    try:
        update_bottle(bottle_id, {"accord_mets": suggerer_accord(bottle)})
    except Exception:
        pass
    try:
        debut, fin = estimer_apogee(bottle)
        update_bottle(bottle_id, {"apogee_debut": debut, "apogee_fin": fin})
    except Exception:
        pass
    return RedirectResponse(url=f"/bouteilles/{bottle_id}", status_code=303)


@app.get("/bouteilles/{bottle_id}")
def voir_bouteille(request: Request, bottle_id: int, erreur: Optional[str] = None):
    bottle = get_bottle(cle_utilisateur(request), bottle_id)
    if bottle is None:
        return RedirectResponse(url="/", status_code=303)
    annee = date.today().year
    return templates.TemplateResponse(
        request, "bouteille.html", {"b": bottle, "annee": annee, "erreur": erreur}
    )


@app.post("/bouteilles/{bottle_id}/accord")
def suggerer_accord_bouteille(request: Request, bottle_id: int, next: str = Form("/")):
    next = safe_next(next)
    bottle = get_bottle(cle_utilisateur(request), bottle_id)
    if bottle is None:
        return RedirectResponse(url="/", status_code=303)
    try:
        accord = suggerer_accord(bottle)
        update_bottle(bottle_id, {"accord_mets": accord})
    except Exception:
        sep = "&" if "?" in next else "?"
        return RedirectResponse(
            url=f"{next}{sep}erreur=Impossible+de+contacter+Groq+pour+l%27accord+mets",
            status_code=303,
        )
    return RedirectResponse(url=next, status_code=303)


@app.post("/bouteilles/{bottle_id}/apogee")
def estimer_apogee_bouteille(request: Request, bottle_id: int, next: str = Form("/")):
    next = safe_next(next)
    bottle = get_bottle(cle_utilisateur(request), bottle_id)
    if bottle is None:
        return RedirectResponse(url="/", status_code=303)
    try:
        debut, fin = estimer_apogee(bottle)
        update_bottle(bottle_id, {"apogee_debut": debut, "apogee_fin": fin})
    except Exception:
        sep = "&" if "?" in next else "?"
        return RedirectResponse(
            url=f"{next}{sep}erreur=Impossible+de+contacter+Groq+pour+l%27apogee",
            status_code=303,
        )
    return RedirectResponse(url=next, status_code=303)


@app.post("/bouteilles/{bottle_id}/marquer-bue")
def marquer_bue(request: Request, bottle_id: int, next: str = Form("/")):
    bottle = get_bottle(cle_utilisateur(request), bottle_id)
    if bottle is None:
        return RedirectResponse(url="/", status_code=303)
    reste = bottle["quantite"] - 1
    if reste > 0:
        update_bottle(bottle_id, {"quantite": reste})
    else:
        update_bottle(bottle_id, {"quantite": 0, "statut": StatutBouteille.BUE.value})
    return RedirectResponse(url=safe_next(next), status_code=303)


@app.post("/bouteilles/{bottle_id}/remettre-en-cave")
def remettre_en_cave(request: Request, bottle_id: int, next: str = Form("/bues")):
    bottle = get_bottle(cle_utilisateur(request), bottle_id)
    if bottle is None:
        return RedirectResponse(url="/", status_code=303)
    update_bottle(
        bottle_id,
        {"statut": StatutBouteille.EN_CAVE.value, "quantite": bottle["quantite"] + 1},
    )
    return RedirectResponse(url=safe_next(next), status_code=303)


@app.post("/bouteilles/fusionner")
def fusionner(request: Request):
    fusions = fusionner_doublons(cle_utilisateur(request))
    if fusions:
        return RedirectResponse(url=f"/?info={fusions}+doublon(s)+fusionné(s).", status_code=303)
    return RedirectResponse(url="/?info=Aucun+doublon+trouvé.", status_code=303)


@app.get("/bues")
def bouteilles_bues(request: Request):
    bottles = list_bottles(cle_utilisateur(request), statut=StatutBouteille.BUE.value)
    return templates.TemplateResponse(request, "bues.html", {"bottles": bottles})


@app.get("/calendrier")
def calendrier(request: Request, erreur: Optional[str] = None):
    cle = cle_utilisateur(request)
    bottles = list_bottles(cle)
    aujourdhui = date.today()
    annee = aujourdhui.year

    pas_estimees = [b for b in bottles if b["apogee_fin"] is None]
    depassees = [
        b for b in bottles if b["apogee_fin"] is not None and b["apogee_fin"] < annee
    ]
    se_depecher = [
        b
        for b in bottles
        if b["apogee_fin"] is not None
        and b["apogee_debut"] is not None
        and b["apogee_debut"] <= annee
        and b["apogee_fin"] == annee
    ]
    a_boire = [
        b
        for b in bottles
        if b["apogee_fin"] is not None
        and b["apogee_debut"] is not None
        and b["apogee_debut"] <= annee < b["apogee_fin"]
    ]
    pas_encore_prete = [
        b for b in bottles if b["apogee_debut"] is not None and b["apogee_debut"] > annee
    ]

    return templates.TemplateResponse(
        request,
        "calendrier.html",
        {
            "depassees": depassees,
            "se_depecher": se_depecher,
            "a_boire": a_boire,
            "pas_encore_prete": pas_encore_prete,
            "pas_estimees": pas_estimees,
            "a_boire_bientot": list_a_boire_bientot(cle),
            "erreur": erreur,
        },
    )


@app.get("/photos/nouvelle")
def nouvelle_photo(request: Request):
    return templates.TemplateResponse(request, "nouvelle_photo.html", {})


async def _sauver_photo(photo: UploadFile, cle: str) -> Optional[Path]:
    if not (photo.content_type or "").startswith("image/"):
        return None
    extension = Path(photo.filename or "").suffix
    unique_name = f"{uuid.uuid4().hex}{extension}"
    destination = upload_dir(cle) / unique_name
    with destination.open("wb") as f:
        f.write(await photo.read())
    return destination


@app.post("/photos")
async def upload_photos(request: Request, photos: List[UploadFile] = File(...)):
    cle = cle_utilisateur(request)
    for photo in photos:
        await _sauver_photo(photo, cle)
    return RedirectResponse(url="/photos", status_code=303)


@app.get("/photos")
def list_photos(request: Request):
    cle = cle_utilisateur(request)
    dossier = upload_dir(cle)
    files = sorted(
        (f for f in dossier.iterdir() if f.is_file() and not f.name.startswith(".")),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )
    used = list_used_photo_paths(cle)
    photos = [{"name": f.name, "utilisee": f.name in used} for f in files]
    a_analyser = sum(1 for p in photos if not p["utilisee"])
    return templates.TemplateResponse(
        request,
        "photos.html",
        {"photos": photos, "a_analyser": a_analyser, "upload_prefix": cle},
    )


@app.post("/photos/analyser")
def analyser_photos(request: Request, photos: List[str] = Form([])):
    cle = cle_utilisateur(request)
    dossier = upload_dir(cle)
    used = list_used_photo_paths(cle)
    a_traiter = []
    for name in photos:
        if name in used or Path(name).name != name:
            continue
        photo_file = dossier / name
        if photo_file.is_file():
            a_traiter.append(photo_file)

    drafts = []
    erreurs = []
    for photo_file in a_traiter:
        try:
            drafts.extend(analyser_photo(photo_file))
        except Exception as exc:
            erreurs.append({"photo": photo_file.name, "erreur": str(exc)})

    return templates.TemplateResponse(
        request,
        "brouillons.html",
        {"drafts": drafts, "erreurs": erreurs, "couleurs": list(Couleur), "upload_prefix": cle},
    )


@app.post("/photos/{name}/supprimer")
def supprimer_photo(request: Request, name: str):
    if Path(name).name != name:
        return RedirectResponse(url="/photos", status_code=303)
    cle = cle_utilisateur(request)
    if name not in list_used_photo_paths(cle):
        photo_file = upload_dir(cle) / name
        if photo_file.is_file():
            photo_file.unlink()
    return RedirectResponse(url="/photos", status_code=303)
