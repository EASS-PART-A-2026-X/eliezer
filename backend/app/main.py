from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query, status
from sqlmodel import Session, select

from app import db
from app.ai_client import AIClientDep, AIServiceBadOutput, AIServiceUnavailable
from app.models import FromTextRequest, Item, ItemCreate, ItemPublic, ItemUpdate
from app.seed import seed_if_empty


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.create_db_and_tables()
    with Session(db.engine) as session:
        seed_if_empty(session)
    yield
    db.engine.dispose()


app = FastAPI(title="eliezer API", lifespan=lifespan)


def save(session: Session, item: Item) -> Item:
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def get_or_404(session: Session, item_id: int) -> Item:
    item = session.get(Item, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Item not found")
    return item


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/items", response_model=list[ItemPublic])
def list_items(
    session: db.SessionDep,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[Item]:
    query = select(Item).order_by(Item.id).offset(offset).limit(limit)
    return list(session.exec(query).all())


@app.post("/items", response_model=ItemPublic, status_code=status.HTTP_201_CREATED)
def create_item(body: ItemCreate, session: db.SessionDep) -> Item:
    return save(session, Item.model_validate(body))


@app.post(
    "/items/from-text",
    response_model=ItemPublic,
    status_code=status.HTTP_201_CREATED,
)
def create_item_from_text(
    body: FromTextRequest, session: db.SessionDep, ai: AIClientDep
) -> Item:
    try:
        new_item = ai.extract_item(body.text)
    except AIServiceUnavailable as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, detail="AI service unavailable"
        ) from exc
    except AIServiceBadOutput as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, detail="AI service returned invalid output"
        ) from exc
    return save(session, Item.model_validate(new_item))


@app.get("/items/{item_id}", response_model=ItemPublic)
def get_item(item_id: int, session: db.SessionDep) -> Item:
    return get_or_404(session, item_id)


@app.patch("/items/{item_id}", response_model=ItemPublic)
def update_item(item_id: int, body: ItemUpdate, session: db.SessionDep) -> Item:
    item = get_or_404(session, item_id)
    # null means "leave unchanged": a stored None would break the contract.
    item.sqlmodel_update(body.model_dump(exclude_unset=True, exclude_none=True))
    return save(session, item)


@app.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(item_id: int, session: db.SessionDep) -> None:
    session.delete(get_or_404(session, item_id))
    session.commit()
