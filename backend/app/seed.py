"""Demo rows inserted on first start. Synthetic data only."""

from sqlmodel import Session, select

from app.models import Item

SEED: list[dict] = [
    {
        "title": "Write the product sketch",
        "description": "Purpose, operational principle and three user stories.",
        "priority": 4,
        "tags": "work",
    },
    {
        "title": "Pick open-source candidates",
        "description": "Three projects with more than 10,000 stars.",
        "priority": 2,
        "tags": "idea",
    },
    {
        "title": "Buy coffee",
        "description": "",
        "priority": 3,
        "tags": "errand",
    },
]


def seed_if_empty(session: Session) -> int:
    """Insert the demo rows only when the table is empty. Returns rows added."""
    if session.exec(select(Item).limit(1)).first() is not None:
        return 0
    # Seeds are input too: model_validate checks the limits; Item(**row) does not.
    session.add_all([Item.model_validate(row) for row in SEED])
    session.commit()
    return len(SEED)
