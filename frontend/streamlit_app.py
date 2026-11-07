import string

import streamlit as st

import api

st.set_page_config(page_title="eliezer")
st.title("eliezer")

# Every ASCII punctuation mark, prefixed with a backslash.
MARKDOWN_ESCAPES = str.maketrans({c: "\\" + c for c in string.punctuation})


def plain(text: str) -> str:
    """Escape Markdown so user or model text is shown, not interpreted."""
    return text.translate(MARKDOWN_ESCAPES)


def notify(message: str) -> None:
    """Remember a success message, then rerun so lists show fresh data."""
    st.session_state["notice"] = message
    st.rerun()


def item_fields(key: str, item: api.Item | None = None) -> dict:
    """Draw the item inputs (inside a form) and return them as a request body."""
    i: dict = dict(item) if item else {}
    return {
        "title": st.text_input(
            "Title",
            i.get("title", ""),
            max_chars=200,
            required=True,  # checked in the browser; easy to bypass
            key=f"{key}-title",
        ),
        "description": st.text_area(
            "Description",
            i.get("description", ""),
            max_chars=5000,
            key=f"{key}-description",
        ),
        "priority": st.number_input(
            "Priority (1 lowest, 5 most urgent)",
            1,
            5,
            i.get("priority", 3),
            key=f"{key}-priority",
        ),
        "tags": st.text_input(
            "Tags, comma-separated", i.get("tags", ""), max_chars=500, key=f"{key}-tags"
        ),
    }


if notice := st.session_state.pop("notice", None):
    st.success(notice)

try:
    with st.spinner("Loading items..."):
        items = api.list_items()
except api.BackendError as exc:
    st.error(str(exc))
    st.stop()  # nothing else on this page works without the backend

browse, add, from_text = st.tabs(
    ["Items", "Add an item", "From text (AI)"],
    key="item-tabs",
    on_change="rerun",
)

with browse:
    if not items:
        st.info("No items yet. Add one in the 'Add an item' tab.")
    for item in items:
        iid = item["id"]
        title = plain(item["title"])  # user text: show it, never interpret it
        label = f"{title} (priority {item['priority']})"
        with st.expander(label), st.form(f"edit-{iid}"):
            changes = item_fields(f"edit-{iid}", item)
            save_col, delete_col = st.columns(2)
            save = save_col.form_submit_button(
                "Save changes", key=f"save-{iid}", width="stretch"
            )
            delete = delete_col.form_submit_button(
                "Delete", key=f"delete-{iid}", width="stretch"
            )
            try:
                if save:
                    api.update_item(iid, changes)
                    notify(f"Saved {plain(changes['title'])}.")
                if delete:
                    api.delete_item(iid)
                    notify(f"Deleted {title}.")
            except api.BackendError as exc:
                st.error(str(exc))

with add, st.form("add", clear_on_submit=True):
    new_item = item_fields("add")
    submitted = st.form_submit_button("Add item", key="add-submit", width="stretch")
    # frontend check before any request
    if submitted and not new_item["title"].strip():
        st.warning("Give the item a title before saving.")
    elif submitted:
        try:
            created = api.create_item(new_item)
        except api.BackendError as exc:
            st.error(str(exc))
        else:
            notify(f"Added {plain(created['title'])}.")

with from_text, st.form("from-text"):
    text = st.text_area(
        "Describe the item in your own words",
        height=200,
        max_chars=5000,
        key="from-text-text",
    )
    if st.form_submit_button(
        "Extract with AI", key="from-text-submit", width="stretch"
    ):
        try:
            with st.spinner("Asking the AI service..."):
                created = api.create_from_text(text)
        except api.BackendError as exc:
            st.error(str(exc))
        else:
            notify(f"Added {plain(created['title'])} from your text.")
