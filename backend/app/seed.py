"""Load the plant catalog and a small demo garden on first start (idempotent).

plants.csv          names from Wikidata (CC0), built by scripts/build_catalog.py
care_curated.json   hand-written general care guidance for common garden plants;
                    entries missing from the CSV are added to the catalog
"""

import csv
import json
from datetime import datetime, timedelta
from functools import cache
from pathlib import Path

from sqlmodel import Session, select

from app.models import CareGuide, CareSource, GardenPlant, Plant

DATA = Path(__file__).parent / "data"

# Synthetic demo garden: (scientific name, nickname, location, days since watered)
DEMO_GARDEN = [
    ("Salvia rosmarinus", "Rosemary bush", "Herb bed", 6),
    ("Ocimum basilicum", None, "Kitchen window", 1),
    ("Citrus × limon", None, "Back yard", 3),
]


@cache
def catalog_rows() -> tuple[dict, ...]:
    """Every catalog row, validated: Wikidata names merged with curated care."""
    with (DATA / "plants.csv").open(encoding="utf-8") as f:
        rows = {row["scientific_name"]: row for row in csv.DictReader(f)}
    curated = json.loads((DATA / "care_curated.json").read_text(encoding="utf-8"))
    for entry in curated:
        guide = CareGuide.model_validate(
            {k: entry[k] for k in CareGuide.model_fields}
        )  # same rules as AI-written care
        row = rows.setdefault(entry["scientific_name"], {"wikidata_id": None})
        row.update(
            scientific_name=entry["scientific_name"],
            name_en=entry["name_en"],  # curated names read better than labels
            name_he=entry["name_he"],
            care_source=CareSource.CURATED,
            **guide.model_dump(),
        )
    for row in rows.values():
        row["wikidata_id"] = row.get("wikidata_id") or None
        Plant.model_validate(row)  # fail at startup, not on first use
    return tuple(rows.values())


def seed_catalog_if_empty(session: Session) -> int:
    if session.exec(select(Plant.id).limit(1)).first() is not None:
        return 0
    rows = catalog_rows()
    session.add_all(Plant.model_validate(row) for row in rows)
    session.commit()
    return len(rows)


def seed_garden_if_empty(session: Session, now: datetime) -> int:
    if session.exec(select(GardenPlant.id).limit(1)).first() is not None:
        return 0
    added = 0
    for scientific_name, nickname, location, days_ago in DEMO_GARDEN:
        plant = session.exec(
            select(Plant).where(Plant.scientific_name == scientific_name)
        ).first()
        if plant is None:
            continue
        session.add(
            GardenPlant(
                plant_id=plant.id,
                nickname=nickname,
                location=location,
                watering_interval_days=plant.watering_interval_days or 7,
                last_watered_at=now - timedelta(days=days_ago),
                created_at=now,
            )
        )
        added += 1
    session.commit()
    return added
