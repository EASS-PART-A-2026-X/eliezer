"""Every user-facing sentence, in English and Hebrew. tests/test_i18n.py checks
that both languages have exactly the same keys and placeholders."""

from datetime import date

LANGUAGES = {"English": "en", "עברית": "he"}

STRINGS: dict[str, dict[str, str]] = {
    "en": {
        "title": "Eliezer — your garden master",
        "subtitle": "Every plant in your garden, watered on time.",
        "language": "Language",
        "tab_garden": "My garden",
        "tab_photo": "Add from a photo",
        "tab_search": "Add by name",
        "loading": "Loading your garden...",
        "empty_garden": "Your garden is empty. Add your first plant from a photo or by name.",
        "water_today": "water today",
        "water_tomorrow": "water tomorrow",
        "water_in": "water in {days} days",
        "overdue_one": "1 day overdue",
        "overdue": "{days} days overdue",
        "schedule": "Water every {days} days · next watering {date}",
        "watered_button": "💧 I watered it",
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
        "edit_heading": "Edit",
        "nickname": "Nickname (optional)",
        "location": "Location (optional)",
        "interval": "Water every (days)",
        "save": "Save changes",
        "saved": "Saved {name}.",
        "delete": "Remove from my garden",
        "deleted": "Removed {name}.",
        "camera": "Take a photo",
        "upload": "...or upload a photo",
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
        "search_hint": "Type at least 2 letters.",
        "no_results": "No plants match “{q}”.",
        "choose": "Choose a plant",
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
        "title": "אליעזר — מאסטר הגינה שלך",
        "subtitle": "כל צמח בגינה שלך, מושקה בזמן.",
        "language": "שפה",
        "tab_garden": "הגינה שלי",
        "tab_photo": "הוספה מתמונה",
        "tab_search": "הוספה לפי שם",
        "loading": "טוען את הגינה שלך...",
        "empty_garden": "הגינה שלך ריקה. הוסיפו את הצמח הראשון מתמונה או לפי שם.",
        "water_today": "להשקות היום",
        "water_tomorrow": "להשקות מחר",
        "water_in": "להשקות בעוד {days} ימים",
        "overdue_one": "באיחור של יום",
        "overdue": "באיחור של {days} ימים",
        "schedule": "השקיה כל {days} ימים · ההשקיה הבאה ב-{date}",
        "watered_button": "💧 השקיתי",
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
        "edit_heading": "עריכה",
        "nickname": "כינוי (לא חובה)",
        "location": "מיקום (לא חובה)",
        "interval": "השקיה כל (ימים)",
        "save": "שמירת שינויים",
        "saved": "{name} נשמר.",
        "delete": "הסרה מהגינה שלי",
        "deleted": "{name} הוסר.",
        "camera": "צלמו תמונה",
        "upload": "...או העלו תמונה",
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
        "search_hint": "הקלידו לפחות 2 אותיות.",
        "no_results": "לא נמצאו צמחים עבור „{q}”.",
        "choose": "בחרו צמח",
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
.stApp, [data-testid="stMain"], [data-testid="stSidebar"] { direction: rtl; }
[data-testid="stMarkdownContainer"], input, textarea { text-align: right; }
</style>"""


def t(key: str, lang: str, **values) -> str:
    return STRINGS[lang][key].format(**values)


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


def status_icon(days: int) -> str:
    return "🔴" if days < 0 else "💧" if days == 0 else "🟢"


def short_date(iso: str) -> str:
    """'2026-11-14' -> '14/11', the day-first style used in Israel."""
    day = date.fromisoformat(iso)
    return f"{day.day}/{day.month}"
