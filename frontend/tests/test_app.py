"""AppTest runs streamlit_app.py in-process; respx fakes every backend call."""

import io
import json

import httpx
import pytest
import respx
from PIL import Image
from streamlit.testing.v1 import AppTest

from api import BACKEND_URL as BASE  # the URL api.py really calls
from i18n import RTL_CSS

APP = "../streamlit_app.py"  # resolved relative to THIS test file


def tiny_jpeg() -> bytes:
    """A real JPEG: st.image decodes what it shows."""
    buffer = io.BytesIO()
    Image.new("RGB", (8, 6), (46, 125, 50)).save(buffer, "JPEG")
    return buffer.getvalue()


JPEG = tiny_jpeg()

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


def open_details(at: AppTest, gid: int) -> AppTest:
    """Tap a card: its details open in a modal."""
    return at.button(key=f"open-{gid}").click().run()


def text(at: AppTest) -> str:
    return " ".join(m.value for m in at.markdown)


def cards(at: AppTest) -> list[str]:
    return [b.label for b in at.button if b.key.startswith("open-")]


# --- my garden -----------------------------------------------------------------------
def test_empty_garden(backend):
    at = start_app(backend, [])
    assert not at.exception
    assert "Your garden is empty" in text(at)
    assert cards(at) == []


def test_garden_cards_show_days_left_most_urgent_first(backend):
    garden = [
        garden_item(5, FIG, -2, nickname="Big fig", location="Back yard"),
        garden_item(6, ROSEMARY, 3),
    ]
    at = start_app(backend, garden)
    assert not at.exception
    assert cards(at) == ["Open Big fig", "Open Rosemary"]
    page = text(at)
    assert ":red-badge[:material/warning: 2 days overdue]" in page
    assert ":green-badge[:material/check_circle: water in 3 days]" in page
    assert "1 plant needs water" in page
    assert "Back yard" in " ".join(c.value for c in at.caption)


def test_card_shows_the_photo_or_a_placeholder(backend):
    photo = backend.get("/garden/6/photo").mock(
        return_value=httpx.Response(200, content=JPEG)
    )
    no_photo = backend.get("/garden/5/photo")
    garden = [garden_item(5, FIG, 4), garden_item(6, ROSEMARY, 3, has_photo=True)]
    at = start_app(backend, garden)
    assert not at.exception
    assert photo.called
    assert not no_photo.called  # has_photo is false: the placeholder needs no call


def test_a_broken_photo_does_not_break_the_page(backend):
    backend.get("/garden/6/photo").mock(return_value=httpx.Response(500))
    at = start_app(backend, [garden_item(6, ROSEMARY, 3, has_photo=True)])
    assert not at.exception
    assert not at.error
    assert cards(at) == ["Open Rosemary"]


def test_hebrew_switches_text_and_direction(backend):
    at = start_app(backend, [garden_item(6, ROSEMARY, 0)], lang="עברית")
    assert not at.exception
    assert at.title[0].value == "אליעזר"
    assert cards(at) == ["פתיחת רוזמרין"]
    assert "להשקות היום" in text(at)
    assert any(RTL_CSS in h.value for h in at.html)
    english = start_app(backend, [garden_item(6, ROSEMARY, 0)])
    assert not any("direction: rtl" in h.value for h in english.html)


def test_tapping_a_card_opens_its_details(backend):
    at = start_app(backend, [garden_item(6, ROSEMARY, 3, location="Herb bed")])
    assert "Water weekly" not in text(at)  # care lives in the modal
    open_details(at, 6)
    assert not at.exception
    assert at.session_state["open_plant"] == 6
    page = text(at)
    assert "1. Water weekly\\." in page  # numbered, with Markdown escaped
    assert "Salvia rosmarinus" in page
    assert at.button(key="water-6").label == "I watered it"


