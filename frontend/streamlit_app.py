"""Eliezer: your garden master. Talks only to the backend, through api.py."""

import string

import streamlit as st

import api
import i18n
import style

st.set_page_config(page_title="Eliezer", page_icon="🌱", layout="centered")
st.html(style.APP_CSS)

# Read the language before the toggle is drawn, so the header can use it.
LANG = i18n.LANGUAGES[st.session_state.get("lang", "English")]
if LANG == "he":
    st.html(i18n.RTL_CSS)

PHOTO_TYPES = ["jpg", "jpeg", "png", "webp"]


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


def short_name(item: dict) -> str:
    """What a card is called: the nickname if there is one."""
    return item["nickname"] or plant_name(item["plant"])


def garden_name(item: dict) -> str:
    """The full name used in messages: 'Rosemary bush (Rosemary)'."""
    name = plant_name(item["plant"])
    return f"{item['nickname']} ({name})" if item["nickname"] else name


def notify(message: str, *, keep_open: bool = False) -> None:
    """Remember a message, then rerun so every list shows fresh data."""
    st.session_state["notice"] = message
    if not keep_open:
        close_plant()
    st.rerun()


def open_plant(garden_id: int) -> None:
    st.session_state["open_plant"] = garden_id


def close_plant() -> None:
    st.session_state.pop("open_plant", None)


def plant_added(added: dict) -> None:
    """Show the new plant: its details on top of My garden."""
    st.session_state["open_plant"] = added["id"]
    st.session_state["show_garden"] = True
    notify(tr("added", name=plain(garden_name(added))), keep_open=True)


def photo_of(item: dict) -> bytes | str:
    if item["has_photo"]:
        try:
            if photo := api.get_photo(item["id"]):
                return photo
        except api.BackendError:
            pass  # a missing thumbnail must not break the page
    return style.PLACEHOLDER_SVG


def status_badge(days: int) -> None:
    if days < 0:
        color, icon = "red", ":material/warning:"
    elif days <= 1:
        color, icon = "orange", ":material/water_drop:"
    else:
        color, icon = "green", ":material/check_circle:"
    st.badge(i18n.days_left(days, LANG), icon=icon, color=color)


# --- header ----------------------------------------------------------------------------
with st.container(horizontal=True, vertical_alignment="center", key="header"):
    st.image(style.LOGO_SVG, width=52)
    with st.container(gap="xxsmall", key="brand"):
        st.title(tr("title"), anchor=False)
        st.caption(tr("subtitle"))
    st.segmented_control(
        "Language / שפה",
        list(i18n.LANGUAGES),
        default="English",
        required=True,  # the user cannot deselect both languages
        key="lang",
        label_visibility="collapsed",
    )

if notice := st.session_state.pop("notice", None):
    # Streamlit drops a toast that lands in the same slot as one still on screen.
    # Toasts share slots with style-only st.html calls, so empty styles shift each
    # message to a new slot: back-to-back messages (watered, removed) both show.
    shown = st.session_state.get("notices_shown", 0) + 1
    st.session_state["notices_shown"] = shown
    for _ in range(shown % 3):
        st.html("<style></style>")
    st.toast(notice, icon=":material/check_circle:")

try:
    with st.spinner(tr("loading")):
        garden = api.list_garden()
except api.BackendError as exc:
    st.error(error_text(exc))
    st.stop()  # nothing else on this page works without the backend

TABS = [
    f":material/potted_plant: {tr('tab_garden')}",
    f":material/photo_camera: {tr('tab_photo')}",
    f":material/search: {tr('tab_search')}",
]
TABS_KEY = f"tabs-{LANG}"  # the labels differ per language
if st.session_state.pop("show_garden", False):
    st.session_state[TABS_KEY] = TABS[0]
garden_tab, photo_tab, search_tab = st.tabs(TABS, key=TABS_KEY, on_change="rerun")


# --- my garden: one card per plant ------------------------------------------------------
def garden_card(item: dict) -> None:
    gid = item["id"]
    with st.container(border=True, gap="xsmall", key=f"card-{gid}"):
        st.image(photo_of(item), width="stretch")
        st.markdown(f"**{plain(short_name(item))}**")
        details = [
            plain(plant_name(item["plant"]))
            if item["nickname"]
            else f"*{plain(item['plant']['scientific_name'])}*"
        ]
        if item["location"]:
            details.append(f":material/location_on: {plain(item['location'])}")
        st.caption(" · ".join(details))
        status_badge(item["days_until_watering"])
        # Stretched over the whole card by CSS: tapping anywhere opens the details.
        st.button(
            tr("open", name=plain(short_name(item))),
            key=f"open-{gid}",
            on_click=open_plant,
            args=(gid,),
        )


