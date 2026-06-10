"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-09
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("users", sa.Column("id", sa.String(36), primary_key=True), sa.Column("username", sa.String(80), nullable=False), sa.Column("display_name", sa.String(160), nullable=False), sa.Column("email", sa.String(255), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_table("projects", sa.Column("id", sa.String(36), primary_key=True), sa.Column("key", sa.String(16), nullable=False), sa.Column("name", sa.String(200), nullable=False), sa.Column("issue_counter", sa.Integer(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_projects_key", "projects", ["key"], unique=True)
    op.create_table("project_members", sa.Column("id", sa.String(36), primary_key=True), sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False), sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("role", sa.String(32), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("project_id", "user_id", name="uq_project_member_once"))
    op.create_index("ix_project_members_project_id", "project_members", ["project_id"])
    op.create_index("ix_project_members_user_id", "project_members", ["user_id"])
    op.create_index("ix_project_members_role", "project_members", ["role"])
    op.create_table("workflow_statuses", sa.Column("id", sa.String(36), primary_key=True), sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False), sa.Column("name", sa.String(80), nullable=False), sa.Column("position", sa.Integer(), nullable=False), sa.Column("is_done", sa.Boolean(), nullable=False), sa.UniqueConstraint("project_id", "name", name="uq_workflow_status_project_name"))
    op.create_index("ix_workflow_statuses_project_id", "workflow_statuses", ["project_id"])
    op.create_table("workflow_transitions", sa.Column("id", sa.String(36), primary_key=True), sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False), sa.Column("from_status_id", sa.String(36), sa.ForeignKey("workflow_statuses.id", ondelete="CASCADE"), nullable=False), sa.Column("to_status_id", sa.String(36), sa.ForeignKey("workflow_statuses.id", ondelete="CASCADE"), nullable=False), sa.UniqueConstraint("project_id", "from_status_id", "to_status_id", name="uq_transition_once"))
    op.create_index("ix_workflow_transitions_project_id", "workflow_transitions", ["project_id"])
    op.create_table("sprints", sa.Column("id", sa.String(36), primary_key=True), sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False), sa.Column("name", sa.String(160), nullable=False), sa.Column("start_date", sa.Date(), nullable=True), sa.Column("end_date", sa.Date(), nullable=True), sa.Column("status", sa.String(32), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_sprints_project_id", "sprints", ["project_id"])
    op.create_index("ix_sprints_status", "sprints", ["status"])
    op.create_table("issues", sa.Column("id", sa.String(36), primary_key=True), sa.Column("issue_key", sa.String(32), nullable=False), sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False), sa.Column("type", sa.String(32), nullable=False), sa.Column("title", sa.String(240), nullable=False), sa.Column("description", sa.Text(), nullable=True), sa.Column("status_id", sa.String(36), sa.ForeignKey("workflow_statuses.id"), nullable=False), sa.Column("priority", sa.String(32), nullable=False), sa.Column("assignee_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True), sa.Column("reporter_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False), sa.Column("sprint_id", sa.String(36), sa.ForeignKey("sprints.id"), nullable=True), sa.Column("parent_id", sa.String(36), sa.ForeignKey("issues.id"), nullable=True), sa.Column("labels", sa.JSON(), nullable=False), sa.Column("story_points", sa.Integer(), nullable=True), sa.Column("version", sa.Integer(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    for column in ["issue_key", "project_id", "type", "title", "status_id", "priority", "assignee_id", "reporter_id", "sprint_id", "parent_id"]:
        op.create_index(f"ix_issues_{column}", "issues", [column], unique=column == "issue_key")
    op.create_table("custom_field_definitions", sa.Column("id", sa.String(36), primary_key=True), sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False), sa.Column("name", sa.String(120), nullable=False), sa.Column("field_type", sa.String(32), nullable=False), sa.Column("options", sa.JSON(), nullable=True), sa.Column("required", sa.Boolean(), nullable=False), sa.UniqueConstraint("project_id", "name", name="uq_custom_field_project_name"))
    op.create_index("ix_custom_field_definitions_project_id", "custom_field_definitions", ["project_id"])
    op.create_table("custom_field_values", sa.Column("id", sa.String(36), primary_key=True), sa.Column("issue_id", sa.String(36), sa.ForeignKey("issues.id", ondelete="CASCADE"), nullable=False), sa.Column("field_id", sa.String(36), sa.ForeignKey("custom_field_definitions.id", ondelete="CASCADE"), nullable=False), sa.Column("value", sa.JSON(), nullable=True), sa.UniqueConstraint("issue_id", "field_id", name="uq_custom_field_value_once"))
    op.create_index("ix_custom_field_values_issue_id", "custom_field_values", ["issue_id"])
    op.create_table("comments", sa.Column("id", sa.String(36), primary_key=True), sa.Column("issue_id", sa.String(36), sa.ForeignKey("issues.id", ondelete="CASCADE"), nullable=False), sa.Column("author_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False), sa.Column("parent_id", sa.String(36), sa.ForeignKey("comments.id"), nullable=True), sa.Column("body", sa.Text(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    for column in ["issue_id", "author_id", "parent_id"]:
        op.create_index(f"ix_comments_{column}", "comments", [column])
    op.create_table("activity_logs", sa.Column("id", sa.String(36), primary_key=True), sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False), sa.Column("issue_id", sa.String(36), sa.ForeignKey("issues.id", ondelete="SET NULL"), nullable=True), sa.Column("actor_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True), sa.Column("action", sa.String(80), nullable=False), sa.Column("details", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    for column in ["project_id", "issue_id", "actor_id", "action", "created_at"]:
        op.create_index(f"ix_activity_logs_{column}", "activity_logs", [column])
    op.create_table("notifications", sa.Column("id", sa.String(36), primary_key=True), sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=True), sa.Column("issue_id", sa.String(36), sa.ForeignKey("issues.id", ondelete="CASCADE"), nullable=True), sa.Column("type", sa.String(64), nullable=False), sa.Column("message", sa.String(500), nullable=False), sa.Column("read", sa.Boolean(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    for column in ["user_id", "type", "read", "created_at"]:
        op.create_index(f"ix_notifications_{column}", "notifications", [column])
    op.create_table("watchers", sa.Column("id", sa.String(36), primary_key=True), sa.Column("issue_id", sa.String(36), sa.ForeignKey("issues.id", ondelete="CASCADE"), nullable=False), sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("issue_id", "user_id", name="uq_watcher_once"))
    op.create_index("ix_watchers_issue_id", "watchers", ["issue_id"])
    op.create_index("ix_watchers_user_id", "watchers", ["user_id"])
    op.create_table("realtime_events", sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True), sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False), sa.Column("issue_id", sa.String(36), sa.ForeignKey("issues.id", ondelete="SET NULL"), nullable=True), sa.Column("event_type", sa.String(64), nullable=False), sa.Column("payload", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    for column in ["project_id", "issue_id", "event_type", "created_at"]:
        op.create_index(f"ix_realtime_events_{column}", "realtime_events", [column])


def downgrade() -> None:
    for table in ["realtime_events", "watchers", "notifications", "activity_logs", "comments", "custom_field_values", "custom_field_definitions", "issues", "sprints", "workflow_transitions", "workflow_statuses", "project_members", "projects", "users"]:
        op.drop_table(table)
