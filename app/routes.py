from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import and_, desc, or_, select
from sqlalchemy.orm import Session

from app import models, schemas, services
from app.auth import project_role, require_project_role, resolve_actor
from app.database import get_db
from app.realtime import manager

router = APIRouter()


def actor(db: Session = Depends(get_db), user: models.User = Depends(resolve_actor)) -> models.User:
    return user


def realtime_event_message(event: models.RealtimeEvent, *, replay: bool) -> dict:
    return {"id": event.id, "type": event.event_type, "payload": event.payload, "replay": replay}


def schedule_latest_event(background_tasks: BackgroundTasks, db: Session, project_id: str) -> None:
    event = services.consume_last_realtime_event(db)
    if event is None:
        event = db.scalar(
            select(models.RealtimeEvent)
            .where(models.RealtimeEvent.project_id == project_id)
            .order_by(desc(models.RealtimeEvent.id))
        )
    if event:
        background_tasks.add_task(manager.broadcast, project_id, realtime_event_message(event, replay=False))


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "teamsync"}


@router.get("/api/users", response_model=list[schemas.UserRead])
def list_users(db: Session = Depends(get_db)) -> list[models.User]:
    return list(db.scalars(select(models.User).order_by(models.User.username)).all())


@router.get("/api/projects", response_model=list[schemas.ProjectRead])
def list_projects(db: Session = Depends(get_db)) -> list[models.Project]:
    return list(db.scalars(select(models.Project).order_by(models.Project.key)).all())


@router.get("/api/session", response_model=schemas.SessionRead)
def session(user: models.User = Depends(actor), db: Session = Depends(get_db)) -> schemas.SessionRead:
    memberships = db.scalars(select(models.ProjectMember).where(models.ProjectMember.user_id == user.id)).all()
    return schemas.SessionRead(
        user=schemas.UserRead.model_validate(user),
        memberships=[
            schemas.ProjectMembershipRead(project_id=m.project_id, project_key=m.project.key, role=m.role)
            for m in memberships
        ],
    )


@router.post("/api/projects/{project_id}/issues", response_model=schemas.IssueRead, status_code=201)
def create_issue(project_id: str, data: schemas.IssueCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db), user: models.User = Depends(actor)) -> schemas.IssueRead:
    project = services.get_project(db, project_id)
    require_project_role(db, project.id, user.id, "member")
    issue = services.create_issue(db, project.id, data, user.id)
    schedule_latest_event(background_tasks, db, issue.project_id)
    return services.issue_to_read(db, issue)


@router.get("/api/projects/{project_id}/board", response_model=schemas.BoardRead)
def get_board(project_id: str, db: Session = Depends(get_db)) -> schemas.BoardRead:
    return services.board(db, project_id)


@router.patch("/api/issues/{issue_id}", response_model=schemas.IssueRead)
def update_issue(issue_id: str, data: schemas.IssueUpdate, background_tasks: BackgroundTasks, db: Session = Depends(get_db), user: models.User = Depends(actor)) -> schemas.IssueRead:
    existing = services.get_issue(db, issue_id)
    require_project_role(db, existing.project_id, user.id, "member")
    issue = services.update_issue(db, issue_id, data, user.id)
    schedule_latest_event(background_tasks, db, issue.project_id)
    return services.issue_to_read(db, issue)


@router.post("/api/issues/{issue_id}/transitions", response_model=schemas.IssueRead)
def transition_issue(issue_id: str, data: schemas.TransitionRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db), user: models.User = Depends(actor)) -> schemas.IssueRead:
    existing = services.get_issue(db, issue_id)
    require_project_role(db, existing.project_id, user.id, "member")
    issue = services.transition_issue(db, issue_id, data, user.id)
    schedule_latest_event(background_tasks, db, issue.project_id)
    return services.issue_to_read(db, issue)


@router.get("/api/projects/{project_id}/sprints", response_model=list[schemas.SprintRead])
def list_sprints(project_id: str, db: Session = Depends(get_db)) -> list[models.Sprint]:
    project = services.get_project(db, project_id)
    return list(db.scalars(select(models.Sprint).where(models.Sprint.project_id == project.id).order_by(models.Sprint.start_date, models.Sprint.created_at)).all())


