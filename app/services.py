from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import and_, desc, func, or_, select, update
from sqlalchemy.orm import Session, joinedload

from app import models, schemas

MENTION_RE = re.compile(r"@([A-Za-z0-9_.-]+)")
LAST_REALTIME_EVENT_KEY = "teamsync_last_realtime_event"


def not_found(name: str) -> HTTPException:
    return HTTPException(status_code=404, detail={"code": "not_found", "message": f"{name} not found"})


def issue_to_read(db: Session, issue: models.Issue) -> schemas.IssueRead:
    watchers = db.scalars(select(models.Watcher.user_id).where(models.Watcher.issue_id == issue.id)).all()
    return schemas.IssueRead(
        id=issue.id,
        issue_key=issue.issue_key,
        project_id=issue.project_id,
        type=issue.type,
        title=issue.title,
        description=issue.description,
        status=issue.status.name,
        priority=issue.priority,
        assignee=schemas.UserRead.model_validate(issue.assignee) if issue.assignee else None,
        reporter=schemas.UserRead.model_validate(issue.reporter),
        sprint=schemas.SprintRead.model_validate(issue.sprint) if issue.sprint else None,
        parent_id=issue.parent_id,
        labels=issue.labels or [],
        story_points=issue.story_points,
        watchers=list(watchers),
        version=issue.version,
        created_at=issue.created_at,
        updated_at=issue.updated_at,
    )


def get_project(db: Session, project_id: str) -> models.Project:
    project = db.get(models.Project, project_id)
    if project is None:
        project = db.scalar(select(models.Project).where(models.Project.key == project_id))
    if project is None:
        raise not_found("project")
    return project


def get_user(db: Session, user_id: str | None) -> models.User:
    if user_id:
        user = db.get(models.User, user_id)
        if user is None:
            user = db.scalar(select(models.User).where(models.User.username == user_id))
        if user:
            return user
    user = db.scalar(select(models.User).order_by(models.User.created_at))
    if user is None:
        raise not_found("user")
    return user


def get_issue(db: Session, issue_id: str) -> models.Issue:
    issue = db.scalar(
        select(models.Issue)
        .options(
            joinedload(models.Issue.status),
            joinedload(models.Issue.assignee),
            joinedload(models.Issue.reporter),
            joinedload(models.Issue.sprint),
        )
        .execution_options(populate_existing=True)
        .where(or_(models.Issue.id == issue_id, models.Issue.issue_key == issue_id))
    )
    if issue is None:
        raise not_found("issue")
    return issue


def conflict(expected_version: int | None, current_version: int | None) -> HTTPException:
    detail: dict[str, Any] = {
        "code": "version_conflict",
        "message": "Issue was updated by another request",
        "expected_version": expected_version,
    }
    if current_version is not None:
        detail["current_version"] = current_version
    return HTTPException(status_code=409, detail=detail)


def validate_sprint_dates(start_date: date | None, end_date: date | None) -> None:
    if start_date and end_date and end_date < start_date:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_sprint_dates", "message": "end_date must be on or after start_date"},
        )


def validate_issue_sprint(db: Session, project_id: str, sprint_id: str | None) -> models.Sprint | None:
    if sprint_id is None:
        return None
    sprint = db.get(models.Sprint, sprint_id)
    if sprint is None:
        raise not_found("sprint")
    if sprint.project_id != project_id or sprint.status == "completed":
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_sprint", "message": "sprint must be open and belong to the issue project"},
        )
    return sprint


def validate_single_active_sprint(db: Session, project_id: str, sprint_id: str, status: str | None) -> None:
    if status != "active":
        return
    existing = db.scalar(
        select(models.Sprint).where(
            models.Sprint.project_id == project_id,
            models.Sprint.status == "active",
            models.Sprint.id != sprint_id,
        )
    )
    if existing:
        raise HTTPException(
            status_code=422,
            detail={"code": "active_sprint_exists", "message": "Only one sprint can be active per project"},
        )


