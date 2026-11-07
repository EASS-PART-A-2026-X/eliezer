from fastapi.testclient import TestClient

from app import db
from app.main import app
from app.models import ItemCreate
from app.seed import SEED, seed_if_empty


def test_data_survives_restart(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'app.db'}"

    monkeypatch.setattr(db, "engine", db.make_engine(url))  # "process" 1
    with TestClient(app) as client:  # `with` runs lifespan startup + shutdown
        assert len(client.get("/items").json()) == len(SEED)  # seeded
        client.post("/items", json={"title": "Survives restarts"})

    monkeypatch.setattr(db, "engine", db.make_engine(url))  # "process" 2
    with TestClient(app) as client:
        titles = [i["title"] for i in client.get("/items").json()]
    assert titles == [row["title"] for row in SEED] + ["Survives restarts"]  # no reseed


def test_seed_is_valid_and_idempotent(session):
    for row in SEED:  # same rules as a POST body, including no unknown keys
        ItemCreate.model_validate(row)
    assert seed_if_empty(session) == len(SEED)
    assert seed_if_empty(session) == 0
