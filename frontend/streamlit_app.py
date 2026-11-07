"""Eliezer: your garden master. Talks only to the backend, through api.py."""

import string

import streamlit as st

import api
import i18n

st.set_page_config(page_title="Eliezer", page_icon="🌱")

# --- language ---------------------------------------------------------------------
choice = st.segmented_control(
    "Language / שפה",
    list(i18n.LANGUAGES),
    default="English",
    required=True,  # the user cannot deselect both languages
    key="lang",
    label_visibility="collapsed",
)
LANG = i18n.LANGUAGES[choice]
if LANG == "he":
    st.html(i18n.RTL_CSS)


def tr(key: str, **values) -> str:
    return i18n.t(key, LANG, **values)


def error_text(exc: api.BackendError) -> str:
    return tr(f"err_{exc.kind}", **exc.values)


# Every ASCII punctuation mark, prefixed with a backslash.
MARKDOWN_ESCAPES = str.maketrans({c: "\\" + c for c in string.punctuation})


def plain(text: str) -> str:
    """Escape Markdown so user or model text is shown, not interpreted."""
    return text.translate(MARKDOWN_ESCAPES)


def plant_name(plant: dict) -> str:
    return plant["name_he"] if LANG == "he" else plant["name_en"]


def garden_name(item: dict) -> str:
    name = plant_name(item["plant"])
    return f"{item['nickname']} ({name})" if item["nickname"] else name


def notify(message: str) -> None:
    """Remember a success message, then rerun so lists show fresh data."""
    st.session_state["notice"] = message
    st.rerun()


st.title(tr("title"))
st.caption(tr("subtitle"))

if notice := st.session_state.pop("notice", None):
    st.success(notice)

try:
    with st.spinner(tr("loading")):
        garden = api.list_garden()
except api.BackendError as exc:
    st.error(error_text(exc))
    st.stop()  # nothing else on this page works without the backend

garden_tab, photo_tab, search_tab = st.tabs(
    [tr("tab_garden"), tr("tab_photo"), tr("tab_search")]
)


# --- my garden -----------------------------------------------------------------------
def show_care(item: dict) -> None:
    plant = item["plant"]
    st.markdown(f"**{tr('care_heading')}**")
    if plant["care_source"] == "none":
        st.caption(tr("no_care"))
        if st.button(tr("get_care"), key=f"care-{item['id']}"):
            try:
                with st.spinner(tr("writing_care")):
                    api.write_care(plant["id"])
            except api.BackendError as exc:
                st.error(error_text(exc))
            else:
                notify(tr("care_ready", name=plain(plant_name(plant))))
        return
    steps = plant["care_he"] if LANG == "he" else plant["care_en"]
    st.markdown("\n".join(f"- {plain(step)}" for step in steps))
    if plant["sunlight"]:
        st.caption(tr("light", light=tr(f"sun_{plant['sunlight']}")))
    st.caption(tr("ai_note" if plant["care_source"] == "ai" else "curated_note"))


def show_garden_plant(item: dict) -> None:
    gid, days = item["id"], item["days_until_watering"]
    name = plain(garden_name(item))
    label = f"{i18n.status_icon(days)} {name} — {i18n.days_left(days, LANG)}"
    with st.expander(label):
        if item["has_photo"] and (photo := api.get_photo(gid)):
            st.image(photo, width=240)
        st.caption(
            tr(
                "schedule",
                days=item["watering_interval_days"],
                date=i18n.short_date(item["next_watering_on"]),
            )
        )
        if st.button(tr("watered_button"), key=f"water-{gid}", type="primary"):
            try:
                watered = api.water(gid)
            except api.BackendError as exc:
                st.error(error_text(exc))
            else:
                notify(tr("watered", name=name, days=watered["days_until_watering"]))
        show_care(item)
        with st.form(f"edit-{gid}"):
            st.markdown(f"**{tr('edit_heading')}**")
            changes = {
                "nickname": st.text_input(
                    tr("nickname"),
                    item["nickname"] or "",
                    max_chars=100,
                    key=f"nick-{gid}",
                ),
                "location": st.text_input(
                    tr("location"),
                    item["location"] or "",
                    max_chars=100,
                    key=f"loc-{gid}",
                ),
                "watering_interval_days": st.number_input(
                    tr("interval"),
                    1,
                    60,
                    item["watering_interval_days"],
                    key=f"every-{gid}",
                ),
            }
            if st.form_submit_button(tr("save"), key=f"save-{gid}"):
                try:
                    api.update_garden(gid, changes)
                except api.BackendError as exc:
                    st.error(error_text(exc))
                else:
                    notify(tr("saved", name=name))
        if st.button(tr("delete"), key=f"delete-{gid}"):
            try:
                api.remove_from_garden(gid)
            except api.BackendError as exc:
                st.error(error_text(exc))
            else:
                notify(tr("deleted", name=name))