def allocate_issue_key(db: Session, project: models.Project) -> str:
    bind = db.get_bind()
    dialect_name = bind.dialect.name if bind is not None else ""
    if dialect_name == "postgresql":
        locked_project = db.scalar(select(models.Project).where(models.Project.id == project.id).with_for_update())
        if locked_project is None:
            raise not_found("project")
        locked_project.issue_counter += 1
        db.flush()
        return f"{locked_project.key}-{locked_project.issue_counter}"

    result = db.execute(
        update(models.Project)
        .where(models.Project.id == project.id)
        .values(issue_counter=models.Project.issue_counter + 1)
        .returning(models.Project.issue_counter)
    )
    next_counter = result.scalar_one_or_none()
    if next_counter is None:
        raise not_found("project")
    project.issue_counter = next_counter
    return f"{project.key}-{next_counter}"


def validate_parent_hierarchy(db: Session, issue_type: str, parent_id: str | None) -> None:
    if issue_type == "epic" and parent_id is not None:
        raise HTTPException(status_code=422, detail={"code": "invalid_parent", "message": "Epic issues cannot have a parent"})
    if issue_type in {"story", "sub_task"} and parent_id is None:
        return
    if issue_type in {"task", "bug"} and parent_id is None:
        return
    if parent_id is None:
        return
    parent = db.get(models.Issue, parent_id)
    if parent is None:
        raise not_found("parent issue")
    allowed: dict[str, set[str]] = {
        "story": {"epic"},
        "sub_task": {"story", "task"},
        "task": {"story", "epic"},
        "bug": {"story", "epic"},
    }
    if parent.type not in allowed.get(issue_type, set()):
        raise HTTPException(
            status_code=422,
            detail={
                "code": "invalid_parent",
                "message": f"{issue_type} cannot be a child of {parent.type}",
                "allowed_parent_types": sorted(allowed.get(issue_type, set())),
            },
        )


def validate_and_store_custom_fields(db: Session, issue: models.Issue, values: dict[str, Any]) -> None:
    definitions = list(
        db.scalars(select(models.CustomFieldDefinition).where(models.CustomFieldDefinition.project_id == issue.project_id))
    )
    by_name = {definition.name: definition for definition in definitions}
    by_id = {definition.id: definition for definition in definitions}
    for definition in definitions:
        if definition.required and definition.name not in values and definition.id not in values:
            raise HTTPException(
                status_code=422,
                detail={"code": "missing_custom_field", "message": f"Custom field '{definition.name}' is required"},
            )
    for field_name, value in values.items():
        definition = by_name.get(field_name) or by_id.get(field_name)
        if definition is None:
            raise HTTPException(status_code=422, detail={"code": "unknown_custom_field", "message": f"Unknown custom field: {field_name}"})
        validate_custom_field_value(definition, value)
        db.add(models.CustomFieldValue(issue_id=issue.id, field_id=definition.id, value=value))


def validate_custom_field_value(definition: models.CustomFieldDefinition, value: Any) -> None:
    invalid = HTTPException(
        status_code=422,
        detail={
            "code": "invalid_custom_field_value",
            "message": f"Custom field '{definition.name}' requires a valid {definition.field_type} value",
        },
    )
    if value is None:
        return
    if definition.field_type in {"text", "string"}:
        if not isinstance(value, str):
            raise invalid
        return
    if definition.field_type in {"number", "integer"}:
        if isinstance(value, bool) or not isinstance(value, int if definition.field_type == "integer" else (int, float)):
            raise invalid
        return
    if definition.field_type in {"dropdown", "select"}:
        if not isinstance(value, str) or value not in (definition.options or []):
            raise invalid
        return
    if definition.field_type == "date":
        if not isinstance(value, str):
            raise invalid
        try:
            date.fromisoformat(value)
        except ValueError:
            raise invalid from None