@router.post("/api/projects/{project_id}/sprints", response_model=schemas.SprintRead, status_code=201)
def create_sprint(project_id: str, data: schemas.SprintCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db), user: models.User = Depends(actor)) -> models.Sprint:
    project = services.get_project(db, project_id)
    require_project_role(db, project.id, user.id, "admin")
    sprint = services.create_sprint(db, project.id, data, user.id)
    schedule_latest_event(background_tasks, db, sprint.project_id)
    return sprint


@router.post("/api/sprints/{sprint_id}/start", response_model=schemas.SprintRead)
def start_sprint(sprint_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db), user: models.User = Depends(actor)) -> models.Sprint:
    existing = db.get(models.Sprint, sprint_id)
    if existing is None:
        raise services.not_found("sprint")
    require_project_role(db, existing.project_id, user.id, "admin")
    sprint = services.update_sprint(db, sprint_id, schemas.SprintUpdate(status="active"), user.id)
    schedule_latest_event(background_tasks, db, sprint.project_id)
    return sprint


@router.patch("/api/sprints/{sprint_id}", response_model=schemas.SprintRead)
def update_sprint(sprint_id: str, data: schemas.SprintUpdate, background_tasks: BackgroundTasks, db: Session = Depends(get_db), user: models.User = Depends(actor)) -> models.Sprint:
    existing = db.get(models.Sprint, sprint_id)
    if existing is None:
        raise services.not_found("sprint")
    require_project_role(db, existing.project_id, user.id, "admin")
    sprint = services.update_sprint(db, sprint_id, data, user.id)
    schedule_latest_event(background_tasks, db, sprint.project_id)
    return sprint


@router.post("/api/sprints/{sprint_id}/complete", response_model=schemas.SprintCompleteRead)
def complete_sprint(sprint_id: str, data: schemas.SprintCompleteRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db), user: models.User = Depends(actor)) -> schemas.SprintCompleteRead:
    existing = db.get(models.Sprint, sprint_id)
    if existing is None:
        raise services.not_found("sprint")
    require_project_role(db, existing.project_id, user.id, "admin")
    result = services.complete_sprint(db, sprint_id, data, user.id)
    schedule_latest_event(background_tasks, db, result.sprint.project_id)
    return result


@router.get("/api/issues/{issue_id}/comments", response_model=list[schemas.CommentRead])
def list_comments(issue_id: str, db: Session = Depends(get_db)) -> list[models.Comment]:
    issue = services.get_issue(db, issue_id)
    return list(db.scalars(select(models.Comment).where(models.Comment.issue_id == issue.id).order_by(models.Comment.created_at)).all())


@router.post("/api/issues/{issue_id}/comments", response_model=schemas.CommentRead, status_code=201)
def create_comment(issue_id: str, data: schemas.CommentCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db), user: models.User = Depends(actor)) -> models.Comment:
    issue = services.get_issue(db, issue_id)
    require_project_role(db, issue.project_id, user.id, "member")
    comment = services.create_comment(db, issue_id, data, user.id)
    issue = services.get_issue(db, comment.issue_id)
    schedule_latest_event(background_tasks, db, issue.project_id)
    return comment


@router.patch("/api/comments/{comment_id}", response_model=schemas.CommentRead)
def update_comment(comment_id: str, data: schemas.CommentUpdate, background_tasks: BackgroundTasks, db: Session = Depends(get_db), user: models.User = Depends(actor)) -> models.Comment:
    current = db.get(models.Comment, comment_id)
    if current is None:
        raise services.not_found("comment")
    issue = services.get_issue(db, current.issue_id)
    require_project_role(db, issue.project_id, user.id, "member")
    comment = services.update_comment(db, comment_id, data, user.id)
    issue = services.get_issue(db, comment.issue_id)
    schedule_latest_event(background_tasks, db, issue.project_id)
    return comment


@router.delete("/api/comments/{comment_id}", status_code=204)
def delete_comment(comment_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db), user: models.User = Depends(actor)) -> None:
    comment = db.get(models.Comment, comment_id)
    project_id = services.get_issue(db, comment.issue_id).project_id if comment else ""
    if project_id:
        require_project_role(db, project_id, user.id, "member")
    services.delete_comment(db, comment_id, user.id)
    if project_id:
        schedule_latest_event(background_tasks, db, project_id)


