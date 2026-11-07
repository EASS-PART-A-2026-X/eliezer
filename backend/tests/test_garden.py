"""My garden: adding plants, the watering countdown, editing and removing."""

from datetime import UTC, datetime

from fastapi import status


def add(client, plant, **extra):
    r = client.post("/garden", json={"plant_id": plant.id, **extra})
    assert r.status_code == 201, r.text
    return r.json()


def test_each_test_starts_with_an_empty_garden(client):
    assert client.get("/garden").json() == []


def test_add_uses_the_catalog_interval_and_starts_just_watered(client, catalog):
    body = add(client, catalog["Salvia rosmarinus"], nickname="By the gate")
    assert body["id"] >= 1
    assert body["nickname"] == "By the gate"
    assert body["watering_interval_days"] == 7  # from the catalog
    assert body["days_until_watering"] == 7
    assert body["next_watering_on"] == "2026-11-14"
    assert body["has_photo"] is False
    assert body["plant"]["name_he"] == "רוזמרין"
    assert client.get(f"/garden/{body['id']}").json() == body  # really stored


def test_interval_defaults_to_7_when_the_catalog_has_none(client, catalog):
    assert add(client, catalog["Ficus carica"])["watering_interval_days"] == 7


def test_interval_can_be_chosen(client, catalog):
    assert (
        add(client, catalog["Ficus carica"], watering_interval_days=12)[
            "days_until_watering"
        ]
        == 12
    )


def test_add_validation(client, catalog):
    pid = catalog["Rosa"].id
    for bad in (
        {"plant_id": pid, "watering_interval_days": 0},
        {"plant_id": pid, "watering_interval_days": 61},
        {"plant_id": pid, "nickname": "x" * 101},
        {"plant_id": pid, "colour": "red"},  # unknown field
        {"nickname": "no plant"},
    ):
        assert client.post("/garden", json=bad).status_code == 422, bad
    r = client.post("/garden", json={"plant_id": 999})
    assert r.status_code == 404
    assert r.json() == {"detail": "Plant not found"}


def test_countdown_follows_the_calendar_and_goes_negative(
    client, catalog, frozen_clock
):
    gid = add(client, catalog["Salvia rosmarinus"])["id"]
    frozen_clock.advance(days=3)
    assert client.get(f"/garden/{gid}").json()["days_until_watering"] == 4
    frozen_clock.advance(days=4)
    assert client.get(f"/garden/{gid}").json()["days_until_watering"] == 0  # today
    frozen_clock.advance(days=2)
    assert client.get(f"/garden/{gid}").json()["days_until_watering"] == -2  # overdue


def test_days_use_israel_dates_not_utc(client, catalog, frozen_clock):
    # 22:30 UTC is already the next day in Israel (UTC+2 in November).
    frozen_clock.current = datetime(2026, 11, 7, 22, 30, tzinfo=UTC)
    body = add(client, catalog["Salvia rosmarinus"])
    assert body["next_watering_on"] == "2026-11-15"


def test_watering_restarts_the_countdown(client, catalog, frozen_clock):
    gid = add(client, catalog["Salvia rosmarinus"])["id"]
    frozen_clock.advance(days=9)
    assert client.get(f"/garden/{gid}").json()["days_until_watering"] == -2
    r = client.post(f"/garden/{gid}/water")
    assert r.status_code == 200
    assert r.json()["days_until_watering"] == 7
    assert r.json()["last_watered_at"].startswith("2026-11-16T08:00:00")
    assert client.get(f"/garden/{gid}").json()["days_until_watering"] == 7  # stored


def test_list_is_sorted_by_days_left(client, catalog, frozen_clock):
    rosemary = add(client, catalog["Salvia rosmarinus"])["id"]  # every 7 days
    fig = add(client, catalog["Ficus carica"], watering_interval_days=2)["id"]
    rose = add(client, catalog["Rosa"], watering_interval_days=30)["id"]
    frozen_clock.advance(days=3)
    garden = client.get("/garden").json()
    assert [p["id"] for p in garden] == [fig, rosemary, rose]
    assert [p["days_until_watering"] for p in garden] == [-1, 4, 27]
    page = client.get("/garden", params={"offset": 1, "limit": 1}).json()
    assert [p["id"] for p in page] == [rosemary]
    assert client.get("/garden", params={"limit": 101}).status_code == 422


def test_patch_changes_only_sent_fields(client, catalog):
    gid = add(client, catalog["Rosa"], nickname="Red rose", location="Front")["id"]
    r = client.patch(f"/garden/{gid}", json={"watering_interval_days": 4})
    assert r.status_code == 200
    assert (r.json()["nickname"], r.json()["watering_interval_days"]) == ("Red rose", 4)
    assert r.json()["days_until_watering"] == 4
    # null interval means "leave unchanged"; empty text clears it
    r = client.patch(
        f"/garden/{gid}", json={"watering_interval_days": None, "nickname": ""}
    )
    assert (r.json()["nickname"], r.json()["watering_interval_days"]) == (None, 4)
    assert r.json()["location"] == "Front"
    assert (
        client.patch(f"/garden/{gid}", json={"watering_interval_days": 0}).status_code
        == 422
    )
    assert client.patch(f"/garden/{gid}", json={"plant_id": 2}).status_code == 422


def test_missing_garden_plant_is_404(client):
    for method, path in (
        ("GET", "/garden/999"),
        ("PATCH", "/garden/999"),
        ("DELETE", "/garden/999"),
        ("POST", "/garden/999/water"),
        ("GET", "/garden/999/photo"),
    ):
        body = {} if method == "PATCH" else None
        r = client.request(method, path, json=body)
        assert r.status_code == 404, (method, path)


def test_delete_then_404(client, catalog):
    gid = add(client, catalog["Rosa"])["id"]
    r = client.delete(f"/garden/{gid}")
    assert r.status_code == status.HTTP_204_NO_CONTENT
    assert r.content == b""
    assert client.get(f"/garden/{gid}").status_code == 404
    assert client.delete(f"/garden/{gid}").status_code == 404
