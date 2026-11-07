"""AppTest runs streamlit_app.py in-process; respx fakes every backend call."""

import json

import httpx
import pytest
import respx
from streamlit.testing.v1 import AppTest

from api import BACKEND_URL as BASE  # the URL api.py really calls
from i18n import RTL_CSS

APP = "../streamlit_app.py"  # resolved relative to THIS test file
JPEG = b"\xff\xd8\xff\xe0fake-jpeg-bytes"

ROSEMARY = {
    "id": 1,
    "scientific_name": "Salvia rosmarinus",
    "name_en": "Rosemary",
    "name_he": "רוזמרין",
    "wikidata_id": "Q102240169",
    "watering_interval_days": 7,
    "sunlight": "full_sun",
    "care_en": ["Water weekly.", "Full sun.", "Trim after flowering."],
    "care_he": ["השקו פעם בשבוע.", "שמש מלאה.", "גזמו אחרי הפריחה."],
    "care_source": "curated",
}
FIG = {
    **ROSEMARY,
    "id": 2,
    "scientific_name": "Ficus carica",
    "name_en": "Fig",
    "name_he": "תאנה",
    "watering_interval_days": None,
    "sunlight": None,
    "care_en": None,
    "care_he": None,
    "care_source": "none",
}


def garden_item(gid: int, plant: dict, days: int, **extra) -> dict:
    return {
        "id": gid,
        "plant": plant,
        "nickname": None,
        "location": None,
        "watering_interval_days": 7,
        "last_watered_at": "2026-11-01T08:00:00Z",
        "created_at": "2026-11-01T08:00:00Z",
        "next_watering_on": "2026-11-08",
        "days_until_watering": days,
        "has_photo": False,
        **extra,
    }


@pytest.fixture
def backend():
    with respx.mock(base_url=BASE, assert_all_called=False) as mock:
        yield mock


def start_app(backend, garden: list[dict], lang: str = "English") -> AppTest:
    backend.get("/garden").mock(return_value=httpx.Response(200, json=garden))
    at = AppTest.from_file(APP, default_timeout=30)
    at.session_state["lang"] = lang
    return at.run()


# --- my garden -----------------------------------------------------------------------
def test_empty_garden(backend):
    at = start_app(backend, [])
    assert not at.exception
    assert "Your garden is empty" in at.info[0].value


def test_garden_shows_days_left_in_english(backend):
    garden = [
        garden_item(5, FIG, -2, nickname="Big fig"),
        garden_item(6, ROSEMARY, 3),
    ]
    at = start_app(backend, garden)
    assert not at.exception
    assert [e.label for e in at.expander] == [
        "🔴 Big fig \\(Fig\\) — 2 days overdue",
        "🟢 Rosemary — water in 3 days",
    ]


def test_hebrew_switches_text_and_direction(backend):
    at = start_app(backend, [garden_item(6, ROSEMARY, 0)], lang="עברית")
    assert not at.exception
    assert at.title[0].value == "אליעזר — מאסטר הגינה שלך"
    assert at.expander[0].label == "💧 רוזמרין — להשקות היום"
    assert any(RTL_CSS in h.value for h in at.html)
    english = start_app(backend, [garden_item(6, ROSEMARY, 0)])
    assert not any("direction: rtl" in h.value for h in english.html)


def test_care_steps_follow_the_language(backend):
    at = start_app(backend, [garden_item(6, ROSEMARY, 3)], lang="עברית")
    text = " ".join(m.value for m in at.markdown)
    assert "השקו פעם בשבוע" in text
    assert "Water weekly" not in text


def test_water_button_restarts_the_countdown(backend):
    post = backend.post("/garden/6/water").mock(
        return_value=httpx.Response(200, json=garden_item(6, ROSEMARY, 7))
    )
    at = start_app(backend, [garden_item(6, ROSEMARY, -1)])
    at.button(key="water-6").click().run()
    assert post.called
    assert at.success[0].value == "Watered Rosemary. Next watering in 7 days."


