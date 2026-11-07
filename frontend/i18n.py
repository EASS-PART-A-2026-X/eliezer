"""Every user-facing sentence, in English and Hebrew. tests/test_i18n.py checks
that both languages have exactly the same keys and placeholders."""

from datetime import date

LANGUAGES = {"English": "en", "עברית": "he"}

STRINGS: dict[str, dict[str, str]] = {
    "en": {
        "title": "Eliezer",
        "subtitle": "Your garden master. Every plant watered on time.",
        "tab_garden": "My garden",
        "tab_photo": "Add by photo",
        "tab_search": "Add by name",
        "loading": "Loading your garden...",
        "empty_title": "Your garden is empty",
        "empty_garden": "Add your first plant from a photo or by name.",
        "plants_one": "1 plant",
        "plants_many": "{count} plants",
        "thirsty_one": "1 plant needs water",
        "thirsty_many": "{count} plants need water",
        "all_watered": "All plants are watered",
        "open": "Open {name}",
        "water_today": "water today",
        "water_tomorrow": "water tomorrow",
        "water_in": "water in {days} days",
        "overdue_one": "1 day overdue",
        "overdue": "{days} days overdue",
        "schedule": "Water every {days} days · next watering {date}",
        "watered_button": "I watered it",
        "watered": "Watered {name}. Next watering in {days} days.",
        "care_heading": "How to care for it",
        "light": "Light: {light}",
        "sun_full_sun": "full sun",
        "sun_partial_shade": "partial shade",
        "sun_shade": "shade",
        "curated_note": "General guidance.",
        "ai_note": "Written by Eliezer's AI. Check it before relying on it.",
        "no_care": "No care instructions yet.",
        "get_care": "Get care instructions from Eliezer",
        "writing_care": "Eliezer is writing care instructions...",
        "care_ready": "Care instructions for {name} are ready.",
        "photo_add": "Add a photo",
        "photo_change": "Change the photo",
        "photo_pick": "Choose or take a photo",
        "photo_save": "Save photo",
        "photo_saved": "Saved the photo of {name}.",
        "edit_heading": "Edit details",
        "nickname": "Nickname (optional)",
        "location": "Location (optional)",
        "interval": "Water every (days)",
        "save": "Save changes",
        "saved": "Saved {name}.",
        "delete": "Remove from my garden",
        "delete_confirm": "Remove {name} from your garden? Its photo is deleted too.",
        "delete_yes": "Yes, remove it",
        "deleted": "Removed {name}.",
        "photo_intro": "Photograph a leaf or flower up close, in good light. Eliezer suggests up to 3 matching plants.",
        "use_camera": "Use my camera",
        "camera": "Take a photo",
        "upload": "Upload or take a photo",
        "identify": "Identify the plant",
        "identifying": "Eliezer is looking at your photo...",
        "need_photo": "Take or upload a photo first.",
        "not_a_plant": "That doesn't look like a plant. Try another photo.",
        "which_one": "Which one is it?",
        "sure": "{pct}% sure",
        "genus_match": "added as the genus {name}",
        "new_plant": "new to the plant database",
        "demo_note": "Demo mode: these answers come from a fixed stand-in, not a real model.",
        "model_note": "Identified by {model}. AI can be wrong: check the name.",
        "add": "Add to my garden",
        "added": "Added {name} to your garden.",
        "not_sure": "Not sure? Search by name instead.",
        "search": "Plant name (English, Hebrew or Latin)",
        "search_placeholder": "e.g. rosemary, lemon, Salvia",
        "search_hint": "Type at least 2 letters.",
        "no_results": "No plants match “{q}”.",
        "has_care": "Care guide",
        "in_garden": "In your garden",
        "add_short": "Add",
        "err_unavailable": "Cannot reach the backend at {url}. Start it (docker compose up) and reload the page.",
        "err_no_answer_read": "The backend took too long to answer. Reload the page to try again.",
        "err_no_answer_write": "The backend did not answer in time. Your change may have been saved. Reload the page and check before trying again.",
        "err_validation": "Please fix: {problems}",
        "err_not_found": "That plant no longer exists. Reload the page.",
        "err_conflict": "That plant is already in the database. Search for it by name.",
        "err_ai_unavailable": "Eliezer's AI is unavailable right now. Try again in a minute, or add the plant by name.",
        "err_ai_bad_output": "Eliezer's AI gave an unusable answer. Try another photo.",
        "err_server": "The backend failed ({code}). Check its logs.",
        "err_not_api": "The service at {url} did not answer like the Eliezer API. Check BACKEND_URL.",
    },
    "he": {
        "title": "אליעזר",
        "subtitle": "מאסטר הגינה שלך. כל צמח מושקה בזמן.",
        "tab_garden": "הגינה שלי",
        "tab_photo": "הוספה מתמונה",
        "tab_search": "הוספה לפי שם",
        "loading": "טוען את הגינה שלך...",
        "empty_title": "הגינה שלך ריקה",
        "empty_garden": "הוסיפו את הצמח הראשון מתמונה או לפי שם.",
        "plants_one": "צמח אחד",
        "plants_many": "{count} צמחים",
        "thirsty_one": "צמח אחד צריך השקיה",
        "thirsty_many": "{count} צמחים צריכים השקיה",
        "all_watered": "כל הצמחים מושקים",
        "open": "פתיחת {name}",
        "water_today": "להשקות היום",
        "water_tomorrow": "להשקות מחר",
        "water_in": "להשקות בעוד {days} ימים",
        "overdue_one": "באיחור של יום",
        "overdue": "באיחור של {days} ימים",
        "schedule": "השקיה כל {days} ימים · ההשקיה הבאה ב-{date}",
        "watered_button": "השקיתי",
        "watered": "השקיתם את {name}. ההשקיה הבאה בעוד {days} ימים.",
        "care_heading": "איך לטפל בו",
        "light": "אור: {light}",
        "sun_full_sun": "שמש מלאה",
        "sun_partial_shade": "צל חלקי",
        "sun_shade": "צל",
        "curated_note": "הנחיות כלליות.",
        "ai_note": "נכתב על ידי הבינה המלאכותית של אליעזר. כדאי לבדוק לפני שסומכים על זה.",
        "no_care": "אין עדיין הוראות טיפול.",
        "get_care": "קבלו הוראות טיפול מאליעזר",
        "writing_care": "אליעזר כותב הוראות טיפול...",
        "care_ready": "הוראות הטיפול עבור {name} מוכנות.",
        "photo_add": "הוספת תמונה",
        "photo_change": "החלפת התמונה",
        "photo_pick": "בחרו או צלמו תמונה",
        "photo_save": "שמירת התמונה",
        "photo_saved": "התמונה של {name} נשמרה.",
        "edit_heading": "עריכת פרטים",
        "nickname": "כינוי (לא חובה)",
        "location": "מיקום (לא חובה)",
        "interval": "השקיה כל (ימים)",
        "save": "שמירת שינויים",
        "saved": "{name} נשמר.",
        "delete": "הסרה מהגינה שלי",
        "delete_confirm": "להסיר את {name} מהגינה? גם התמונה שלו תימחק.",
        "delete_yes": "כן, להסיר",
        "deleted": "{name} הוסר.",
        "photo_intro": "צלמו עלה או פרח מקרוב ובאור טוב. אליעזר יציע עד 3 צמחים מתאימים.",
        "use_camera": "שימוש במצלמה",
        "camera": "צלמו תמונה",
        "upload": "העלו או צלמו תמונה",
        "identify": "זיהוי הצמח",
        "identifying": "אליעזר מסתכל על התמונה...",
        "need_photo": "צלמו או העלו תמונה קודם.",
        "not_a_plant": "זה לא נראה כמו צמח. נסו תמונה אחרת.",
        "which_one": "איזה מהם זה?",
        "sure": "ביטחון {pct}%",
        "genus_match": "יתווסף כסוג {name}",
        "new_plant": "חדש במאגר הצמחים",
        "demo_note": "מצב הדגמה: התשובות מגיעות מתחליף קבוע, לא ממודל אמיתי.",
        "model_note": "זוהה על ידי {model}. בינה מלאכותית יכולה לטעות: בדקו את השם.",
        "add": "הוספה לגינה שלי",
        "added": "{name} נוסף לגינה שלך.",
        "not_sure": "לא בטוחים? חפשו לפי שם.",
        "search": "שם הצמח (עברית, אנגלית או לטינית)",
        "search_placeholder": "למשל רוזמרין, לימון, Salvia",
        "search_hint": "הקלידו לפחות 2 אותיות.",
        "no_results": "לא נמצאו צמחים עבור „{q}”.",
        "has_care": "יש הוראות טיפול",
        "in_garden": "כבר בגינה",
        "add_short": "הוספה",
        "err_unavailable": "אין חיבור לשרת בכתובת {url}. הפעילו אותו (docker compose up) וטענו מחדש את הדף.",
        "err_no_answer_read": "השרת לא ענה בזמן. טענו מחדש את הדף כדי לנסות שוב.",
        "err_no_answer_write": "השרת לא ענה בזמן. ייתכן שהשינוי נשמר. טענו מחדש את הדף ובדקו לפני שתנסו שוב.",
        "err_validation": "נא לתקן: {problems}",
        "err_not_found": "הצמח הזה כבר לא קיים. טענו מחדש את הדף.",
        "err_conflict": "הצמח הזה כבר קיים במאגר. חפשו אותו לפי שם.",
        "err_ai_unavailable": "הבינה המלאכותית של אליעזר לא זמינה כרגע. נסו שוב בעוד דקה, או הוסיפו את הצמח לפי שם.",
        "err_ai_bad_output": "הבינה המלאכותית של אליעזר החזירה תשובה לא שמישה. נסו תמונה אחרת.",
        "err_server": "השרת נכשל ({code}). בדקו את היומנים שלו.",
        "err_not_api": "השירות בכתובת {url} לא ענה כמו ה-API של אליעזר. בדקו את BACKEND_URL.",
    },
}

# Applied with st.html when Hebrew is chosen. Style-only HTML takes no space.
RTL_CSS = """<style>
.stApp, [data-testid="stMain"], [data-testid="stSidebar"],
[data-testid="stDialog"], [data-testid="stToast"] { direction: rtl; }
[data-testid="stMarkdownContainer"], input, textarea { text-align: right; }
</style>"""


def t(key: str, lang: str, **values) -> str:
    return STRINGS[lang][key].format(**values)


def count(n: int, key: str, lang: str) -> str:
    """count(1, "plants", "en") -> '1 plant'; count(3, ...) -> '3 plants'."""
    return t(f"{key}_one", lang) if n == 1 else t(f"{key}_many", lang, count=n)


def days_left(days: int, lang: str) -> str:
    if days == 0:
        return t("water_today", lang)
    if days == 1:
        return t("water_tomorrow", lang)
    if days > 1:
        return t("water_in", lang, days=days)
    if days == -1:
        return t("overdue_one", lang)
    return t("overdue", lang, days=-days)


def short_date(iso: str) -> str:
    """'2026-11-14' -> '14/11', the day-first style used in Israel."""
    day = date.fromisoformat(iso)
    return f"{day.day}/{day.month}"