with garden_tab:
    if not garden:
        st.info(tr("empty_garden"))
    for item in garden:
        show_garden_plant(item)


# --- add from a photo ------------------------------------------------------------------
def candidate_label(candidate: dict) -> str:
    """Radio labels render Markdown, and these names come from a model: escape."""
    name = plain(candidate["name_he"] if LANG == "he" else candidate["name_en"])
    scientific = plain(candidate["scientific_name"])
    pct = round(candidate["confidence"] * 100)
    label = f"{name} — *{scientific}* ({tr('sure', pct=pct)})"
    if candidate["plant_id"] is None:
        label += f" · {tr('new_plant')}"
    elif candidate["matched_on"] == "genus":
        label += f" · {tr('genus_match', name=scientific.split()[0])}"
    return label


def add_candidate(candidate: dict, photo: dict, nickname: str) -> None:
    plant_id = candidate["plant_id"]
    if plant_id is None:  # the catalog does not know it yet: add it first
        plant_id = api.create_plant(
            candidate["scientific_name"], candidate["name_en"], candidate["name_he"]
        )["id"]
    added = api.add_to_garden(plant_id, nickname)
    api.upload_photo(added["id"], photo["data"], photo["name"], photo["type"])
    st.session_state.pop("identified", None)
    notify(tr("added", name=plain(garden_name(added))))


with photo_tab:
    camera = st.camera_input(tr("camera"), key="camera")
    upload = st.file_uploader(
        tr("upload"), type=["jpg", "jpeg", "png", "webp"], key="upload"
    )
    photo_file = camera or upload
    if st.button(tr("identify"), key="identify", type="primary"):
        if photo_file is None:
            st.warning(tr("need_photo"))
        else:
            photo = {
                "data": photo_file.getvalue(),
                "name": photo_file.name,
                "type": photo_file.type,
            }
            try:
                with st.spinner(tr("identifying")):
                    result = api.identify(photo["data"], photo["name"], photo["type"])
            except api.BackendError as exc:
                st.error(error_text(exc))
            else:
                st.session_state["identified"] = {"result": result, "photo": photo}

    if identified := st.session_state.get("identified"):
        result = identified["result"]
        if not result["is_plant"]:
            st.info(tr("not_a_plant"))
        else:
            if result["model"] == "demo":
                st.warning(tr("demo_note"))
            else:
                st.caption(tr("model_note", model=result["model"]))
            index = st.radio(
                tr("which_one"),
                range(len(result["candidates"])),
                format_func=lambda i: candidate_label(result["candidates"][i]),
                key="candidate",
            )
            nickname = st.text_input(
                tr("nickname"), max_chars=100, key="photo-nickname"
            )
            if st.button(tr("add"), key="photo-add"):
                try:
                    add_candidate(
                        result["candidates"][index], identified["photo"], nickname
                    )
                except api.BackendError as exc:
                    st.error(error_text(exc))
    st.caption(tr("not_sure"))


# --- add by name -----------------------------------------------------------------------
with search_tab:
    q = st.text_input(tr("search"), max_chars=100, key="search-q")
    if len(q.strip()) < 2:
        st.caption(tr("search_hint"))
    else:
        try:
            results = api.search_plants(q.strip())
        except api.BackendError as exc:
            st.error(error_text(exc))
            results = []
        else:
            if not results:
                st.info(tr("no_results", q=q.strip()))
        if results:
            by_id = {p["id"]: p for p in results}
            plant_id = st.selectbox(
                tr("choose"),
                list(by_id),
                format_func=lambda pid: (
                    f"{plant_name(by_id[pid])} — {by_id[pid]['scientific_name']}"
                ),
                key="search-choice",
            )
            nickname = st.text_input(
                tr("nickname"), max_chars=100, key="search-nickname"
            )
            if st.button(tr("add"), key="search-add", type="primary"):
                try:
                    added = api.add_to_garden(plant_id, nickname)
                except api.BackendError as exc:
                    st.error(error_text(exc))
                else:
                    notify(tr("added", name=plain(garden_name(added))))