def status_by_name(db: Session, project_id: str, name: str | None) -> models.WorkflowStatus:
    stmt = select(models.WorkflowStatus).where(models.WorkflowStatus.project_id == project_id)
    if name:
        stmt = stmt.where(func.lower(models.WorkflowStatus.name) == name.lower())
    else:
        stmt = stmt.order_by(models.WorkflowStatus.position)
    status = db.scalar(stmt)
    if status is None:
        raise HTTPException(status_code=422, detail={"code": "invalid_status", "message": "status is not configured"})
    return status


def add_activity(
    db: Session,
    project_id: str,
    action: str,
    actor_id: str | None,
    issue_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> models.ActivityLog:
    activity = models.ActivityLog(
        project_id=project_id,
        issue_id=issue_id,
        actor_id=actor_id,
        action=action,
        details=details or {},
    )
    db.add(activity)
    return activity


def add_notification(
    db: Session,
    user_id: str | None,
    notification_type: str,
    message: str,
    project_id: str | None = None,
    issue_id: str | None = None,
) -> None:
    if not user_id:
        return
    db.add(
        models.Notification(
            user_id=user_id,
            project_id=project_id,
            issue_id=issue_id,
            type=notification_type,
            message=message,
        )
    )


def add_realtime_event(
    db: Session,
    project_id: str,
    event_type: str,
    payload: dict[str, Any],
    issue_id: str | None = None,
) -> models.RealtimeEvent:
    event = models.RealtimeEvent(project_id=project_id, issue_id=issue_id, event_type=event_type, payload=payload)
    db.add(event)
    db.flush()
    db.info[LAST_REALTIME_EVENT_KEY] = event
    return event


def consume_last_realtime_event(db: Session) -> models.RealtimeEvent | None:
    return db.info.pop(LAST_REALTIME_EVENT_KEY, None)


def create_issue(db: Session, project_id: str, data: schemas.IssueCreate, actor_id: str | None) -> models.Issue:
    project = get_project(db, project_id)
    reporter = get_user(db, data.reporter_id or actor_id)
    status = status_by_name(db, project.id, data.status)
    if data.assignee_id:
        get_user(db, data.assignee_id)
    validate_issue_sprint(db, project.id, data.sprint_id)
    validate_parent_hierarchy(db, data.type, data.parent_id)

    issue_key = allocate_issue_key(db, project)
    issue = models.Issue(
        issue_key=issue_key,
        project_id=project.id,
        type=data.type,
        title=data.title,
        description=data.description,
        status_id=status.id,
        priority=data.priority,
        assignee_id=data.assignee_id,
        reporter_id=reporter.id,
        sprint_id=data.sprint_id,
        parent_id=data.parent_id,
        labels=data.labels,
        story_points=data.story_points,
    )
    db.add(issue)
    db.flush()
    validate_and_store_custom_fields(db, issue, data.custom_fields)
    add_activity(db, project.id, "issue_created", actor_id or reporter.id, issue.id, {"issue_key": issue.issue_key})
    add_realtime_event(db, project.id, "issue_created", {"issue_id": issue.id, "issue_key": issue.issue_key}, issue.id)
    if issue.assignee_id:
        add_notification(db, issue.assignee_id, "assignment", f"You were assigned {issue.issue_key}", project.id, issue.id)
    db.commit()
    db.refresh(issue)
    return get_issue(db, issue.id)


def board(db: Session, project_id: str) -> schemas.BoardRead:
    project = get_project(db, project_id)
    statuses = db.scalars(
        select(models.WorkflowStatus).where(models.WorkflowStatus.project_id == project.id).order_by(models.WorkflowStatus.position)
    ).all()
    issues = db.scalars(
        select(models.Issue)
        .options(
            joinedload(models.Issue.status),
            joinedload(models.Issue.assignee),
            joinedload(models.Issue.reporter),
            joinedload(models.Issue.sprint),
        )
        .where(models.Issue.project_id == project.id)
        .order_by(models.Issue.created_at)
    ).all()
    by_status: dict[str, list[models.Issue]] = {status.id: [] for status in statuses}
    for issue in issues:
        by_status.setdefault(issue.status_id, []).append(issue)
    return schemas.BoardRead(
        project=schemas.ProjectRead.model_validate(project),
        columns=[
            schemas.BoardColumn(
                status=schemas.StatusRead.model_validate(status),
                issues=[issue_to_read(db, issue) for issue in by_status.get(status.id, [])],
            )
            for status in statuses
        ],
    )


def update_issue(db: Session, issue_id: str, data: schemas.IssueUpdate, actor_id: str | None) -> models.Issue:
    issue = get_issue(db, issue_id)
    if data.expected_version is not None and data.expected_version != issue.version:
        raise conflict(data.expected_version, issue.version)
    changes: dict[str, Any] = {}
    values: dict[str, Any] = {}
    for field in ["title", "description", "priority", "assignee_id", "sprint_id", "labels", "story_points"]:
        value = getattr(data, field)
        if value is not None and getattr(issue, field) != value:
            if field == "sprint_id":
                validate_issue_sprint(db, issue.project_id, value)
            changes[field] = {"from": getattr(issue, field), "to": value}
            values[field] = value
    if "assignee_id" in changes:
        get_user(db, values["assignee_id"])
    if changes:
        updated_at = models.utcnow()
        if data.expected_version is not None:
            result = db.execute(
                update(models.Issue)
                .where(models.Issue.id == issue.id, models.Issue.version == data.expected_version)
                .values(**values, version=models.Issue.version + 1, updated_at=updated_at)
            )
            if result.rowcount != 1:
                db.rollback()
                current_version = db.scalar(select(models.Issue.version).where(models.Issue.id == issue.id))
                raise conflict(data.expected_version, current_version)
        else:
            for field, value in values.items():
                setattr(issue, field, value)
            issue.version += 1
            issue.updated_at = updated_at
        if "assignee_id" in changes:
            add_notification(db, values["assignee_id"], "assignment", f"You were assigned {issue.issue_key}", issue.project_id, issue.id)
        add_activity(db, issue.project_id, "issue_updated", actor_id, issue.id, {"changes": changes})
        add_realtime_event(db, issue.project_id, "issue_updated", {"issue_id": issue.id, "changes": changes}, issue.id)
    db.commit()
    return get_issue(db, issue.id)


def allowed_transition_names(db: Session, issue: models.Issue) -> list[str]:
    return list(
        db.scalars(
            select(models.WorkflowStatus.name)
            .join(models.WorkflowTransition, models.WorkflowTransition.to_status_id == models.WorkflowStatus.id)
            .where(models.WorkflowTransition.from_status_id == issue.status_id)
            .order_by(models.WorkflowStatus.position)
        ).all()
    )


def transition_issue(db: Session, issue_id: str, data: schemas.TransitionRequest, actor_id: str | None) -> models.Issue:
    issue = get_issue(db, issue_id)
    if data.expected_version is not None and data.expected_version != issue.version:
        raise conflict(data.expected_version, issue.version)
    target = status_by_name(db, issue.project_id, data.to_status)
    transition = db.scalar(
        select(models.WorkflowTransition).where(
            and_(
                models.WorkflowTransition.project_id == issue.project_id,
                models.WorkflowTransition.from_status_id == issue.status_id,
                models.WorkflowTransition.to_status_id == target.id,
            )
        )
    )
    if transition is None:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "workflow_violation",
                "message": f"Cannot move issue from {issue.status.name} to {target.name}",
                "current_status": issue.status.name,
                "requested_status": target.name,
                "allowed_transitions": allowed_transition_names(db, issue),
            },
        )
    if target.is_done and issue.type in {"story", "task"} and issue.story_points is None:
        raise HTTPException(
            status_code=422,
            detail={"code": "missing_story_points", "message": "story_points is required before moving this issue to Done"},
        )
    previous = issue.status.name
    updated_at = models.utcnow()
    if data.expected_version is not None:
        result = db.execute(
            update(models.Issue)
            .where(models.Issue.id == issue.id, models.Issue.version == data.expected_version)
            .values(status_id=target.id, version=models.Issue.version + 1, updated_at=updated_at)
        )
        if result.rowcount != 1:
            db.rollback()
            current_version = db.scalar(select(models.Issue.version).where(models.Issue.id == issue.id))
            raise conflict(data.expected_version, current_version)
    else:
        issue.status_id = target.id
        issue.version += 1
        issue.updated_at = updated_at
    add_activity(db, issue.project_id, "issue_moved", actor_id, issue.id, {"from": previous, "to": target.name})
    add_realtime_event(db, issue.project_id, "issue_moved", {"issue_id": issue.id, "from": previous, "to": target.name}, issue.id)
    if target.name.lower() == "in review":
        add_notification(db, issue.assignee_id or issue.reporter_id, "status_change", f"{issue.issue_key} moved to In Review", issue.project_id, issue.id)
    if target.is_done:
        for watcher_id in db.scalars(select(models.Watcher.user_id).where(models.Watcher.issue_id == issue.id)):
            add_notification(db, watcher_id, "status_change", f"{issue.issue_key} moved to Done", issue.project_id, issue.id)
    db.commit()
    return get_issue(db, issue.id)