def test_care_steps_follow_the_language(backend):
    at = open_details(
        start_app(backend, [garden_item(6, ROSEMARY, 3)], lang="עברית"), 6
    )
    assert "השקו פעם בשבוע" in text(at)
    assert "Water weekly" not in text(at)


def test_water_button_restarts_the_countdown_and_closes_the_details(backend):
    post = backend.post("/garden/6/water").mock(
        return_value=httpx.Response(200, json=garden_item(6, ROSEMARY, 7))
    )
    at = open_details(start_app(backend, [garden_item(6, ROSEMARY, -1)]), 6)
    at.button(key="water-6").click().run()
    assert post.called
    assert at.toast[0].value == "Watered Rosemary. Next watering in 7 days."
    assert "open_plant" not in at.session_state


def test_missing_care_can_be_requested_from_the_ai(backend):
    care = backend.post("/plants/2/care").mock(
        return_value=httpx.Response(200, json={**FIG, "care_source": "ai"})
    )
    at = open_details(start_app(backend, [garden_item(5, FIG, 4)]), 5)
    assert "No care instructions yet." in [c.value for c in at.caption]
    at.button(key="care-5").click().run()
    assert care.called
    assert at.toast[0].value == "Care instructions for Fig are ready."
    assert at.session_state["open_plant"] == 5  # stays open to show the new care


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
    at = open_details(start_app(backend, [garden_item(5, FIG, 4)]), 5)
    at.button(key="care-5").click().run()
    assert not at.exception
    assert at.error[0].value == message


def test_edit_sends_only_the_form_fields(backend):
    patch = backend.patch("/garden/6").mock(
        return_value=httpx.Response(200, json=garden_item(6, ROSEMARY, 3))
    )
    at = open_details(start_app(backend, [garden_item(6, ROSEMARY, 3)]), 6)
    at.text_input(key="nick-6").input("By the gate")
    at.number_input(key="every-6").set_value(10)
    at.button(key="save-6").click().run()
    assert json.loads(patch.calls.last.request.content) == {
        "nickname": "By the gate",
        "location": "",
        "watering_interval_days": 10,
    }
    assert at.toast[0].value == "Saved Rosemary."


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
    at = open_details(start_app(backend, [garden_item(6, ROSEMARY, 3)]), 6)
    at.button(key="save-6").click().run()
    assert not at.exception
    assert at.error[0].value == (
        "Please fix: watering_interval_days: Input should be less than or equal to 60"
    )


def test_a_photo_can_be_added_later(backend):
    put = backend.put("/garden/6/photo").mock(return_value=httpx.Response(204))
    at = open_details(start_app(backend, [garden_item(6, ROSEMARY, 3)]), 6)
    assert at.button(key="save-photo-6").disabled  # nothing chosen yet
    at.file_uploader(key="new-photo-6-0").upload("bush.jpg", JPEG, "image/jpeg").run()
    at.button(key="save-photo-6").click().run()
    assert put.called and JPEG in put.calls.last.request.content
    assert at.toast[0].value == "Saved the photo of Rosemary."
    assert at.session_state["open_plant"] == 6


def test_remove_asks_first_then_deletes(backend):
    delete = backend.delete("/garden/6").mock(return_value=httpx.Response(204))
    at = open_details(start_app(backend, [garden_item(6, ROSEMARY, 3)]), 6)
    assert "Remove Rosemary from your garden?" in text(at)
    assert not delete.called
    at.button(key="delete-6").click().run()
    assert delete.called
    assert at.toast[0].value == "Removed Rosemary."
    assert "open_plant" not in at.session_state


def test_lost_reply_after_watering_says_outcome_unknown(backend):
    backend.post("/garden/6/water").mock(side_effect=httpx.ReadTimeout("no reply"))
    at = open_details(start_app(backend, [garden_item(6, ROSEMARY, 3)]), 6)
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
    at.file_uploader(key="upload-0").upload("leaf.jpg", JPEG, "image/jpeg")
    return at.button(key="identify").click().run()


