"""One real-browser flow through frontend -> backend -> database.

Start the stack first (docker compose up --build --wait), then from frontend/:
    uv run pytest e2e --base-url http://localhost:8501 --browser-channel chrome
Drop --browser-channel chrome if you ran `uv run playwright install chromium`.
"""

import uuid

from playwright.sync_api import Page, expect


def test_add_then_delete_an_item(page: Page):
    title = f"E2E item {uuid.uuid4().hex[:6]}"  # unique: the database persists
    page.goto("/")
    expect(page.get_by_role("heading", name="eliezer")).to_be_visible()

    # Add an item with the form (frontend -> backend -> database).
    page.get_by_role("tab", name="Add an item").click()
    add = page.get_by_role("tabpanel", name="Add an item")  # each edit form
    add.get_by_label("Title").fill(title)  # has a "Title" field too
    add.get_by_label("Priority").fill("4")
    add.get_by_role("button", name="Add item").click()
    expect(page.get_by_text(f"Added {title}.")).to_be_visible()

    # After a reload it is still listed: the backend stored it.
    page.reload()
    label = f"{title} (priority 4)"
    items = page.get_by_role("tabpanel", name="Items")
    expect(items.get_by_text(label)).to_be_visible()

    # Clean up through the UI, which also tests delete in a real browser.
    row = items.get_by_role("group").filter(has_text=label)  # its expander
    row.get_by_text(label).click()  # open it
    row.get_by_role("button", name="Delete").click()
    expect(page.get_by_text(f"Deleted {title}.")).to_be_visible()
    expect(items.get_by_text(label)).to_have_count(0)
