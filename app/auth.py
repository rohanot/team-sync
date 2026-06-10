from fastapi import Depends, Header, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.database import get_db


def first_user(db: Session) -> models.User:
    user = db.scalar(select(models.User).order_by(models.User.created_at))
    if user is None:
        user = models.User(username="system", display_name="System User", email="system@teamsync.local")
        db.add(user)
        db.flush()
    return user


def user_from_dev_token(db: Session, token: str | None) -> models.User | None:
    if not token:
        return None
    username = token.removeprefix("Bearer ").removeprefix("dev-")
    return db.scalar(select(models.User).where(models.User.username == username))


def resolve_actor(
    db: Session = Depends(get_db),
    user_id: str | None = Query(default=None, alias="user_id"),
    x_dev_token: str | None = Header(default=None, alias="X-Dev-Token"),
    authorization: str | None = Header(default=None),
) -> models.User:
    token_user = user_from_dev_token(db, x_dev_token or authorization)
    if token_user:
        return token_user
    if user_id:
        user = db.get(models.User, user_id)
        if user is None:
            user = db.scalar(select(models.User).where(models.User.username == user_id))
        if user:
            return user
        raise HTTPException(status_code=401, detail={"code": "invalid_actor", "message": "Unknown user"})
    return first_user(db)


ROLE_RANK = {"viewer": 1, "member": 2, "admin": 3}


def project_role(db: Session, project_id: str, user_id: str) -> str:
    membership = db.scalar(
        select(models.ProjectMember)
        .where(models.ProjectMember.project_id == project_id, models.ProjectMember.user_id == user_id)
    )
    return membership.role if membership else "viewer"


def require_project_role(db: Session, project_id: str, user_id: str, minimum_role: str) -> None:
    role = project_role(db, project_id, user_id)
    if ROLE_RANK.get(role, 0) < ROLE_RANK[minimum_role]:
        raise HTTPException(
            status_code=403,
            detail={"code": "forbidden", "message": f"{minimum_role} role required", "role": role},
        )