with garden_tab:
    if not garden:
        with st.container(
            border=True, horizontal_alignment="center", key="empty-garden"
        ):
            st.image(style.PLACEHOLDER_SVG, width=200)
            st.markdown(f"**{tr('empty_title')}**", text_alignment="center")
            st.markdown(tr("empty_garden"), text_alignment="center")
    else:
        thirsty = sum(1 for item in garden if item["days_until_watering"] <= 0)
        with st.container(horizontal=True, key="summary"):
            st.badge(
                i18n.count(len(garden), "plants", LANG),
                icon=":material/potted_plant:",
                color="gray",
            )
            if thirsty:
                st.badge(
                    i18n.count(thirsty, "thirsty", LANG),
                    icon=":material/water_drop:",
                    color="orange",
                )
            else:
                st.badge(tr("all_watered"), icon=":material/check:", color="green")
        with st.container(key="garden-grid"):
            for item in garden:
                garden_card(item)


# --- plant details (a modal) ------------------------------------------------------------
def show_care(item: dict) -> None:
    plant = item["plant"]
    st.subheader(tr("care_heading"), anchor=False)
    if plant["care_source"] == "none":
        st.caption(tr("no_care"))
        if st.button(
            tr("get_care"), key=f"care-{item['id']}", icon=":material/auto_awesome:"
        ):
            try:
                with st.spinner(tr("writing_care")):
                    api.write_care(plant["id"])
            except api.BackendError as exc:
                st.error(error_text(exc))
            else:
                notify(tr("care_ready", name=plain(plant_name(plant))), keep_open=True)
        return
    if plant["sunlight"]:
        st.badge(
            tr("light", light=tr(f"sun_{plant['sunlight']}")),
            icon=":material/wb_sunny:",
            color="orange",
        )
    steps = plant["care_he"] if LANG == "he" else plant["care_en"]
    st.markdown("\n".join(f"{n}. {plain(step)}" for n, step in enumerate(steps, 1)))
    st.caption(tr("ai_note" if plant["care_source"] == "ai" else "curated_note"))


def change_photo(item: dict) -> None:
    gid = item["id"]
    label = tr("photo_change" if item["has_photo"] else "photo_add")
    with st.expander(label, icon=":material/add_a_photo:"):
        version = st.session_state.get("photo_version", 0)  # new key = empty widget
        new = st.file_uploader(
            tr("photo_pick"), type=PHOTO_TYPES, key=f"new-photo-{gid}-{version}"
        )
        if st.button(tr("photo_save"), key=f"save-photo-{gid}", disabled=new is None):
            try:
                api.upload_photo(gid, new.getvalue(), new.name, new.type)
            except api.BackendError as exc:
                st.error(error_text(exc))
            else:
                st.session_state["photo_version"] = version + 1
                notify(tr("photo_saved", name=plain(garden_name(item))), keep_open=True)


def edit_details(item: dict) -> None:
    gid, name = item["id"], plain(garden_name(item))
    with (
        st.expander(tr("edit_heading"), icon=":material/edit:"),
        st.form(f"edit-{gid}", border=False),
    ):
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
        if st.form_submit_button(tr("save"), key=f"save-{gid}", type="primary"):
            try:
                api.update_garden(gid, changes)
            except api.BackendError as exc:
                st.error(error_text(exc))
            else:
                notify(tr("saved", name=name))


def remove_plant(item: dict) -> None:
    gid, name = item["id"], plain(garden_name(item))
    with st.popover(
        tr("delete"), icon=":material/delete:", type="tertiary", key=f"remove-{gid}"
    ):
        st.markdown(tr("delete_confirm", name=name))
        if st.button(tr("delete_yes"), key=f"delete-{gid}", type="primary"):
            try:
                api.remove_from_garden(gid)
            except api.BackendError as exc:
                st.error(error_text(exc))
            else:
                notify(tr("deleted", name=name))


def plant_details(item: dict) -> None:
    gid, plant = item["id"], item["plant"]
    name = plain(garden_name(item))
    with st.container(key="dlg-photo"):
        st.image(photo_of(item), width="stretch")
    change_photo(item)

    about = [plain(plant_name(plant))] if item["nickname"] else []
    about.append(f"*{plain(plant['scientific_name'])}*")
    if item["location"]:
        about.append(f":material/location_on: {plain(item['location'])}")
    st.markdown(" · ".join(about))

    with st.container(border=True, key="dlg-watering"):
        status_badge(item["days_until_watering"])
        st.caption(
            tr(
                "schedule",
                days=item["watering_interval_days"],
                date=i18n.short_date(item["next_watering_on"]),
            )
        )
        if st.button(
            tr("watered_button"),
            key=f"water-{gid}",
            icon=":material/water_drop:",
            width="stretch",
        ):
            try:
                watered = api.water(gid)
            except api.BackendError as exc:
                st.error(error_text(exc))
            else:
                notify(tr("watered", name=name, days=watered["days_until_watering"]))

    show_care(item)
    edit_details(item)
    remove_plant(item)


