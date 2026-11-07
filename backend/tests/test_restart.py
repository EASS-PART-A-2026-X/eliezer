from fastapi.testclient import TestClient

from app import db
from app.main import app
from app.seed import DEMO_GARDEN, catalog_rows


def test_data_survives_restart_and_is_seeded_once(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'app.db'}"

    monkeypatch.setattr(db, "engine", db.make_engine(url))  # "process" 1
    with TestClient(app) as client:  # `with` runs lifespan startup + shutdown
        garden = client.get("/garden").json()
        assert len(garden) == len(DEMO_GARDEN)  # demo garden seeded
        assert client.get("/plants", params={"q": "Salvia rosmarinus"}).json()
        first = garden[0]["id"]
        client.post(f"/garden/{first}/water")
        client.delete(f"/garden/{garden[1]['id']}")

    monkeypatch.setattr(db, "engine", db.make_engine(url))  # "process" 2
    with TestClient(app) as client:
        after = client.get("/garden").json()
        rosemary = client.get("/plants", params={"q": "Salvia rosmarinus"}).json()
    assert len(after) == len(DEMO_GARDEN) - 1  # the deletion stuck; no reseed
    assert len(rosemary) == 1  # catalog not loaded twice
    assert next(p for p in after if p["id"] == first)["days_until_watering"] >= 6


def test_full_catalog_loads(session):
    from app.seed import seed_catalog_if_empty

    assert seed_catalog_if_empty(session) == len(catalog_rows())
    assert seed_catalog_if_empty(session) == 0
