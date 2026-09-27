from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from database import get_connection, init_db

load_dotenv()

app = FastAPI(title="Apogée Wine")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

init_db()


@app.get("/")
def index(request: Request):
    conn = get_connection()
    try:
        bottle_count = conn.execute("SELECT COUNT(*) FROM bottles").fetchone()[0]
    finally:
        conn.close()
    return templates.TemplateResponse(
        request, "index.html", {"bottle_count": bottle_count}
    )
