from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel
from sqlmodel.pool import StaticPool

from app import clock, db
from app.ai_client import AIClient, get_ai_client
from app.main import app
from app.models import CareSource, Plant

# Mid-morning in Israel; tests move time with `frozen_clock.advance(days=...)`.
START = datetime(2026, 11, 7, 8, 0, tzinfo=UTC)


class FrozenClock:
    def __init__(self) -> None:
        self.current = START

    def advance(self, **delta) -> None:
        self.current += timedelta(**delta)

    def __call__(self) -> datetime:
        return self.current


@pytest.fixture
def session() -> Iterator[Session]:
    """A fresh in-memory database for every test, foreign keys enforced."""
    engine = db.make_engine("sqlite://", poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()  # else: ResourceWarning (an error under filterwarnings)


@pytest.fixture
def frozen_clock() -> FrozenClock:
    return FrozenClock()


@pytest.fixture
def client(session: Session, frozen_clock: FrozenClock) -> Iterator[TestClient]:
    app.dependency_overrides[db.get_session] = lambda: session
    app.dependency_overrides[clock.now] = frozen_clock
    yield TestClient(app)  # no `with`: the lifespan (and the seed) does not run
    app.dependency_overrides.clear()


@pytest.fixture
def catalog(session: Session) -> dict[str, Plant]:
    """A small catalog: one curated plant, one without care, one genus."""
    plants = [
        Plant(
            scientific_name="Salvia rosmarinus",
            name_en="Rosemary",
            name_he="רוזמרין",
            watering_interval_days=7,
            sunlight="full_sun",
            care_en=["Water weekly.", "Full sun.", "Trim after flowering."],
            care_he=["השקו פעם בשבוע.", "שמש מלאה.", "גזמו אחרי הפריחה."],
            care_source=CareSource.CURATED,
        ),
        Plant(scientific_name="Ficus carica", name_en="Fig", name_he="תאנה"),
        Plant(scientific_name="Rosa", name_en="Rose", name_he="ורד"),
        Plant(scientific_name="Citrus × limon", name_en="Lemon", name_he="לימון"),
    ]
    session.add_all(plants)
    session.commit()
    return {p.scientific_name: p for p in plants}


@pytest.fixture
def fake_ai(client) -> Callable:
    """fake_ai(handler) routes the backend's ai-service calls to handler(request)."""
    calls: list[httpx.Request] = []

    def install(handler):
        def recording(request: httpx.Request) -> httpx.Response:
            calls.append(request)
            return handler(request)

        ai = AIClient("http://ai-service", transport=httpx.MockTransport(recording))
        app.dependency_overrides[get_ai_client] = lambda: ai
        return calls

    return install


@pytest.fixture(autouse=True)
def no_backoff(monkeypatch):
    # tenacity waits between attempts; make it instant in tests.
    monkeypatch.setattr(AIClient._post.retry, "sleep", lambda seconds: None)
