from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from database.connection import connection, initialize_database
from database.schema import create_schema
from database.store import CORE, replace_species, write_document, write_rows

DATA_DIR = BACKEND_ROOT / "data"
ORDER = [
    "users.json", "community_organisations.json", "classes.json", "programs.json",
    "conservation_programs.json", "community_memberships.json", "community_join_requests.json",
    "enrollments.json", "learning_activities.json", "program_enrollments.json",
    "community_contributions.json", "species_sightings.json",
]


def _load(path: Path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def migrate() -> dict[str, int]:
    initialize_database(); create_schema()
    counts: dict[str, int] = {}
    app_path = DATA_DIR / "komodo_hub.json"
    if app_path.is_file():
        app = _load(app_path)
        if isinstance(app, dict):
            write_document("komodo_hub", app)
            species = app.get("species") if isinstance(app.get("species"), list) else []
            replace_species(species); counts["species"] = len(species)

    names = [p.name for p in DATA_DIR.glob("*.json") if p.name not in {"komodo_hub.json", "sessions.json"}]
    ordered = ORDER + sorted(name for name in names if name not in ORDER)
    for name in ordered:
        path = DATA_DIR / name
        if not path.is_file():
            continue
        rows = _load(path)
        if isinstance(rows, list):
            write_rows(name, rows); counts[name] = len(rows)

    sessions_path = DATA_DIR / "sessions.json"
    if sessions_path.is_file():
        sessions = _load(sessions_path)
        if isinstance(sessions, dict):
            with connection() as conn:
                cursor = conn.cursor()
                for token, row in sessions.items():
                    if not isinstance(row, dict) or not row.get("userId") or not row.get("expiresAt"):
                        continue
                    cursor.execute(
                        "INSERT IGNORE INTO sessions(token_hash,user_id,expires_at) VALUES(%s,%s,%s)",
                        (hashlib.sha256(token.encode()).hexdigest(), row["userId"], row["expiresAt"]),
                    )
                conn.commit(); cursor.close()
            counts["sessions"] = len(sessions)
    return counts


if __name__ == "__main__":
    result = migrate()
    print("Migration completed.")
    for collection, count in sorted(result.items()):
        print(f"  {collection}: {count}")
