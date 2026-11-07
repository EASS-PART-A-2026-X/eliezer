"""The committed catalog files: names, Hebrew, curated care, demo garden."""

import csv
import json

from app.models import CareGuide, CareSource, has_hebrew
from app.seed import DATA, DEMO_GARDEN, catalog_rows


def test_wikidata_csv_is_usable():
    with (DATA / "plants.csv").open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) >= 1000
    sci = [r["scientific_name"] for r in rows]
    assert len(sci) == len(set(sci))  # unique
    for row in rows:
        assert row["name_en"] and row["scientific_name"]
        assert has_hebrew(row["name_he"]), row


def test_curated_care_is_valid_and_merged():
    curated = json.loads((DATA / "care_curated.json").read_text(encoding="utf-8"))
    assert len(curated) >= 40
    for entry in curated:
        CareGuide.model_validate({k: entry[k] for k in CareGuide.model_fields})
    rows = {r["scientific_name"]: r for r in catalog_rows()}
    for entry in curated:
        row = rows[entry["scientific_name"]]
        assert row["care_source"] == CareSource.CURATED
        assert row["name_he"] == entry["name_he"]


def test_demo_garden_plants_have_curated_care():
    rows = {r["scientific_name"]: r for r in catalog_rows()}
    for scientific_name, *_ in DEMO_GARDEN:
        assert rows[scientific_name]["care_source"] == CareSource.CURATED
