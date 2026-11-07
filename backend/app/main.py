import logging
import re
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Annotated

from fastapi import FastAPI, File, HTTPException, Query, Response, UploadFile, status
from sqlalchemy import case, func, or_
from sqlmodel import Session, col, delete, select

from app import clock, db
from app.ai_client import AIClientDep, AIServiceBadOutput, AIServiceUnavailable
from app.images import (
    IDENTIFY_MAX_SIDE,
    MAX_UPLOAD_BYTES,
    THUMBNAIL_MAX_SIDE,
    InvalidImage,
    to_jpeg,
)
from app.models import (
    CareSource,
    GardenPhoto,
    GardenPlant,
    GardenPlantCreate,
    GardenPlantPublic,
    GardenPlantUpdate,
    IdentifyCandidate,
    IdentifyResponse,
    Plant,
    PlantCreate,
    PlantPublic,
)
from app.seed import seed_catalog_if_empty, seed_garden_if_empty

logger = logging.getLogger("eliezer")


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.create_db_and_tables()
    with Session(db.engine) as session:
        plants = seed_catalog_if_empty(session)
        garden = seed_garden_if_empty(session, clock.now())
    logger.warning("seeded %d catalog plants, %d garden plants", plants, garden)
    yield
    db.engine.dispose()


app = FastAPI(title="Eliezer API", lifespan=lifespan)

Offset = Annotated[int, Query(ge=0)]
Limit = Annotated[int, Query(ge=1, le=100)]


def save[T](session: Session, row: T) -> T:
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def ai_errors_to_http(exc: Exception) -> HTTPException:
    if isinstance(exc, AIServiceUnavailable):
        return HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, detail="AI service unavailable"
        )
    return HTTPException(
        status.HTTP_502_BAD_GATEWAY, detail="AI service returned invalid output"
    )


def invalid_photo(message: str) -> HTTPException:
    # Same shape as FastAPI's own 422s, so clients show one kind of message.
    detail = [{"loc": ["body", "photo"], "msg": message, "type": "invalid_image"}]
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail)


def read_photo(photo: UploadFile, max_side: int) -> bytes:
    data = photo.file.read(MAX_UPLOAD_BYTES + 1)
    try:
        return to_jpeg(data, max_side)
    except InvalidImage as exc:
        raise invalid_photo(str(exc)) from exc


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# --- catalog -------------------------------------------------------------------------
def plant_or_404(session: Session, plant_id: int) -> Plant:
    plant = session.get(Plant, plant_id)
    if plant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Plant not found")
    return plant


@app.get("/plants", response_model=list[PlantPublic])
def search_plants(
    session: db.SessionDep,
    q: Annotated[str | None, Query(max_length=100)] = None,
    offset: Offset = 0,
    limit: Limit = 20,
) -> list[Plant]:
    query = select(Plant)
    if q and q.strip():
        term = q.strip()
        query = query.where(
            or_(
                col(Plant.name_en).icontains(term, autoescape=True),
                col(Plant.name_he).icontains(term, autoescape=True),
                col(Plant.scientific_name).icontains(term, autoescape=True),
            )
        )
    order = case(
        (col(Plant.care_source) == CareSource.CURATED, 0),
        (col(Plant.care_source) == CareSource.AI, 1),
        else_=2,
    )
    query = query.order_by(
        order, func.length(Plant.scientific_name), Plant.scientific_name
    )
    return list(session.exec(query.offset(offset).limit(limit)).all())


@app.get("/plants/{plant_id}", response_model=PlantPublic)
def get_plant(plant_id: int, session: db.SessionDep) -> Plant:
    return plant_or_404(session, plant_id)


@app.post("/plants", response_model=PlantPublic, status_code=status.HTTP_201_CREATED)
def create_plant(body: PlantCreate, session: db.SessionDep) -> Plant:
    exists = session.exec(
        select(Plant.id).where(
            func.lower(Plant.scientific_name) == body.scientific_name.lower()
        )
    ).first()
    if exists is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Plant already exists")
    return save(session, Plant.model_validate(body))


@app.post("/plants/{plant_id}/care", response_model=PlantPublic)
def write_care(plant_id: int, session: db.SessionDep, ai: AIClientDep) -> Plant:
    """Return the plant's care; ask the AI service to write it the first time."""
    plant = plant_or_404(session, plant_id)
    if plant.care_source != CareSource.NONE:
        return plant  # idempotent: never pay for the same guide twice
    try:
        guide = ai.write_care(plant.scientific_name, plant.name_en, plant.name_he)
    except (AIServiceUnavailable, AIServiceBadOutput) as exc:
        raise ai_errors_to_http(exc) from exc
    plant.sqlmodel_update(guide.model_dump())
    plant.care_source = CareSource.AI
    return save(session, plant)


def normalize_scientific(name: str) -> str:
    """'Citrus ×limon', 'Citrus × limon' and 'citrus limon' compare equal."""
    return re.sub(r"\s+", " ", name.replace("×", " ")).strip().lower()


@app.post("/plants/identify", response_model=IdentifyResponse)
def identify_plant(
    session: db.SessionDep, ai: AIClientDep, photo: Annotated[UploadFile, File()]
) -> IdentifyResponse:
    """Ask the AI service what the photo shows; match its guesses to the catalog.

    Writes nothing: the user confirms a candidate, then adds it to the garden.
    """
    jpeg = read_photo(photo, IDENTIFY_MAX_SIDE)
    try:
        result = ai.identify(jpeg)
    except (AIServiceUnavailable, AIServiceBadOutput) as exc:
        raise ai_errors_to_http(exc) from exc
    catalog = {
        normalize_scientific(name): plant_id
        for plant_id, name in session.exec(select(Plant.id, Plant.scientific_name))
    }
    candidates = []
    for c in result.candidates if result.is_plant else []:
        key = normalize_scientific(c.scientific_name)
        genus = key.split(" ")[0]
        if key in catalog:
            plant_id, matched_on = catalog[key], "species"
        elif genus in catalog:
            plant_id, matched_on = catalog[genus], "genus"
        else:
            plant_id, matched_on = None, None
        candidates.append(
            IdentifyCandidate(
                **c.model_dump(), plant_id=plant_id, matched_on=matched_on
            )
        )
    return IdentifyResponse(
        is_plant=result.is_plant, model=result.model, candidates=candidates
    )


