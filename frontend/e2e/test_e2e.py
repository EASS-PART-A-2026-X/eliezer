"""Real-browser flows through frontend -> backend -> database.

Start the stack first (docker compose up --build --wait), then from frontend/:
    uv run pytest e2e --base-url http://localhost:8501 --browser-channel chrome
Drop --browser-channel chrome if you ran `uv run playwright install chromium`.
"""

import re
import uuid

from playwright.sync_api import Page, expect


def test_add_by_name_rename_water_then_remove(page: Page):
    nickname = f"E2E {uuid.uuid4().hex[:6]}"  # unique: the database persists
    page.goto("/")
    expect(page.get_by_role("heading", name="Eliezer")).to_be_visible()

    # Add rosemary by name with one tap (frontend -> backend -> database).
    page.get_by_role("tab", name="Add by name").click()
    search = page.get_by_label("Plant name (English, Hebrew or Latin)")
    search.fill("rosemary")
    search.press("Enter")
    row = page.locator('[class*="st-key-result-"]').filter(has_text="Salvia rosmarinus")
    row.get_by_role("button", name="Add").click()

    # Its details open at once; give it a nickname there.
    details = page.get_by_role("dialog")
    expect(details.get_by_text("How to care for it")).to_be_visible()
    details.get_by_text("Edit details").click()
    details.get_by_label("Nickname (optional)").fill(nickname)
    details.get_by_role("button", name="Save changes").click()
    expect(details).to_have_count(0)

    # After a reload its card is still there, with a full countdown.
    page.reload()
    card = page.locator('[class*="st-key-card-"]').filter(has_text=nickname)
    expect(card).to_contain_text("water in 7 days")

    # Tap the card, water it, then remove it through the details.
    page.get_by_role("button", name=f"Open {nickname}").click()
    page.get_by_role("dialog").get_by_role("button", name="I watered it").click()
    expect(
        page.get_by_text(f"Watered {nickname} (Rosemary). Next watering in 7 days.")
    ).to_be_visible()
    page.get_by_role("button", name=f"Open {nickname}").click()
    details = page.get_by_role("dialog")
    details.get_by_role("button", name="Remove from my garden").click()
    page.get_by_role("button", name="Yes, remove it").click()
    expect(page.get_by_text(f"Removed {nickname} (Rosemary).")).to_be_visible()
    expect(card).to_have_count(0)


def test_hebrew_toggle_switches_language_and_direction(page: Page):
    page.goto("/")
    # The segmented control is a radio group for assistive technology.
    page.get_by_role("radio", name="עברית").click()
    expect(page.get_by_role("heading", name="אליעזר")).to_be_visible()
    expect(page.get_by_role("tab", name="הגינה שלי")).to_be_visible()
    expect(page.locator(".stApp")).to_have_css("direction", "rtl")
    page.get_by_role("radio", name="English").click()
    expect(page.get_by_role("heading", name="Eliezer")).to_be_visible()
    expect(page.locator(".stApp")).to_have_css("direction", re.compile("ltr"))


def test_garden_is_usable_on_a_phone(page: Page):
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto("/")
    expect(page.locator('[class*="st-key-card-"]').first).to_be_visible()
    # Two cards per row (the page styles arrive just after the first paint).
    page.wait_for_function(
        "getComputedStyle(document.querySelector('.st-key-garden-grid'))"
        ".gridTemplateColumns.split(' ').length === 2"
    )
    overflow = page.evaluate(
        "document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )
    assert overflow == 0  # nothing sticks out sideways
