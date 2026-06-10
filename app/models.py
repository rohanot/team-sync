from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(160))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    key: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    issue_counter: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    statuses: Mapped[list[WorkflowStatus]] = relationship(back_populates="project", cascade="all, delete-orphan")
    issues: Mapped[list[Issue]] = relationship(back_populates="project")


class ProjectMember(Base):
    __tablename__ = "project_members"
    __table_args__ = (UniqueConstraint("project_id", "user_id", name="uq_project_member_once"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(32), default="member", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped[User] = relationship()
    project: Mapped[Project] = relationship()


class WorkflowStatus(Base):
    __tablename__ = "workflow_statuses"
    __table_args__ = (UniqueConstraint("project_id", "name", name="uq_workflow_status_project_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    position: Mapped[int] = mapped_column(Integer, default=0)
    is_done: Mapped[bool] = mapped_column(Boolean, default=False)

    project: Mapped[Project] = relationship(back_populates="statuses")


class WorkflowTransition(Base):
    __tablename__ = "workflow_transitions"
    __table_args__ = (
        UniqueConstraint("project_id", "from_status_id", "to_status_id", name="uq_transition_once"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    from_status_id: Mapped[str] = mapped_column(ForeignKey("workflow_statuses.id", ondelete="CASCADE"))
    to_status_id: Mapped[str] = mapped_column(ForeignKey("workflow_statuses.id", ondelete="CASCADE"))

    from_status: Mapped[WorkflowStatus] = relationship(foreign_keys=[from_status_id])
    to_status: Mapped[WorkflowStatus] = relationship(foreign_keys=[to_status_id])


class Sprint(Base):
    __tablename__ = "sprints"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="planned", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Issue(Base):
    __tablename__ = "issues"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    issue_key: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(240), index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status_id: Mapped[str] = mapped_column(ForeignKey("workflow_statuses.id"), index=True)
    priority: Mapped[str] = mapped_column(String(32), default="medium", index=True)
    assignee_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    reporter_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    sprint_id: Mapped[str | None] = mapped_column(ForeignKey("sprints.id"), nullable=True, index=True)
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("issues.id"), nullable=True, index=True)
    labels: Mapped[list[str]] = mapped_column(JSON, default=list)
    story_points: Mapped[int | None] = mapped_column(Integer, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    project: Mapped[Project] = relationship(back_populates="issues")
    status: Mapped[WorkflowStatus] = relationship()
    assignee: Mapped[User | None] = relationship(foreign_keys=[assignee_id])
    reporter: Mapped[User] = relationship(foreign_keys=[reporter_id])
    sprint: Mapped[Sprint | None] = relationship()
    parent: Mapped[Issue | None] = relationship(remote_side=[id])


class CustomFieldDefinition(Base):
    __tablename__ = "custom_field_definitions"
    __table_args__ = (UniqueConstraint("project_id", "name", name="uq_custom_field_project_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    field_type: Mapped[str] = mapped_column(String(32))
    options: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    required: Mapped[bool] = mapped_column(Boolean, default=False)


class CustomFieldValue(Base):
    __tablename__ = "custom_field_values"
    __table_args__ = (UniqueConstraint("issue_id", "field_id", name="uq_custom_field_value_once"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    issue_id: Mapped[str] = mapped_column(ForeignKey("issues.id", ondelete="CASCADE"), index=True)
    field_id: Mapped[str] = mapped_column(ForeignKey("custom_field_definitions.id", ondelete="CASCADE"))
    value: Mapped[dict | list | str | int | float | None] = mapped_column(JSON, nullable=True)


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    issue_id: Mapped[str] = mapped_column(ForeignKey("issues.id", ondelete="CASCADE"), index=True)
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("comments.id"), nullable=True, index=True)
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    author: Mapped[User] = relationship()


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    issue_id: Mapped[str | None] = mapped_column(ForeignKey("issues.id", ondelete="SET NULL"), nullable=True, index=True)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=True)
    issue_id: Mapped[str | None] = mapped_column(ForeignKey("issues.id", ondelete="CASCADE"), nullable=True)
    type: Mapped[str] = mapped_column(String(64), index=True)
    message: Mapped[str] = mapped_column(String(500))
    read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class Watcher(Base):
    __tablename__ = "watchers"
    __table_args__ = (UniqueConstraint("issue_id", "user_id", name="uq_watcher_once"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    issue_id: Mapped[str] = mapped_column(ForeignKey("issues.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RealtimeEvent(Base):
    __tablename__ = "realtime_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    issue_id: Mapped[str | None] = mapped_column(ForeignKey("issues.id", ondelete="SET NULL"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


Index("ix_issues_search_title_description", Issue.title, Issue.description)
