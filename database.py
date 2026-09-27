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


def list_bottles(
    statut: str = StatutBouteille.EN_CAVE.value,
    couleur: str | None = None,
    millesime: int | None = None,
    region: str | None = None,
    cepage: str | None = None,
) -> list[sqlite3.Row]:
    conditions = ["statut = ?"]
    params: list = [statut]

    if couleur:
        conditions.append("couleur = ?")
        params.append(couleur)
    if millesime:
        conditions.append("millesime = ?")
        params.append(millesime)
    if region:
        conditions.append("region = ?")
        params.append(region)
    if cepage:
        conditions.append("cepages LIKE ?")
        params.append(f"%{cepage}%")

    query = f"SELECT * FROM bottles WHERE {' AND '.join(conditions)} ORDER BY nom COLLATE NOCASE"
    conn = get_connection()
    try:
        return conn.execute(query, params).fetchall()
    finally:
        conn.close()


def list_regions() -> list[str]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT DISTINCT region FROM bottles"
            " WHERE region IS NOT NULL AND region != ''"
            " ORDER BY region COLLATE NOCASE"
        ).fetchall()
        return [r[0] for r in rows]
    finally:
        conn.close()


def list_millesimes() -> list[int]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT DISTINCT millesime FROM bottles"
            " WHERE millesime IS NOT NULL"
            " ORDER BY millesime DESC"
        ).fetchall()
        return [r[0] for r in rows]
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
