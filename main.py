from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from database import init_db, insert_bottle, list_bottles, list_millesimes, list_regions
from enums import Couleur

load_dotenv()

app = FastAPI(title="Apogée Wine")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

init_db()


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
        }
    )
    return RedirectResponse(url="/", status_code=303)