def create_sprint(db: Session, project_id: str, data: schemas.SprintCreate, actor_id: str | None) -> models.Sprint:
    project = get_project(db, project_id)
    validate_sprint_dates(data.start_date, data.end_date)
    sprint = models.Sprint(project_id=project.id, name=data.name, start_date=data.start_date, end_date=data.end_date)
    db.add(sprint)
    db.flush()
    add_activity(db, project.id, "sprint_created", actor_id, None, {"sprint_id": sprint.id, "name": sprint.name})
    add_realtime_event(db, project.id, "sprint_updated", {"sprint_id": sprint.id, "action": "created"})
    db.commit()
    return sprint


def update_sprint(db: Session, sprint_id: str, data: schemas.SprintUpdate, actor_id: str | None) -> models.Sprint:
    sprint = db.get(models.Sprint, sprint_id)
    if sprint is None:
        raise not_found("sprint")
    start_date = data.start_date if data.start_date is not None else sprint.start_date
    end_date = data.end_date if data.end_date is not None else sprint.end_date
    validate_sprint_dates(start_date, end_date)
    validate_single_active_sprint(db, sprint.project_id, sprint.id, data.status)
    for field in ["name", "start_date", "end_date", "status"]:
        value = getattr(data, field)
        if value is not None:
            setattr(sprint, field, value)
    add_activity(db, sprint.project_id, "sprint_updated", actor_id, None, {"sprint_id": sprint.id})
    add_realtime_event(db, sprint.project_id, "sprint_updated", {"sprint_id": sprint.id, "action": "updated"})
    db.commit()
    return sprint