def test_identify_without_a_photo_warns(backend):
    at = start_app(backend, [])
    at.button(key="identify").click().run()
    assert at.warning[0].value == "Take or upload a photo first."


def test_identify_shows_candidates_and_demo_note(backend):
    at = identify_photo(backend, httpx.Response(200, json=IDENTIFIED))
    assert not at.exception
    assert at.warning[0].value.startswith("Demo mode")
    candidates = at.radio(key="candidate")
    assert candidates.options == ["Rosemary", "Monstera"]
    captions = list(candidates.proto.captions)
    assert captions[0] == "*Salvia rosmarinus* · 60% sure"
    assert "new to the plant database" in captions[1]


def test_adding_a_known_candidate_uploads_the_photo_and_shows_it(backend):
    added = garden_item(9, ROSEMARY, 7, has_photo=True)
    post = backend.post("/garden").mock(return_value=httpx.Response(201, json=added))
    put = backend.put("/garden/9/photo").mock(return_value=httpx.Response(204))
    backend.get("/garden/9/photo").mock(return_value=httpx.Response(200, content=JPEG))
    at = identify_photo(backend, httpx.Response(200, json=IDENTIFIED))
    backend.get("/garden").mock(return_value=httpx.Response(200, json=[added]))
    at.button(key="photo-add").click().run()
    assert json.loads(post.calls.last.request.content) == {
        "plant_id": 1,
        "nickname": None,
    }
    assert put.called and JPEG in put.calls.last.request.content
    assert at.toast[0].value == "Added Rosemary to your garden."
    # The new plant's details open on top of My garden; the photo form is reset.
    assert at.session_state["open_plant"] == 9
    assert at.session_state["tabs-en"].endswith("My garden")
    assert at.button(key="water-9")
    assert at.file_uploader(key="upload-1").value is None


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
    assert at.toast[0].value == "Added Monstera to your garden."


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


def test_search_and_add_with_one_tap(backend):
    search = backend.get("/plants").mock(
        return_value=httpx.Response(200, json=[ROSEMARY, FIG])
    )
    post = backend.post("/garden").mock(
        return_value=httpx.Response(201, json=garden_item(11, FIG, 7))
    )
    at = start_app(backend, [garden_item(6, ROSEMARY, 3)], lang="עברית")
    at.text_input(key="search-q").input("תאנה").run()
    assert search.calls.last.request.url.params["q"] == "תאנה"
    assert [b.key for b in at.button if b.key.startswith("search-add-")] == [
        "search-add-1",
        "search-add-2",
    ]
    page = text(at)
    assert "**רוזמרין**" in page and "Ficus carica" in page
    assert page.count("כבר בגינה") == 1  # rosemary is already planted
    at.button(key="search-add-2").click().run()
    assert json.loads(post.calls.last.request.content) == {
        "plant_id": 2,
        "nickname": None,
    }
    assert at.toast[0].value == "תאנה נוסף לגינה שלך."


def test_search_without_results(backend):
    backend.get("/plants").mock(return_value=httpx.Response(200, json=[]))
    at = start_app(backend, [])
    at.text_input(key="search-q").input("zzz").run()
    assert at.info[-1].value == "No plants match “zzz”."


@pytest.mark.parametrize(
    ("url", "switch_shown"),
    [
        (None, True),  # this computer (AppTest has no URL)
        ("http://localhost:8501/", True),
        ("https://garden.example/", True),
        ("http://10.100.102.187:8501/", False),  # a phone on the Wi-Fi
    ],
)
def test_live_camera_switch_only_where_browsers_allow_it(
    backend, monkeypatch, url, switch_shown
):
    import streamlit as st

    monkeypatch.setattr(type(st.context), "url", property(lambda self: url))
    at = start_app(backend, [])
    assert not at.exception
    assert any(t.key == "use-camera" for t in at.toggle) is switch_shown
    assert at.file_uploader(key="upload-0")  # the phone's way to take a photo