def test_missing_care_can_be_requested_from_the_ai(backend):
    care = backend.post("/plants/2/care").mock(
        return_value=httpx.Response(200, json={**FIG, "care_source": "ai"})
    )
    at = start_app(backend, [garden_item(5, FIG, 4)])
    assert "No care instructions yet." in [c.value for c in at.caption]
    at.button(key="care-5").click().run()
    assert care.called
    assert at.success[0].value == "Care instructions for Fig are ready."


@pytest.mark.parametrize(
    ("status", "message"),
    [
        (
            503,
            "Eliezer's AI is unavailable right now. Try again in a minute, or add the plant by name.",
        ),
        (502, "Eliezer's AI gave an unusable answer. Try another photo."),
    ],
)
def test_care_errors_are_friendly(backend, status, message):
    backend.post("/plants/2/care").mock(
        return_value=httpx.Response(status, json={"detail": "x"})
    )
    at = start_app(backend, [garden_item(5, FIG, 4)])
    at.button(key="care-5").click().run()
    assert not at.exception
    assert at.error[0].value == message


def test_edit_sends_only_the_form_fields(backend):
    patch = backend.patch("/garden/6").mock(
        return_value=httpx.Response(200, json=garden_item(6, ROSEMARY, 3))
    )
    at = start_app(backend, [garden_item(6, ROSEMARY, 3)])
    at.text_input(key="nick-6").input("By the gate")
    at.number_input(key="every-6").set_value(10)
    at.button(key="save-6").click().run()
    assert json.loads(patch.calls.last.request.content) == {
        "nickname": "By the gate",
        "location": "",
        "watering_interval_days": 10,
    }


def test_validation_errors_are_shown_in_words(backend):
    detail = [
        {
            "loc": ["body", "watering_interval_days"],
            "msg": "Input should be less than or equal to 60",
        }
    ]
    backend.patch("/garden/6").mock(
        return_value=httpx.Response(422, json={"detail": detail})
    )
    at = start_app(backend, [garden_item(6, ROSEMARY, 3)])
    at.button(key="save-6").click().run()
    assert not at.exception
    assert at.error[0].value == (
        "Please fix: watering_interval_days: Input should be less than or equal to 60"
    )


def test_lost_reply_after_watering_says_outcome_unknown(backend):
    backend.post("/garden/6/water").mock(side_effect=httpx.ReadTimeout("no reply"))
    at = start_app(backend, [garden_item(6, ROSEMARY, 3)])
    at.button(key="water-6").click().run()
    assert not at.exception
    assert "may have been saved" in at.error[0].value


def test_backend_down_shows_next_step_not_traceback(backend):
    backend.get("/garden").mock(side_effect=httpx.ConnectError("refused"))
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    assert "Cannot reach the backend" in at.error[0].value
    assert len(at.tabs) == 0  # st.stop(): the rest of the page is not drawn


def test_backend_down_in_hebrew(backend):
    backend.get("/garden").mock(side_effect=httpx.ConnectError("refused"))
    at = AppTest.from_file(APP, default_timeout=30)
    at.session_state["lang"] = "עברית"
    at.run()
    assert at.error[0].value.startswith("אין חיבור לשרת")


# --- add from a photo -------------------------------------------------------------------
IDENTIFIED = {
    "is_plant": True,
    "model": "demo",
    "candidates": [
        {
            **{k: ROSEMARY[k] for k in ("scientific_name", "name_en", "name_he")},
            "confidence": 0.6,
            "plant_id": 1,
            "matched_on": "species",
        },
        {
            "scientific_name": "Monstera deliciosa",
            "name_en": "Monstera",
            "name_he": "מונסטרה",
            "confidence": 0.3,
            "plant_id": None,
            "matched_on": None,
        },
    ],
}


def identify_photo(backend, reply: httpx.Response) -> AppTest:
    backend.post("/plants/identify").mock(return_value=reply)
    at = start_app(backend, [])
    at.file_uploader(key="upload").upload("leaf.jpg", JPEG, "image/jpeg")
    return at.button(key="identify").click().run()


def test_identify_without_a_photo_warns(backend):
    at = start_app(backend, [])
    at.button(key="identify").click().run()
    assert at.warning[0].value == "Take or upload a photo first."


