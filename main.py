import uuid
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from database import (
    init_db,
    insert_bottle,
    list_bottles,
    list_millesimes,
    list_regions,
    list_used_photo_paths,
)
from enums import Couleur
from vision import analyser_photo

load_dotenv()

app = FastAPI(title="Apogée Wine")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

init_db()

UPLOAD_DIR = Path(__file__).parent / "static" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@app.get("/")
def index(
    request: Request,
    couleur: Optional[str] = None,
    millesime: Optional[str] = None,
    region: Optional[str] = None,
    cepage: Optional[str] = None,
):
    couleur = couleur or None
    region = region or None
    cepage = cepage or None
    millesime_int = int(millesime) if millesime else None

    bottles = list_bottles(
        couleur=couleur,
        millesime=millesime_int,
        region=region,
        cepage=cepage,
    )
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "bottles": bottles,
            "couleurs": list(Couleur),
            "regions": list_regions(),
            "millesimes": list_millesimes(),
            "filters": {
                "couleur": couleur or "",
                "millesime": millesime_int or "",
                "region": region or "",
                "cepage": cepage or "",
            },
        },
    )


@app.get("/bouteilles/nouvelle")
def nouvelle_bouteille(request: Request):
    return templates.TemplateResponse(
        request, "nouvelle_bouteille.html", {"couleurs": list(Couleur)}
    )


@app.post("/bouteilles")
def create_bottle(
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
    insert_bottle(
        {
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
    return RedirectResponse(url="/", status_code=303)


@app.get("/photos/nouvelle")
def nouvelle_photo(request: Request):
    return templates.TemplateResponse(request, "nouvelle_photo.html", {})


@app.post("/photos")
async def upload_photos(photos: List[UploadFile] = File(...)):
    for photo in photos:
        if not (photo.content_type or "").startswith("image/"):
            continue
        extension = Path(photo.filename or "").suffix
        unique_name = f"{uuid.uuid4().hex}{extension}"
        destination = UPLOAD_DIR / unique_name
        with destination.open("wb") as f:
            f.write(await photo.read())
    return RedirectResponse(url="/photos", status_code=303)


@app.get("/photos")
def list_photos(request: Request):
    files = sorted(
        (f for f in UPLOAD_DIR.iterdir() if f.is_file() and not f.name.startswith(".")),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )
    used = list_used_photo_paths()
    photos = [{"name": f.name, "utilisee": f.name in used} for f in files]
    a_analyser = sum(1 for p in photos if not p["utilisee"])
    return templates.TemplateResponse(
        request, "photos.html", {"photos": photos, "a_analyser": a_analyser}
    )


@app.post("/photos/analyser")
def analyser_photos(request: Request, photos: List[str] = Form([])):
    used = list_used_photo_paths()
    a_traiter = []
    for name in photos:
        if name in used or Path(name).name != name:
            continue
        photo_file = UPLOAD_DIR / name
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
        {"drafts": drafts, "erreurs": erreurs, "couleurs": list(Couleur)},
    )


@app.post("/photos/{name}/supprimer")
def supprimer_photo(name: str):
    if Path(name).name != name:
        return RedirectResponse(url="/photos", status_code=303)
    if name not in list_used_photo_paths():
        photo_file = UPLOAD_DIR / name
        if photo_file.is_file():
            photo_file.unlink()
    return RedirectResponse(url="/photos", status_code=303)
