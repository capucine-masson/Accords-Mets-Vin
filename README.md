# Apogée Wine

Accordeur mets et vin : cataloguer sa cave, savoir quand boire chaque bouteille (apogée), obtenir des suggestions d'accords mets/vin, et être alerté quand une bouteille traîne depuis trop longtemps.

## Fonctionnalités

- Ajout de bouteilles manuellement ou par photo (une ou plusieurs bouteilles par photo, reconnaissance automatique via IA)
- Vue de la cave triée par couleur, avec filtres (couleur, millésime, région, cépage)
- Suggestion d'accord mets/vin et estimation de la fenêtre d'apogée générées automatiquement à l'ajout (via IA)
- Calendrier d'apogée (dépassée / à boire vite / à boire maintenant / pas encore prête)
- Fusion automatique des doublons (même vin ajouté plusieurs fois → quantité cumulée)
- Statut "bue" / "en cave", avec décrément de quantité plutôt qu'un simple bascule
- Connexion factice : un identifiant = une cave, totalement séparée des autres identifiants

## Lancer le projet

```bash
pip install -r requirements.txt
```

Créer un fichier `.env` à la racine (voir `.env.example`) :

```
GROQ_API_KEY=ta_cle_groq
APP_SECRET_KEY=une_chaine_secrete_quelconque
```

Puis démarrer le serveur :

```bash
uvicorn main:app --reload
```

Ouvrir `http://localhost:8000`, se connecter avec l'identifiant de son choix (aucun mot de passe : la connexion sert uniquement à séparer les caves de chacun).

## Choix techniques

- **Backend** : FastAPI (routes synchrones sauf upload de fichiers)
- **Base de données** : SQLite en accès direct (module `sqlite3`, pas d'ORM)
- **Frontend** : Jinja2 + un peu de JS vanilla (pas de framework JS), CSS custom
- **IA (Groq)** :
  - `qwen/qwen3.8-27b` (vision) pour reconnaître les bouteilles sur une photo
  - `openai/gpt-oss-20b` (texte) pour l'accord mets et l'estimation d'apogée
- **Auth** : session signée (Starlette `SessionMiddleware`), pas de vrai mot de passe — volontairement factice
- **Multi-cave** : chaque identifiant a sa propre cave (colonne `proprietaire` en base) et son propre dossier de photos (`static/uploads/<identifiant>/`)

## Architecture

```
main.py          routes FastAPI (pages + actions)
database.py      accès SQLite (schéma, requêtes)
vision.py        appel Groq vision (analyse de photo)
conseils.py      appel Groq texte (accord mets, apogée)
enums.py         enums (Couleur, StatutBouteille)
templates/       pages Jinja2 (base.html + une page par écran)
static/style.css feuille de style
static/uploads/  photos importées, un sous-dossier par identifiant
cave.db          base SQLite (générée au démarrage, non versionnée)
```

Chaque bouteille appartient à un `proprietaire` (l'identifiant saisi à la connexion, normalisé). Toutes les requêtes de lecture/écriture sont filtrées par ce propriétaire, y compris l'accès direct à une bouteille par son URL.