def test_identify_shows_candidates_and_demo_note(backend):
    at = identify_photo(backend, httpx.Response(200, json=IDENTIFIED))
    assert not at.exception
    assert at.warning[0].value.startswith("Demo mode")
    labels = at.radio(key="candidate").options
    assert labels[0].startswith("Rosemary — *Salvia rosmarinus* (60% sure)")
    assert "new to the plant database" in labels[1]


def test_adding_a_known_candidate_uploads_the_photo(backend):
    added = garden_item(9, ROSEMARY, 7)
    post = backend.post("/garden").mock(return_value=httpx.Response(201, json=added))
    put = backend.put("/garden/9/photo").mock(return_value=httpx.Response(204))
    at = identify_photo(backend, httpx.Response(200, json=IDENTIFIED))
    at.button(key="photo-add").click().run()
    assert json.loads(post.calls.last.request.content) == {
        "plant_id": 1,
        "nickname": None,
    }
    assert put.called and JPEG in put.calls.last.request.content
    assert at.success[0].value == "Added Rosemary to your garden."


def test_adding_an_unknown_candidate_creates_the_catalog_entry_first(backend):
    new_plant = {
        **FIG,
        "id": 77,
        "scientific_name": "Monstera deliciosa",
        "name_en": "Monstera",
        "name_he": "מונסטרה",
    }
    create = backend.post("/plants").mock(
        return_value=httpx.Response(201, json=new_plant)
    )
    backend.post("/garden").mock(
        return_value=httpx.Response(201, json=garden_item(10, new_plant, 7))
    )
    backend.put("/garden/10/photo").mock(return_value=httpx.Response(204))
    at = identify_photo(backend, httpx.Response(200, json=IDENTIFIED))
    at.radio(key="candidate").set_value(1)
    at.button(key="photo-add").click().run()
    assert json.loads(create.calls.last.request.content) == {
        "scientific_name": "Monstera deliciosa",
        "name_en": "Monstera",
        "name_he": "מונסטרה",
    }
    assert at.success[0].value == "Added Monstera to your garden."


def test_not_a_plant(backend):
    reply = httpx.Response(
        200, json={"is_plant": False, "model": "demo", "candidates": []}
    )
    at = identify_photo(backend, reply)
    assert at.info[-1].value == "That doesn't look like a plant. Try another photo."


def test_identify_when_ai_is_down(backend):
    at = identify_photo(
        backend, httpx.Response(503, json={"detail": "AI service unavailable"})
    )
    assert not at.exception
    assert at.error[0].value.startswith("Eliezer's AI is unavailable right now.")


# --- add by name --------------------------------------------------------------------------
def test_short_search_shows_a_hint(backend):
    at = start_app(backend, [])
    at.text_input(key="search-q").input("r").run()
    assert "Type at least 2 letters." in [c.value for c in at.caption]


def test_search_and_add(backend):
    search = backend.get("/plants").mock(
        return_value=httpx.Response(200, json=[ROSEMARY, FIG])
    )
    post = backend.post("/garden").mock(
        return_value=httpx.Response(
            201, json=garden_item(11, FIG, 7, nickname="Old fig")
        )
    )
    at = start_app(backend, [], lang="עברית")
    at.text_input(key="search-q").input("תאנה").run()
    assert search.calls.last.request.url.params["q"] == "תאנה"
    assert at.selectbox(key="search-choice").options == [
        "רוזמרין — Salvia rosmarinus",
        "תאנה — Ficus carica",
    ]
    at.selectbox(key="search-choice").set_value(2)
    at.text_input(key="search-nickname").input("Old fig")
    at.button(key="search-add").click().run()
    assert json.loads(post.calls.last.request.content) == {
        "plant_id": 2,
        "nickname": "Old fig",
    }
    assert at.success[0].value == "Old fig \\(תאנה\\) נוסף לגינה שלך."


def test_search_without_results(backend):
    backend.get("/plants").mock(return_value=httpx.Response(200, json=[]))
    at = start_app(backend, [])
    at.text_input(key="search-q").input("zzz").run()
    assert at.info[-1].value == "No plants match “zzz”."
