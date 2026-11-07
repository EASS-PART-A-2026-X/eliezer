"""AppTest runs streamlit_app.py in-process; respx fakes every backend call."""

import json

import httpx
import pytest
import respx
from streamlit.testing.v1 import AppTest

from api import BACKEND_URL as BASE  # the URL api.py really calls

APP = "../streamlit_app.py"  # resolved relative to THIS test file
TEXT = "URGENT: send the quarterly report to the client"
AI_ERRORS = {
    503: "AI service is unavailable, try again in a minute.",
    502: "AI returned something unusable. Try rewording the text.",
}


@pytest.fixture
def backend():
    with respx.mock(base_url=BASE, assert_all_called=False) as mock:
        yield mock


def start_app(backend, items: list[dict]) -> AppTest:
    backend.get("/items").mock(return_value=httpx.Response(200, json=items))
    # 30 s instead of the 3 s default: a cold first run can be slow.
    return AppTest.from_file(APP, default_timeout=30).run()


def open_from_text_tab(backend) -> AppTest:
    at = start_app(backend, [])
    at.session_state["item-tabs"] = "From text (AI)"
    return at.run()


def test_empty_state(backend):
    at = start_app(backend, [])
    assert not at.exception
    assert "No items yet" in at.info[0].value


def test_list_shows_items(backend):
    item = {"id": 1, "title": "Plan", "description": "", "priority": 4, "tags": ""}
    at = start_app(backend, [item])
    assert not at.exception
    assert [e.label for e in at.expander] == ["Plan (priority 4)"]


def test_backend_down_shows_next_step_not_traceback(backend):
    backend.get("/items").mock(side_effect=httpx.ConnectError("refused"))
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    assert "Cannot reach the backend" in at.error[0].value
    assert "reload the page" in at.error[0].value
    assert len(at.tabs) == 0  # st.stop(): the rest of the page is not drawn


def test_validation_errors_are_shown_in_words(backend):
    msg = "String should have at least 1 character"
    detail = [{"loc": ["body", "title"], "msg": msg}]
    backend.post("/items").mock(
        return_value=httpx.Response(422, json={"detail": detail})
    )
    at = start_app(backend, [])
    at.text_input(key="add-title").input("Plan")  # passes the frontend title check
    at.button(key="add-submit").click().run()
    assert not at.exception
    assert at.error[0].value == f"Please fix: title: {msg}"


def test_lost_reply_after_a_write_says_outcome_unknown(backend):
    backend.post("/items").mock(side_effect=httpx.ReadTimeout("no reply"))
    at = start_app(backend, [])
    at.text_input(key="add-title").input("Plan")
    at.button(key="add-submit").click().run()
    assert not at.exception
    assert "may have been saved" in at.error[0].value  # not "cannot reach"


def test_add_sends_exact_json(backend):
    body = {"title": "Plan", "description": "", "priority": 3, "tags": ""}
    post = backend.post("/items").mock(
        return_value=httpx.Response(201, json={"id": 4, **body})
    )
    at = start_app(backend, [])
    at.text_input(key="add-title").input("Plan")
    at.button(key="add-submit").click().run()
    assert json.loads(post.calls.last.request.content) == body
    assert at.success[0].value == "Added Plan."


def test_from_text_success(backend):
    saved = {
        "id": 4,
        "title": "Send the report",
        "description": "",
        "priority": 5,
        "tags": "work",
    }
    post = backend.post("/items/from-text").mock(
        return_value=httpx.Response(201, json=saved)
    )
    at = open_from_text_tab(backend)
    at.text_area(key="from-text-text").input(TEXT)
    at.button(key="from-text-submit").click().run()
    assert json.loads(post.calls.last.request.content) == {"text": TEXT}
    assert at.success[0].value == "Added Send the report from your text."


@pytest.mark.parametrize("status", [503, 502])
def test_from_text_shows_ai_errors_and_keeps_the_draft(backend, status):
    reply = httpx.Response(status, json={"detail": "fixed text from the backend"})
    backend.post("/items/from-text").mock(return_value=reply)
    at = open_from_text_tab(backend)
    at.text_area(key="from-text-text").input(TEXT)
    at.button(key="from-text-submit").click().run()
    assert not at.exception
    assert at.error[0].value == AI_ERRORS[status]
    assert at.session_state["item-tabs"] == "From text (AI)"
    assert at.text_area(key="from-text-text").value == TEXT
