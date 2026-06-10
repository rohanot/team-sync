from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class UserRead(BaseModel):
    id: str
    username: str
    display_name: str
    email: str

    model_config = ConfigDict(from_attributes=True)


class ProjectRead(BaseModel):
    id: str
    key: str
    name: str

    model_config = ConfigDict(from_attributes=True)


class ProjectMembershipRead(BaseModel):
    project_id: str
    project_key: str
    role: str


class SessionRead(BaseModel):
    user: UserRead
    memberships: list[ProjectMembershipRead]


class StatusRead(BaseModel):
    id: str
    name: str
    position: int
    is_done: bool

    model_config = ConfigDict(from_attributes=True)


class SprintRead(BaseModel):
    id: str
    project_id: str
    name: str
    start_date: date | None
    end_date: date | None
    status: str
    completed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class IssueCreate(BaseModel):
    type: str = Field(pattern="^(epic|story|task|bug|sub_task)$")
    title: str = Field(min_length=1, max_length=240)
    description: str | None = None
    status: str | None = None
    priority: str = "medium"
    assignee_id: str | None = None
    reporter_id: str | None = None
    sprint_id: str | None = None
    parent_id: str | None = None
    labels: list[str] = Field(default_factory=list)
    story_points: int | None = Field(default=None, ge=0)
    custom_fields: dict[str, Any] = Field(default_factory=dict)


class IssueUpdate(BaseModel):
    expected_version: int | None = Field(default=None, ge=1)
    title: str | None = Field(default=None, min_length=1, max_length=240)
    description: str | None = None
    priority: str | None = None
    assignee_id: str | None = None
    sprint_id: str | None = None
    labels: list[str] | None = None
    story_points: int | None = Field(default=None, ge=0)


class TransitionRequest(BaseModel):
    to_status: str
    expected_version: int | None = Field(default=None, ge=1)


class IssueRead(BaseModel):
    id: str
    issue_key: str
    project_id: str
    type: str
    title: str
    description: str | None
    status: str
    priority: str
    assignee: UserRead | None
    reporter: UserRead
    sprint: SprintRead | None
    parent_id: str | None
    labels: list[str]
    story_points: int | None
    watchers: list[str]
    version: int
    created_at: datetime
    updated_at: datetime


class BoardColumn(BaseModel):
    status: StatusRead
    issues: list[IssueRead]


class BoardRead(BaseModel):
    project: ProjectRead
    columns: list[BoardColumn]


class SprintCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    start_date: date | None = None
    end_date: date | None = None


class SprintUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    start_date: date | None = None
    end_date: date | None = None
    status: str | None = Field(default=None, pattern="^(planned|active|completed)$")


class SprintCompleteRequest(BaseModel):
    carry_over_issue_ids: list[str] = Field(default_factory=list)
    next_sprint_id: str | None = None


class SprintCompleteRead(BaseModel):
    sprint: SprintRead
    completed: list[IssueRead]
    incomplete: list[IssueRead]
    carried_over: list[IssueRead]
    velocity: int


class CommentCreate(BaseModel):
    body: str = Field(min_length=1)
    parent_id: str | None = None


class CommentUpdate(BaseModel):
    body: str = Field(min_length=1)


class CommentRead(BaseModel):
    id: str
    issue_id: str
    author: UserRead
    parent_id: str | None
    body: str
    created_at: datetime
    updated_at: datetime


class ActivityRead(BaseModel):
    id: str
    project_id: str
    issue_id: str | None
    actor_id: str | None
    action: str
    details: dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationRead(BaseModel):
    id: str
    user_id: str
    project_id: str | None
    issue_id: str | None
    type: str
    message: str
    read: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SearchRead(BaseModel):
    results: list[IssueRead]
    next_cursor: str | None


class ErrorRead(BaseModel):
    error: dict[str, Any]
