"""Both languages must say the same things, with the same placeholders."""

import re
import string

import pytest

from i18n import STRINGS, days_left, short_date, t

HEBREW = re.compile(r"[֐-׿]")


def placeholders(text: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


def test_same_keys_in_both_languages():
    assert STRINGS["en"].keys() == STRINGS["he"].keys()


@pytest.mark.parametrize("key", sorted(STRINGS["en"]))
def test_same_placeholders(key):
    assert placeholders(STRINGS["en"][key]) == placeholders(STRINGS["he"][key]), key


@pytest.mark.parametrize("key", sorted(STRINGS["he"]))
def test_hebrew_strings_are_hebrew(key):
    assert HEBREW.search(STRINGS["he"][key]), key


def test_days_left_wording():
    assert [days_left(d, "en") for d in (3, 1, 0, -1, -4)] == [
        "water in 3 days",
        "water tomorrow",
        "water today",
        "1 day overdue",
        "4 days overdue",
    ]
    assert days_left(3, "he") == "להשקות בעוד 3 ימים"
    assert days_left(-4, "he") == "באיחור של 4 ימים"


def test_t_fills_placeholders():
    assert (
        t("watered", "en", name="Basil", days=2)
        == "Watered Basil. Next watering in 2 days."
    )


def test_short_date_is_day_first():
    assert short_date("2026-11-04") == "4/11"