@router.get("/api/projects/{project_id}/activity", response_model=list[schemas.ActivityRead])
def activity(
    project_id: str,
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = None,
    action: str | None = None,
    issue_id: str | None = None,
    actor_id: str | None = None,
) -> list[models.ActivityLog]:
    project = services.get_project(db, project_id)
    stmt = select(models.ActivityLog).where(models.ActivityLog.project_id == project.id).order_by(desc(models.ActivityLog.created_at), models.ActivityLog.id).limit(limit)
    if cursor:
        try:
            created_text, last_id = cursor.split("|", 1)
            created_at = datetime.fromisoformat(created_text)
        except ValueError:
            raise HTTPException(status_code=422, detail={"code": "invalid_cursor", "message": "cursor is invalid"}) from None
        stmt = stmt.where(or_(models.ActivityLog.created_at < created_at, and_(models.ActivityLog.created_at == created_at, models.ActivityLog.id > last_id)))
    if action:
        stmt = stmt.where(models.ActivityLog.action == action)
    if issue_id:
        issue = services.get_issue(db, issue_id)
        stmt = stmt.where(models.ActivityLog.issue_id == issue.id)
    if actor_id:
        actor = services.get_user(db, actor_id)
        stmt = stmt.where(models.ActivityLog.actor_id == actor.id)
    return list(db.scalars(stmt).all())


@router.post("/api/issues/{issue_id}/watch", status_code=204)
def watch(issue_id: str, db: Session = Depends(get_db), user: models.User = Depends(actor)) -> None:
    issue = services.get_issue(db, issue_id)
    require_project_role(db, issue.project_id, user.id, "viewer")
    services.watch_issue(db, issue_id, user.id)


@router.delete("/api/issues/{issue_id}/watch", status_code=204)
def unwatch(issue_id: str, db: Session = Depends(get_db), user: models.User = Depends(actor)) -> None:
    issue = services.get_issue(db, issue_id)
    require_project_role(db, issue.project_id, user.id, "viewer")
    services.unwatch_issue(db, issue_id, user.id)


@router.get("/api/notifications", response_model=list[schemas.NotificationRead])
def notifications(db: Session = Depends(get_db), user: models.User = Depends(actor), unread_only: bool = False) -> list[models.Notification]:
    stmt = select(models.Notification).where(models.Notification.user_id == user.id).order_by(desc(models.Notification.created_at))
    if unread_only:
        stmt = stmt.where(models.Notification.read.is_(False))
    return list(db.scalars(stmt).all())


@router.get("/api/search", response_model=schemas.SearchRead)
def search(
    db: Session = Depends(get_db),
    q: str | None = None,
    project_id: str | None = None,
    status: str | None = None,
    assignee_id: str | None = None,
    priority: str | None = None,
    issue_type: str | None = None,
    sprint_id: str | None = None,
    cursor: str | None = None,
    limit: int = Query(default=25, ge=1, le=100),
) -> schemas.SearchRead:
    return services.search_issues(db, q, project_id, status, assignee_id, priority, issue_type, sprint_id, cursor, limit)


@router.websocket("/ws/projects/{project_id}")
async def websocket_project(project_id: str, websocket: WebSocket, last_event_id: int | None = None, user_id: str = "anonymous") -> None:
    from app.database import SessionLocal

    db = SessionLocal()
    resolved_project_id = project_id
    try:
        project = services.get_project(db, project_id)
        resolved_project_id = project.id
        await manager.connect(project.id, user_id, websocket)
        replay_stmt = select(models.RealtimeEvent).where(models.RealtimeEvent.project_id == project.id).order_by(models.RealtimeEvent.id)
        if last_event_id is not None:
            replay_stmt = replay_stmt.where(models.RealtimeEvent.id > last_event_id)
        for event in db.scalars(replay_stmt.limit(100)).all():
            await websocket.send_json(realtime_event_message(event, replay=True))
        await websocket.send_json({"type": "presence", "users": await manager.presence(project.id)})
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(resolved_project_id, user_id, websocket)
        db.close()
