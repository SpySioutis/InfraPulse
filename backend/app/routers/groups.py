"""Server group CRUD. Example groups are suggestions only — never seeded."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import auth
from app.database import get_db
from app.models import Server, ServerGroup, User
from app.schemas import GroupIn, GroupOut

router = APIRouter(prefix="/groups", tags=["groups"])


def _out(group: ServerGroup, db: Session) -> GroupOut:
    payload = GroupOut.model_validate(group)
    payload.server_count = db.query(Server).filter(Server.group_id == group.id).count()
    return payload


@router.get("", response_model=list[GroupOut])
def list_groups(user: User = Depends(auth.get_current_user), db: Session = Depends(get_db)) -> list[GroupOut]:
    return [_out(g, db) for g in db.query(ServerGroup).order_by(ServerGroup.name).all()]


@router.post("", response_model=GroupOut, status_code=201)
def create_group(
    payload: GroupIn, user: User = Depends(auth.get_current_user), db: Session = Depends(get_db)
) -> GroupOut:
    group = ServerGroup(name=payload.name.strip(), description=payload.description)
    db.add(group)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="A group with this name already exists.")
    db.refresh(group)
    auth.audit(db, user, "group.create", "server_group", group.id, group.name)
    return _out(group, db)


@router.put("/{group_id}", response_model=GroupOut)
def rename_group(
    group_id: str,
    payload: GroupIn,
    user: User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
) -> GroupOut:
    group = db.get(ServerGroup, group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="Group not found.")
    group.name = payload.name.strip()
    group.description = payload.description
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="A group with this name already exists.")
    db.refresh(group)
    auth.audit(db, user, "group.update", "server_group", group.id, group.name)
    return _out(group, db)


@router.delete("/{group_id}", status_code=204)
def delete_group(
    group_id: str, user: User = Depends(auth.require_admin), db: Session = Depends(get_db)
) -> None:
    group = db.get(ServerGroup, group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="Group not found.")
    in_use = db.query(Server).filter(Server.group_id == group_id).count()
    if in_use:
        raise HTTPException(
            status_code=409, detail=f"Group still has {in_use} server(s). Reassign them first."
        )
    db.delete(group)
    db.commit()
    auth.audit(db, user, "group.delete", "server_group", group_id, group.name)