def complete_sprint(db: Session, sprint_id: str, data: schemas.SprintCompleteRequest, actor_id: str | None) -> schemas.SprintCompleteRead:
    sprint = db.get(models.Sprint, sprint_id)
    if sprint is None:
        raise not_found("sprint")
    issues = db.scalars(
        select(models.Issue)
        .options(joinedload(models.Issue.status), joinedload(models.Issue.assignee), joinedload(models.Issue.reporter), joinedload(models.Issue.sprint))
        .where(models.Issue.sprint_id == sprint.id)
    ).all()
    completed = [issue for issue in issues if issue.status.is_done]
    incomplete = [issue for issue in issues if not issue.status.is_done]
    carry_ids = set(data.carry_over_issue_ids)
    carried = [issue for issue in incomplete if issue.id in carry_ids or issue.issue_key in carry_ids]
    next_sprint = db.get(models.Sprint, data.next_sprint_id) if data.next_sprint_id else None
    if data.next_sprint_id and next_sprint is None:
        raise not_found("next sprint")
    if next_sprint and (next_sprint.project_id != sprint.project_id or next_sprint.status == "completed"):
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_next_sprint", "message": "next_sprint_id must belong to the same project and be open"},
        )
    unknown_carry_ids = carry_ids - {issue.id for issue in incomplete} - {issue.issue_key for issue in incomplete}
    if unknown_carry_ids:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_carry_over_issue", "message": "carry-over issues must be incomplete issues in this sprint"},
        )
    for issue in carried:
        issue.sprint_id = next_sprint.id if next_sprint else None
        issue.version += 1
        add_activity(db, sprint.project_id, "issue_carried_over", actor_id, issue.id, {"from_sprint_id": sprint.id, "to_sprint_id": data.next_sprint_id})
    sprint.status = "completed"
    sprint.completed_at = models.utcnow()
    db.flush()
    if next_sprint is not None:
        validate_single_active_sprint(db, sprint.project_id, next_sprint.id, "active")
        next_sprint.status = "active"
    velocity = sum(issue.story_points or 0 for issue in completed)
    add_activity(db, sprint.project_id, "sprint_completed", actor_id, None, {"sprint_id": sprint.id, "velocity": velocity})
    add_realtime_event(db, sprint.project_id, "sprint_updated", {"sprint_id": sprint.id, "action": "completed", "velocity": velocity})
    if next_sprint is not None:
        add_activity(db, sprint.project_id, "sprint_updated", actor_id, None, {"sprint_id": next_sprint.id, "action": "activated"})
        add_realtime_event(db, sprint.project_id, "sprint_updated", {"sprint_id": next_sprint.id, "action": "activated"})
    db.commit()
    refreshed_completed = [get_issue(db, issue.id) for issue in completed]
    refreshed_incomplete = [get_issue(db, issue.id) for issue in incomplete]
    refreshed_carried = [get_issue(db, issue.id) for issue in carried]
    return schemas.SprintCompleteRead(
        sprint=schemas.SprintRead.model_validate(sprint),
        completed=[issue_to_read(db, issue) for issue in refreshed_completed],
        incomplete=[issue_to_read(db, issue) for issue in refreshed_incomplete],
        carried_over=[issue_to_read(db, issue) for issue in refreshed_carried],
        velocity=velocity,
    )


