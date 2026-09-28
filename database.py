import sqlite3
from pathlib import Path

from enums import Couleur, StatutBouteille

DB_PATH = Path(__file__).parent / "cave.db"

COULEURS_SQL = ", ".join(f"'{c.value}'" for c in Couleur)
STATUTS_SQL = ", ".join(f"'{s.value}'" for s in StatutBouteille)

ORDRE_COULEURS = [Couleur.ROUGE.value, Couleur.BLANC.value, Couleur.EFFERVESCENT.value, Couleur.ROSE.value]
ORDRE_COULEUR_SQL = "CASE couleur " + " ".join(
    f"WHEN '{c}' THEN {i}" for i, c in enumerate(ORDRE_COULEURS)
) + " ELSE 99 END"

PROPRIETAIRE_HERITE = "capucine"


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
                proprietaire TEXT NOT NULL DEFAULT '',
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
                statut TEXT NOT NULL DEFAULT '{StatutBouteille.EN_CAVE.value}' CHECK (statut IN ({STATUTS_SQL})),
                photo_path TEXT,
                accord_mets TEXT,
                apogee_debut INTEGER,
                apogee_fin INTEGER
            )
            """
        )
        existing_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(bottles)")
        }
        nouvelles_colonnes = {
            "proprietaire": "TEXT NOT NULL DEFAULT ''",
            "photo_path": "TEXT",
            "accord_mets": "TEXT",
            "apogee_debut": "INTEGER",
            "apogee_fin": "INTEGER",
        }
        for colonne, type_sql in nouvelles_colonnes.items():
            if colonne not in existing_columns:
                conn.execute(f"ALTER TABLE bottles ADD COLUMN {colonne} {type_sql}")
        # Bouteilles créées avant l'introduction des caves séparées par identifiant :
        # rattachées une bonne fois pour toutes à l'identifiant historique.
        conn.execute(
            "UPDATE bottles SET proprietaire = ? WHERE proprietaire = ''",
            (PROPRIETAIRE_HERITE,),
        )
        conn.commit()
    finally:
        conn.close()


def list_bottles(
    proprietaire: str,
    statut: str = StatutBouteille.EN_CAVE.value,
    couleur: str | None = None,
    millesime: int | None = None,
    region: str | None = None,
    cepage: str | None = None,
) -> list[sqlite3.Row]:
    conditions = ["proprietaire = ?", "statut = ?"]
    params: list = [proprietaire, statut]

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

    query = (
        f"SELECT * FROM bottles WHERE {' AND '.join(conditions)} "
        f"ORDER BY {ORDRE_COULEUR_SQL}, nom COLLATE NOCASE"
    )
    conn = get_connection()
    try:
        return conn.execute(query, params).fetchall()
    finally:
        conn.close()


def list_regions(proprietaire: str) -> list[str]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT DISTINCT region FROM bottles"
            " WHERE proprietaire = ? AND region IS NOT NULL AND region != ''"
            " ORDER BY region COLLATE NOCASE",
            (proprietaire,),
        ).fetchall()
        return [r[0] for r in rows]
    finally:
        conn.close()


def list_millesimes(proprietaire: str) -> list[int]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT DISTINCT millesime FROM bottles"
            " WHERE proprietaire = ? AND millesime IS NOT NULL"
            " ORDER BY millesime DESC",
            (proprietaire,),
        ).fetchall()
        return [r[0] for r in rows]
    finally:
        conn.close()


def insert_bottle(bottle: dict) -> int:
    bottle = {"photo_path": None, **bottle}
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            INSERT INTO bottles
                (proprietaire, nom, domaine, millesime, couleur, region, pays, cepages,
                 prix_achat, quantite, date_achat, note, statut, photo_path)
            VALUES
                (:proprietaire, :nom, :domaine, :millesime, :couleur, :region, :pays, :cepages,
                 :prix_achat, :quantite, :date_achat, :note, :statut, :photo_path)
            """,
            bottle,
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def list_used_photo_paths(proprietaire: str) -> set[str]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT DISTINCT photo_path FROM bottles"
            " WHERE proprietaire = ? AND photo_path IS NOT NULL",
            (proprietaire,),
        ).fetchall()
        return {r[0] for r in rows}
    finally:
        conn.close()


def get_bottle(proprietaire: str, bottle_id: int) -> sqlite3.Row | None:
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT * FROM bottles WHERE id = ? AND proprietaire = ?",
            (bottle_id, proprietaire),
        ).fetchone()
    finally:
        conn.close()


def update_bottle(bottle_id: int, fields: dict) -> None:
    colonnes = ", ".join(f"{cle} = :{cle}" for cle in fields)
    conn = get_connection()
    try:
        conn.execute(
            f"UPDATE bottles SET {colonnes} WHERE id = :id",
            {**fields, "id": bottle_id},
        )
        conn.commit()
    finally:
        conn.close()


def list_a_boire_bientot(proprietaire: str, dans_les_jours: int = 180) -> list[sqlite3.Row]:
    conn = get_connection()
    try:
        return conn.execute(
            """
            SELECT * FROM bottles
            WHERE proprietaire = ?
              AND statut = ?
              AND apogee_fin IS NOT NULL
              AND apogee_fin <= CAST(strftime('%Y', 'now', ? || ' days') AS INTEGER)
            ORDER BY apogee_fin ASC
            """,
            (proprietaire, StatutBouteille.EN_CAVE.value, dans_les_jours),
        ).fetchall()
    finally:
        conn.close()
