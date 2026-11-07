# Testing strategy: split each input into partitions and test at least one value
# from each, especially both sides of every limit. A test counts only if it fails
# when the rule it protects is broken.
#   title: missing | "" | whitespace only | 1-200 chars | 201 chars
#   priority: 0 | 1-5 | 6          description: <=5000 | 5001
#   fields: only known ones | an unknown one ("owner")
#   item id: exists | missing (GET, PATCH, DELETE)
from fastapi import status

TASK = {"title": "Plan sprint", "priority": 4}


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_create_returns_201_with_defaults(client):
    r = client.post("/items", json={"title": "Plan sprint"})
    assert r.status_code == status.HTTP_201_CREATED
    body = r.json()
    assert body["id"] >= 1
    assert body["title"] == "Plan sprint"
    assert body["priority"] == 3  # default
    assert body["description"] == body["tags"] == ""


def test_get_returns_what_was_created(client):
    created = client.post("/items", json=TASK).json()
    r = client.get(f"/items/{created['id']}")
    assert r.status_code == 200
    assert r.json() == created


def test_list_is_ordered_and_paginated(client):
    for n in range(3):
        client.post("/items", json={"title": f"I{n}"})
    assert [i["title"] for i in client.get("/items").json()] == ["I0", "I1", "I2"]
    page = client.get("/items", params={"offset": 1, "limit": 1}).json()
    assert [i["title"] for i in page] == ["I1"]
    assert client.get("/items", params={"limit": 101}).status_code == 422
    assert client.get("/items", params={"limit": 0}).status_code == 422


def test_unknown_field_is_rejected(client):
    r = client.post("/items", json={**TASK, "owner": "me"})
    assert r.status_code == 422
    assert r.json()["detail"][0]["type"] == "extra_forbidden"


def test_invalid_bodies_are_422(client):
    bad_bodies = [
        {"title": ""},  # too short
        {"title": "   "},  # whitespace is stripped first
        {"title": "x" * 201},  # one over the limit
        {"title": "x", "priority": 0},  # priority >= 1
        {"title": "x", "priority": 6},  # priority <= 5
        {"title": "x", "description": "d" * 5001},  # description <= 5000
        {"priority": 3},  # title missing
    ]
    for body in bad_bodies:
        r = client.post("/items", json=body)
        assert r.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT, body


def test_limits_are_inclusive(client):
    for body in (
        {"title": "x" * 200, "priority": 1},
        {"title": "x", "priority": 5, "description": "d" * 5000},
    ):
        assert client.post("/items", json=body).status_code == 201, body


def test_patch_changes_only_sent_fields(client):
    iid = client.post("/items", json=TASK).json()["id"]
    r = client.patch(f"/items/{iid}", json={"priority": 5})
    assert r.status_code == 200
    assert (r.json()["title"], r.json()["priority"]) == ("Plan sprint", 5)
    # null means "leave unchanged"
    r = client.patch(f"/items/{iid}", json={"title": None})
    assert r.status_code == 200
    assert r.json()["title"] == "Plan sprint"
    assert client.patch(f"/items/{iid}", json={"priority": 0}).status_code == 422


def test_missing_item_is_404(client):
    for method in ("GET", "PATCH", "DELETE"):
        body = {} if method == "PATCH" else None  # PATCH must pass validation first
        r = client.request(method, "/items/999", json=body)
        assert r.status_code == 404, method
        assert r.json() == {"detail": "Item not found"}


def test_delete_then_404(client):
    iid = client.post("/items", json=TASK).json()["id"]
    r = client.delete(f"/items/{iid}")
    assert r.status_code == status.HTTP_204_NO_CONTENT
    assert r.content == b""
    assert client.get(f"/items/{iid}").status_code == 404
    assert client.delete(f"/items/{iid}").status_code == 404


def test_each_test_starts_empty(client):
    assert client.get("/items").json() == []
