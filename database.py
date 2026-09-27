import sqlite3
from pathlib import Path

from enums import Couleur, StatutBouteille

DB_PATH = Path(__file__).parent / "cave.db"

COULEURS_SQL = ", ".join(f"'{c.value}'" for c in Couleur)
STATUTS_SQL = ", ".join(f"'{s.value}'" for s in StatutBouteille)


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_connection()
    try:
        conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS bottles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nom TEXT NOT NULL,
                domaine TEXT,
                millesime INTEGER,
                couleur TEXT NOT NULL CHECK (couleur IN ({COULEURS_SQL})),
                region TEXT,
                pays TEXT,
                cepages TEXT,
                prix_achat REAL,
                quantite INTEGER NOT NULL DEFAULT 1,
                date_achat TEXT,
                note TEXT,
                statut TEXT NOT NULL DEFAULT '{StatutBouteille.EN_CAVE.value}' CHECK (statut IN ({STATUTS_SQL}))
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def list_bottles(statut: str = StatutBouteille.EN_CAVE.value) -> list[sqlite3.Row]:
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT * FROM bottles WHERE statut = ? ORDER BY nom COLLATE NOCASE",
            (statut,),
        ).fetchall()
    finally:
        conn.close()


def insert_bottle(bottle: dict) -> int:
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            INSERT INTO bottles
                (nom, domaine, millesime, couleur, region, pays, cepages,
                 prix_achat, quantite, date_achat, note, statut)
            VALUES
                (:nom, :domaine, :millesime, :couleur, :region, :pays, :cepages,
                 :prix_achat, :quantite, :date_achat, :note, :statut)
            """,
            bottle,
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()