if (open_id := st.session_state.get("open_plant")) is not None:
    item = next((g for g in garden if g["id"] == open_id), None)
    if item is None:
        close_plant()  # removed meanwhile
    else:
        as_dialog = st.dialog(
            plain(short_name(item)), width="medium", on_dismiss=close_plant
        )
        as_dialog(plant_details)(item)


# --- add from a photo --------------------------------------------------------------------
def candidate_caption(candidate: dict) -> str:
    """Captions render Markdown, and these names come from a model: escape."""
    scientific = plain(candidate["scientific_name"])
    parts = [f"*{scientific}*", tr("sure", pct=round(candidate["confidence"] * 100))]
    if candidate["plant_id"] is None:
        parts.append(tr("new_plant"))
    elif candidate["matched_on"] == "genus":
        parts.append(tr("genus_match", name=scientific.split()[0]))
    return " · ".join(parts)


def candidate_name(candidate: dict) -> str:
    return plain(candidate["name_he"] if LANG == "he" else candidate["name_en"])


def add_candidate(candidate: dict, photo: dict) -> None:
    plant_id = candidate["plant_id"]
    if plant_id is None:  # the catalog does not know it yet: add it first
        plant_id = api.create_plant(
            candidate["scientific_name"], candidate["name_en"], candidate["name_he"]
        )["id"]
    added = api.add_to_garden(plant_id)
    api.upload_photo(added["id"], photo["data"], photo["name"], photo["type"])
    st.session_state.pop("identified", None)
    st.session_state["upload_version"] = st.session_state.get("upload_version", 0) + 1
    plant_added(added)


with photo_tab:
    st.caption(tr("photo_intro"))
    version = st.session_state.get("upload_version", 0)  # new key = empty widgets
    camera = None
    if st.toggle(tr("use_camera"), key="use-camera"):
        camera = st.camera_input(tr("camera"), key=f"camera-{version}")
    upload = st.file_uploader(tr("upload"), type=PHOTO_TYPES, key=f"upload-{version}")
    photo_file = camera or upload
    if st.button(
        tr("identify"),
        key="identify",
        type="primary",
        icon=":material/auto_awesome:",
        width="stretch",
    ):
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
            st.info(tr("not_a_plant"), icon=":material/help:")
        else:
            if result["model"] == "demo":
                st.warning(tr("demo_note"))
            else:
                st.caption(tr("model_note", model=result["model"]))
            candidates = result["candidates"]
            with st.container(border=True, key="candidates"):
                picture, choices = st.columns([1, 2], vertical_alignment="center")
                picture.image(identified["photo"]["data"], width="stretch")
                with choices:
                    index = st.radio(
                        tr("which_one"),
                        range(len(candidates)),
                        format_func=lambda i: candidate_name(candidates[i]),
                        captions=[candidate_caption(c) for c in candidates],
                        key="candidate",
                    )
                if st.button(
                    tr("add"),
                    key="photo-add",
                    type="primary",
                    icon=":material/add:",
                    width="stretch",
                ):
                    try:
                        add_candidate(candidates[index], identified["photo"])
                    except api.BackendError as exc:
                        st.error(error_text(exc))
    st.caption(tr("not_sure"))


# --- add by name ---------------------------------------------------------------------------
def search_result(plant: dict, in_garden: bool) -> bool:
    """One row per catalog plant; returns True when its Add button is pressed."""
    pid = plant["id"]
    with st.container(
        border=True,
        horizontal=True,
        vertical_alignment="center",
        wrap=False,  # the Add button stays on the right, also on phones
        key=f"result-{pid}",
    ):
        with st.container(gap="xsmall"):
            st.markdown(
                f"**{plain(plant_name(plant))}**  \n"
                f":gray[*{plain(plant['scientific_name'])}*]"
            )
            if plant["care_source"] != "none" or in_garden:
                with st.container(horizontal=True, gap="xsmall"):
                    if plant["care_source"] != "none":
                        st.badge(
                            tr("has_care"), icon=":material/menu_book:", color="green"
                        )
                    if in_garden:
                        st.badge(
                            tr("in_garden"),
                            icon=":material/potted_plant:",
                            color="gray",
                        )
        return st.button(
            tr("add_short"), key=f"search-add-{pid}", icon=":material/add:"
        )


with search_tab:
    q = st.text_input(
        tr("search"),
        max_chars=100,
        key="search-q",
        placeholder=tr("search_placeholder"),
        icon=":material/search:",
    )
    term = q.strip()
    if len(term) < 2:
        st.caption(tr("search_hint"))
    else:
        try:
            results = api.search_plants(term)
        except api.BackendError as exc:
            st.error(error_text(exc))
            results = []
        else:
            if not results:
                st.info(tr("no_results", q=term))
        in_garden = {item["plant"]["id"] for item in garden}
        chosen = None
        for plant in results:
            if search_result(plant, plant["id"] in in_garden):
                chosen = plant["id"]
        if chosen is not None:
            try:
                added = api.add_to_garden(chosen)
            except api.BackendError as exc:
                st.error(error_text(exc))
            else:
                plant_added(added)
