"""Shareable weekly-reflection snapshots.

Persists a frozen copy of a `WeeklyReflection` to disk under a generated id
so it can be retrieved via a public read-only URL.
"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..models.reflection import WeeklyReflection
from ..services.reflection import build_weekly_reflection
from ..storage import list_entries

router = APIRouter()

DATA_DIR = Path(__file__).parent.parent.parent / ".data"
SHARED_FILE = DATA_DIR / "shared_reflections.json"


def _read_all() -> dict:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not SHARED_FILE.exists():
        return {}
    return json.loads(SHARED_FILE.read_text(encoding="utf-8"))


def _write_all(data: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SHARED_FILE.write_text(
        json.dumps(data, indent=2, default=str), encoding="utf-8"
    )


@router.post("/reflection/share")
def create_share() -> dict:
    """Snapshot the current weekly reflection and return a share id."""
    now = datetime.now(timezone.utc)
    entries = list_entries()
    reflection = build_weekly_reflection(entries, now)

    share_id = uuid.uuid4().hex[:10]
    store = _read_all()
    store[share_id] = {
        "created_at": now.isoformat(),
        "reflection": reflection.model_dump(mode="json"),
    }
    _write_all(store)
    return {"id": share_id}


@router.get("/shared/{share_id}", response_model=WeeklyReflection)
def get_share(share_id: str) -> WeeklyReflection:
    store = _read_all()
    record = store.get(share_id)
    if not record:
        raise HTTPException(status_code=404, detail="Shared reflection not found")
    return WeeklyReflection(**record["reflection"])
