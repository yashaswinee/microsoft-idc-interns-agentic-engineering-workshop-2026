"""Smoke test for the weekly reflection route."""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient


def _create_entry_on_date(client: TestClient, mood: int, energy: int, when: datetime) -> None:
    """Create an entry through the API, then patch the stored timestamp."""
    from app import storage

    resp = client.post("/api/entries", json={"mood": mood, "energy": energy, "tags": ["sleep"]})
    assert resp.status_code == 201
    entry_id = resp.json()["id"]
    raw = storage._read_all()
    for e in raw:
        if e["id"] == entry_id:
            e["timestamp"] = when.isoformat()
    storage._write_all(raw)


class TestWeeklyReflectionRoute:
    def test_route_returns_normal_mode_when_seeded(self, client: TestClient):
        now = datetime.now(timezone.utc)
        for i in range(7):
            _create_entry_on_date(client, mood=3 + (i % 2), energy=6, when=now - timedelta(days=i))

        resp = client.get("/api/reflection/weekly")
        assert resp.status_code == 200
        data = resp.json()

        assert data["mode"] == "normal"
        assert data["entry_count"] == 7
        assert data["days_with_entries"] == 7
        assert "start" in data["window"] and "end" in data["window"]
        assert data["trend"]["label"] in {"improving", "declining", "flat"}
        assert data["narrative"]
        assert data["reflection_prompt"] == "What would you do differently next week?"
        assert data["share_text"].rstrip().endswith("— Shared from Pulse")
        assert data["suggestion"] is None
        # The reflection prompt is now bucketed by mode + trend; just check
        # the smoke-test contract that a non-empty question came back.
        assert data["reflection_prompt"] is not None
        assert data["reflection_prompt"].endswith("?")

    def test_route_returns_empty_mode_when_storage_empty(self, client: TestClient):
        resp = client.get("/api/reflection/weekly")
        assert resp.status_code == 200
        data = resp.json()

        assert data["mode"] == "empty"
        assert data["entry_count"] == 0
        assert data["days_with_entries"] == 0
        assert data["avg_mood"] is None
        assert data["avg_energy"] is None
        assert data["best_day"] is None
        assert data["worst_day"] is None
        assert data["top_tags"] == []
        assert data["narrative"] is None
        assert data["suggestion"] is None
        assert data["share_text"] is None
        assert data["trend"]["label"] == "insufficient_data"
        assert data["trend"]["slope"] is None
        assert data["reflection_prompt"] is not None
