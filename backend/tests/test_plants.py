"""The plant catalog: search, lookup, adding identified plants, AI-written care."""

import json

import httpx

from app.models import Plant

GUIDE = {
    "watering_interval_days": 10,
    "sunlight": "full_sun",
    "care_en": ["Water deeply.", "Plant in full sun.", "Prune in winter."],
    "care_he": ["השקו לעומק.", "שתלו בשמש מלאה.", "גזמו בחורף."],
}


def names(response) -> list[str]:
    return [p["scientific_name"] for p in response.json()]


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_search_by_english_hebrew_and_scientific_name(client, catalog):
    assert names(client.get("/plants", params={"q": "rosemary"})) == [
        "Salvia rosmarinus"
    ]
    assert names(client.get("/plants", params={"q": "רוזמרין"})) == [
        "Salvia rosmarinus"
    ]
    assert names(client.get("/plants", params={"q": "FICUS"})) == ["Ficus carica"]
    assert client.get("/plants", params={"q": "zzz"}).json() == []


def test_search_lists_curated_plants_first(client, catalog):
    r = client.get("/plants")
    assert r.status_code == 200
    assert names(r)[0] == "Salvia rosmarinus"  # the only plant with curated care
    assert len(r.json()) == len(catalog)


def test_search_wildcards_are_literal(client, catalog):
    assert client.get("/plants", params={"q": "%"}).json() == []
    assert client.get("/plants", params={"q": "_"}).json() == []


def test_search_limits_are_validated(client):
    assert client.get("/plants", params={"limit": 0}).status_code == 422
    assert client.get("/plants", params={"limit": 101}).status_code == 422
    assert client.get("/plants", params={"q": "x" * 101}).status_code == 422


def test_get_plant_and_404(client, catalog):
    pid = catalog["Salvia rosmarinus"].id
    body = client.get(f"/plants/{pid}").json()
    assert body["care_source"] == "curated"
    assert body["care_he"][0] == "השקו פעם בשבוע."
    r = client.get("/plants/999")
    assert r.status_code == 404
    assert r.json() == {"detail": "Plant not found"}


def test_create_plant_201_then_409(client, catalog):
    body = {
        "scientific_name": "Monstera deliciosa",
        "name_en": "Monstera",
        "name_he": "מונסטרה",
    }
    r = client.post("/plants", json=body)
    assert r.status_code == 201
    assert r.json()["care_source"] == "none"
    again = client.post(
        "/plants", json={**body, "scientific_name": "monstera DELICIOSA"}
    )
    assert again.status_code == 409


def test_create_plant_validation(client):
    good = {
        "scientific_name": "Monstera deliciosa",
        "name_en": "Monstera",
        "name_he": "מונסטרה",
    }
    for bad in (
        {**good, "name_he": "Monstera"},  # no Hebrew letters
        {**good, "scientific_name": ""},
        {**good, "name_en": "x" * 121},
        {**good, "family": "Araceae"},  # unknown field
    ):
        assert client.post("/plants", json=bad).status_code == 422, bad


def test_existing_care_is_returned_without_an_ai_call(client, catalog, fake_ai):
    calls = fake_ai(lambda request: httpx.Response(200, json=GUIDE))
    r = client.post(f"/plants/{catalog['Salvia rosmarinus'].id}/care")
    assert r.status_code == 200
    assert r.json()["watering_interval_days"] == 7  # the curated value
    assert calls == []


def test_missing_care_is_written_by_ai_validated_and_stored(client, catalog, fake_ai):
    calls = fake_ai(lambda request: httpx.Response(200, json=GUIDE))
    fig = catalog["Ficus carica"]
    r = client.post(f"/plants/{fig.id}/care")
    assert r.status_code == 200
    assert r.json()["care_source"] == "ai"
    assert r.json()["care_he"] == GUIDE["care_he"]
    [sent] = calls
    assert sent.url.path == "/care"
    assert json.loads(sent.content) == {
        "scientific_name": "Ficus carica",
        "name_en": "Fig",
        "name_he": "תאנה",
    }
    # Stored: the second request needs no AI call.
    assert client.post(f"/plants/{fig.id}/care").json() == r.json()
    assert len(calls) == 1


def test_care_with_english_in_the_hebrew_steps_is_502(
    client, session, catalog, fake_ai
):
    wrong = {**GUIDE, "care_he": ["Water deeply.", "Full sun.", "Prune."]}
    fake_ai(lambda request: httpx.Response(200, json=wrong))
    fig = catalog["Ficus carica"]
    r = client.post(f"/plants/{fig.id}/care")
    assert r.status_code == 502
    assert r.json() == {"detail": "AI service returned invalid output"}
    session.refresh(fig)
    assert fig.care_source == "none" and fig.care_he is None  # nothing stored


def test_care_when_ai_is_down_is_503_and_stores_nothing(
    client, session, catalog, fake_ai
):
    def refuse(request):
        raise httpx.ConnectError("refused", request=request)

    calls = fake_ai(refuse)
    fig = catalog["Ficus carica"]
    r = client.post(f"/plants/{fig.id}/care")
    assert r.status_code == 503
    assert r.json() == {"detail": "AI service unavailable"}
    assert len(calls) == 3  # connect errors are retried, boundedly
    session.refresh(fig)
    assert fig.care_source == "none"


def test_care_for_missing_plant_is_404(client, fake_ai):
    calls = fake_ai(lambda request: httpx.Response(200, json=GUIDE))
    assert client.post("/plants/999/care").status_code == 404
    assert calls == []


def test_plant_rows_reject_out_of_range_intervals():
    for days in (0, 61):
        try:
            Plant.model_validate(
                {
                    "scientific_name": "X y",
                    "name_en": "X",
                    "name_he": "א",
                    "watering_interval_days": days,
                }
            )
        except ValueError:
            continue
        raise AssertionError(f"{days} days was accepted")