def create_comment(db: Session, issue_id: str, data: schemas.CommentCreate, actor_id: str | None) -> models.Comment:
    issue = get_issue(db, issue_id)
    author = get_user(db, actor_id)
    if data.parent_id:
        parent = db.get(models.Comment, data.parent_id)
        if parent is None:
            raise not_found("parent comment")
        if parent.issue_id != issue.id:
            raise HTTPException(
                status_code=422,
                detail={"code": "invalid_comment_parent", "message": "parent comment must belong to the same issue"},
            )
    comment = models.Comment(issue_id=issue.id, author_id=author.id, parent_id=data.parent_id, body=data.body)
    db.add(comment)
    db.flush()
    mentioned = set(MENTION_RE.findall(data.body))
    for username in mentioned:
        user = db.scalar(select(models.User).where(models.User.username == username))
        if user:
            add_notification(db, user.id, "mention", f"{author.display_name} mentioned you on {issue.issue_key}", issue.project_id, issue.id)
    for watcher_id in db.scalars(select(models.Watcher.user_id).where(models.Watcher.issue_id == issue.id)):
        if watcher_id != author.id:
            add_notification(db, watcher_id, "comment", f"New comment on {issue.issue_key}", issue.project_id, issue.id)
    add_activity(db, issue.project_id, "comment_added", author.id, issue.id, {"comment_id": comment.id})
    add_realtime_event(db, issue.project_id, "comment_added", {"issue_id": issue.id, "comment_id": comment.id}, issue.id)
    db.commit()
    return comment


def update_comment(db: Session, comment_id: str, data: schemas.CommentUpdate, actor_id: str | None) -> models.Comment:
    comment = db.get(models.Comment, comment_id)
    if comment is None:
        raise not_found("comment")
    issue = get_issue(db, comment.issue_id)
    comment.body = data.body
    comment.updated_at = models.utcnow()
    add_activity(db, issue.project_id, "comment_updated", actor_id, issue.id, {"comment_id": comment.id})
    add_realtime_event(db, issue.project_id, "comment_added", {"issue_id": issue.id, "comment_id": comment.id, "action": "updated"}, issue.id)
    db.commit()
    return comment


