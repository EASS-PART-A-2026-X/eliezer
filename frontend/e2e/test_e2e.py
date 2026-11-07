"""Real-browser flows through frontend -> backend -> database.

Start the stack first (docker compose up --build --wait), then from frontend/:
    uv run pytest e2e --base-url http://localhost:8501 --browser-channel chrome
Drop --browser-channel chrome if you ran `uv run playwright install chromium`.
"""

import re
import uuid

from playwright.sync_api import Page, expect


def test_add_by_name_water_then_remove(page: Page):
    nickname = f"E2E {uuid.uuid4().hex[:6]}"  # unique: the database persists
    page.goto("/")
    expect(
        page.get_by_role("heading", name="Eliezer — your garden master")
    ).to_be_visible()

    # Add rosemary by name (frontend -> backend -> database).
    page.get_by_role("tab", name="Add by name").click()
    search = page.get_by_role("tabpanel", name="Add by name")
    search.get_by_label("Plant name (English, Hebrew or Latin)").fill("rosemary")
    search.get_by_label("Plant name (English, Hebrew or Latin)").press("Enter")
    choice = search.get_by_role("combobox", name="Choose a plant")
    expect(choice).to_have_value("Rosemary — Salvia rosmarinus")
    search.get_by_label("Nickname (optional)").fill(nickname)
    search.get_by_label("Nickname (optional)").press("Enter")
    search.get_by_role("button", name="Add to my garden").click()
    expect(
        page.get_by_text(f"Added {nickname} (Rosemary) to your garden.")
    ).to_be_visible()

    # After a reload it is still listed, with a full countdown: the backend stored it.
    page.reload()
    label = f"{nickname} (Rosemary) — water in 7 days"
    garden = page.get_by_role("tabpanel", name="My garden")
    expect(garden.get_by_text(label)).to_be_visible()

    # Water it, then remove it through the UI.
    row = garden.get_by_role("group").filter(has_text=label)  # its expander
    row.get_by_text(label).click()
    row.get_by_role("button", name="I watered it").click()
    expect(
        page.get_by_text(f"Watered {nickname} (Rosemary). Next watering in 7 days.")
    ).to_be_visible()
    row = garden.get_by_role("group").filter(has_text=nickname)
    row.get_by_text(nickname).first.click()
    row.get_by_role("button", name="Remove from my garden").click()
    expect(page.get_by_text(f"Removed {nickname} (Rosemary).")).to_be_visible()
    expect(garden.get_by_text(label)).to_have_count(0)


def test_hebrew_toggle_switches_language_and_direction(page: Page):
    page.goto("/")
    # The segmented control is a radio group for assistive technology.
    page.get_by_role("radio", name="עברית").click()
    expect(page.get_by_role("heading", name="אליעזר — מאסטר הגינה שלך")).to_be_visible()
    expect(page.get_by_role("tab", name="הגינה שלי")).to_be_visible()
    expect(page.locator(".stApp")).to_have_css("direction", "rtl")
    page.get_by_role("radio", name="English").click()
    expect(
        page.get_by_role("heading", name="Eliezer — your garden master")
    ).to_be_visible()
    expect(page.locator(".stApp")).to_have_css("direction", re.compile("ltr"))