# --- garden --------------------------------------------------------------------------
def garden_or_404(session: Session, garden_id: int) -> GardenPlant:
    garden_plant = session.get(GardenPlant, garden_id)
    if garden_plant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Garden plant not found")
    return garden_plant


def has_photo(session: Session, garden_id: int) -> bool:
    query = select(GardenPhoto.garden_plant_id).where(
        GardenPhoto.garden_plant_id == garden_id
    )
    return session.exec(query).first() is not None


def to_public(
    garden_plant: GardenPlant, plant: Plant, photo: bool, now: datetime
) -> GardenPlantPublic:
    next_on = clock.next_watering_on(
        garden_plant.last_watered_at, garden_plant.watering_interval_days
    )
    return GardenPlantPublic(
        **garden_plant.model_dump(exclude={"plant_id"}),
        plant=PlantPublic.model_validate(plant),
        next_watering_on=next_on,
        days_until_watering=clock.days_until(next_on, now),
        has_photo=photo,
    )


def public_one(session: Session, garden_plant: GardenPlant, now: datetime):
    plant = session.get(Plant, garden_plant.plant_id)
    return to_public(garden_plant, plant, has_photo(session, garden_plant.id), now)


@app.get("/garden", response_model=list[GardenPlantPublic])
def list_garden(
    session: db.SessionDep, now: clock.NowDep, offset: Offset = 0, limit: Limit = 100
) -> list[GardenPlantPublic]:
    rows = session.exec(
        select(GardenPlant, Plant).join(Plant).order_by(GardenPlant.id)
    ).all()
    with_photo = set(session.exec(select(GardenPhoto.garden_plant_id)).all())
    items = [to_public(g, p, g.id in with_photo, now) for g, p in rows]
    # A single garden is small; sorting here keeps the date maths in one place.
    items.sort(key=lambda item: (item.days_until_watering, item.id))
    return items[offset : offset + limit]


@app.post(
    "/garden", response_model=GardenPlantPublic, status_code=status.HTTP_201_CREATED
)
def add_to_garden(
    body: GardenPlantCreate, session: db.SessionDep, now: clock.NowDep
) -> GardenPlantPublic:
    plant = plant_or_404(session, body.plant_id)
    garden_plant = GardenPlant(
        plant_id=plant.id,
        nickname=body.nickname or None,
        location=body.location or None,
        watering_interval_days=(
            body.watering_interval_days or plant.watering_interval_days or 7
        ),
        last_watered_at=now,  # new plants start "just watered"
        created_at=now,
    )
    return to_public(save(session, garden_plant), plant, False, now)


@app.get("/garden/{garden_id}", response_model=GardenPlantPublic)
def get_garden_plant(
    garden_id: int, session: db.SessionDep, now: clock.NowDep
) -> GardenPlantPublic:
    return public_one(session, garden_or_404(session, garden_id), now)


@app.patch("/garden/{garden_id}", response_model=GardenPlantPublic)
def update_garden_plant(
    garden_id: int, body: GardenPlantUpdate, session: db.SessionDep, now: clock.NowDep
) -> GardenPlantPublic:
    garden_plant = garden_or_404(session, garden_id)
    changes = body.model_dump(exclude_unset=True)
    if changes.get("watering_interval_days") is None:
        changes.pop("watering_interval_days", None)  # null means "leave unchanged"
    for key in ("nickname", "location"):
        if key in changes and not changes[key]:
            changes[key] = None  # "" or null clears the text
    garden_plant.sqlmodel_update(changes)
    return public_one(session, save(session, garden_plant), now)


@app.delete("/garden/{garden_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_from_garden(garden_id: int, session: db.SessionDep) -> None:
    garden_plant = garden_or_404(session, garden_id)
    session.exec(delete(GardenPhoto).where(GardenPhoto.garden_plant_id == garden_id))
    session.delete(garden_plant)
    session.commit()


@app.post("/garden/{garden_id}/water", response_model=GardenPlantPublic)
def water(garden_id: int, session: db.SessionDep, now: clock.NowDep):
    """Mark the plant as watered now: the countdown starts again."""
    garden_plant = garden_or_404(session, garden_id)
    garden_plant.last_watered_at = now
    return public_one(session, save(session, garden_plant), now)


@app.put("/garden/{garden_id}/photo", status_code=status.HTTP_204_NO_CONTENT)
def put_photo(
    garden_id: int, session: db.SessionDep, photo: Annotated[UploadFile, File()]
) -> None:
    garden_or_404(session, garden_id)
    jpeg = read_photo(photo, THUMBNAIL_MAX_SIDE)
    existing = session.get(GardenPhoto, garden_id)
    if existing is None:
        session.add(GardenPhoto(garden_plant_id=garden_id, jpeg=jpeg))
    else:
        existing.jpeg = jpeg
    session.commit()


@app.get("/garden/{garden_id}/photo", response_class=Response)
def get_photo(garden_id: int, session: db.SessionDep) -> Response:
    photo = session.get(GardenPhoto, garden_id)
    if photo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No photo")
    return Response(content=photo.jpeg, media_type="image/jpeg")