def delete_comment(db: Session, comment_id: str, actor_id: str | None) -> None:
    comment = db.get(models.Comment, comment_id)
    if comment is None:
        raise not_found("comment")
    issue = get_issue(db, comment.issue_id)
    add_activity(db, issue.project_id, "comment_deleted", actor_id, issue.id, {"comment_id": comment.id})
    db.delete(comment)
    add_realtime_event(db, issue.project_id, "comment_added", {"issue_id": issue.id, "comment_id": comment.id, "action": "deleted"}, issue.id)
    db.commit()


def watch_issue(db: Session, issue_id: str, user_id: str) -> None:
    issue = get_issue(db, issue_id)
    user = get_user(db, user_id)
    existing = db.scalar(select(models.Watcher).where(and_(models.Watcher.issue_id == issue.id, models.Watcher.user_id == user.id)))
    if existing is None:
        db.add(models.Watcher(issue_id=issue.id, user_id=user.id))
        add_activity(db, issue.project_id, "issue_watched", user.id, issue.id, {})
    db.commit()


def unwatch_issue(db: Session, issue_id: str, user_id: str) -> None:
    issue = get_issue(db, issue_id)
    user = get_user(db, user_id)
    existing = db.scalar(select(models.Watcher).where(and_(models.Watcher.issue_id == issue.id, models.Watcher.user_id == user.id)))
    if existing:
        db.delete(existing)
        add_activity(db, issue.project_id, "issue_unwatched", user.id, issue.id, {})
    db.commit()


def search_issues(
    db: Session,
    q: str | None,
    project_id: str | None,
    status: str | None,
    assignee_id: str | None,
    priority: str | None,
    issue_type: str | None,
    sprint_id: str | None,
    cursor: str | None,
    limit: int,
) -> schemas.SearchRead:
    stmt = (
        select(models.Issue)
        .options(joinedload(models.Issue.status), joinedload(models.Issue.assignee), joinedload(models.Issue.reporter), joinedload(models.Issue.sprint))
        .join(models.WorkflowStatus, models.WorkflowStatus.id == models.Issue.status_id)
        .order_by(desc(models.Issue.created_at), models.Issue.id)
    )
    if q:
        like = f"%{q}%"
        comment_issue_ids = select(models.Comment.issue_id).where(models.Comment.body.ilike(like))
        stmt = stmt.where(or_(models.Issue.title.ilike(like), models.Issue.description.ilike(like), models.Issue.id.in_(comment_issue_ids)))
    if project_id:
        project = get_project(db, project_id)
        stmt = stmt.where(models.Issue.project_id == project.id)
    if status:
        stmt = stmt.where(func.lower(models.WorkflowStatus.name) == status.lower())
    if assignee_id:
        stmt = stmt.where(models.Issue.assignee_id == assignee_id)
    if priority:
        stmt = stmt.where(func.lower(models.Issue.priority) == priority.lower())
    if issue_type:
        stmt = stmt.where(models.Issue.type == issue_type)
    if sprint_id:
        stmt = stmt.where(models.Issue.sprint_id == sprint_id)
    if cursor:
        try:
            created_text, last_id = cursor.split("|", 1)
            created_at = datetime.fromisoformat(created_text)
            stmt = stmt.where(or_(models.Issue.created_at < created_at, and_(models.Issue.created_at == created_at, models.Issue.id > last_id)))
        except ValueError:
            raise HTTPException(status_code=422, detail={"code": "invalid_cursor", "message": "cursor is invalid"}) from None
    rows = db.scalars(stmt.limit(min(limit, 100) + 1)).all()
    page = rows[:limit]
    next_cursor = None
    if len(rows) > limit and page:
        last = page[-1]
        next_cursor = f"{last.created_at.isoformat()}|{last.id}"
    return schemas.SearchRead(results=[issue_to_read(db, issue) for issue in page], next_cursor=next_cursor)
