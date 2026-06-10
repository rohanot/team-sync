from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models


def seed_demo_data(db: Session) -> None:
    project = db.scalar(select(models.Project).where(models.Project.key == "TS"))

    # Make sure users exist
    users = []
    for username, display_name, email in [
        ("jane", "Jane Smith", "jane@teamsync.local"),
        ("bob", "Bob Chen", "bob@teamsync.local"),
        ("maya", "Maya Patel", "maya@teamsync.local"),
    ]:
        user = db.scalar(select(models.User).where(models.User.username == username))
        if not user:
            user = models.User(username=username, display_name=display_name, email=email)
            db.add(user)
            db.flush()
        users.append(user)

    if project:
        # If project exists, check if project members exist. If not, seed them.
        if db.scalar(select(models.ProjectMember).where(models.ProjectMember.project_id == project.id)) is None:
            db.add_all(
                [
                    models.ProjectMember(project_id=project.id, user_id=users[0].id, role="admin"),
                    models.ProjectMember(project_id=project.id, user_id=users[1].id, role="member"),
                    models.ProjectMember(project_id=project.id, user_id=users[2].id, role="viewer"),
                ]
            )
            db.commit()
        return

    project = models.Project(key="TS", name="TeamSync Platform")
    db.add(project)
    db.flush()
    db.add_all(
        [
            models.ProjectMember(project_id=project.id, user_id=users[0].id, role="admin"),
            models.ProjectMember(project_id=project.id, user_id=users[1].id, role="member"),
            models.ProjectMember(project_id=project.id, user_id=users[2].id, role="viewer"),
        ]
    )

    statuses = [
        models.WorkflowStatus(project_id=project.id, name="Backlog", position=0),
        models.WorkflowStatus(project_id=project.id, name="To Do", position=1),
        models.WorkflowStatus(project_id=project.id, name="In Progress", position=2),
        models.WorkflowStatus(project_id=project.id, name="In Review", position=3),
        models.WorkflowStatus(project_id=project.id, name="Done", position=4, is_done=True),
    ]
    db.add_all(statuses)
    db.flush()
    by_name = {status.name: status for status in statuses}
    for from_name, to_name in [
        ("Backlog", "To Do"),
        ("To Do", "In Progress"),
        ("In Progress", "In Review"),
        ("In Review", "Done"),
    ]:
        db.add(
            models.WorkflowTransition(
                project_id=project.id,
                from_status_id=by_name[from_name].id,
                to_status_id=by_name[to_name].id,
            )
        )

    db.add_all(
        [
            models.CustomFieldDefinition(project_id=project.id, name="Customer Impact", field_type="dropdown", options=["low", "medium", "high"]),
            models.CustomFieldDefinition(project_id=project.id, name="Due Date", field_type="date"),
        ]
    )

    sprint_1 = models.Sprint(project_id=project.id, name="Sprint 1", start_date=date(2026, 6, 1), end_date=date(2026, 6, 14), status="active")
    sprint_2 = models.Sprint(project_id=project.id, name="Sprint 2", start_date=date(2026, 6, 15), end_date=date(2026, 6, 28), status="planned")
    db.add_all([sprint_1, sprint_2])
    db.flush()

    def issue(issue_type: str, title: str, status: str, assignee: models.User, story_points: int | None = None, parent_id: str | None = None) -> models.Issue:
        project.issue_counter += 1
        row = models.Issue(
            issue_key=f"{project.key}-{project.issue_counter}",
            project_id=project.id,
            type=issue_type,
            title=title,
            description=f"Seeded demo issue for {title}.",
            status_id=by_name[status].id,
            priority="high" if issue_type == "bug" else "medium",
            assignee_id=assignee.id,
            reporter_id=users[1].id,
            sprint_id=sprint_1.id if status != "Backlog" else None,
            parent_id=parent_id,
            labels=["demo", issue_type],
            story_points=story_points,
        )
        db.add(row)
        db.flush()
        return row

    epic = issue("epic", "Launch TeamSync backend", "In Progress", users[0])
    story_1 = issue("story", "Create issue workflow", "Done", users[0], 5, epic.id)
    story_2 = issue("story", "Complete sprint carry-over", "In Progress", users[2], 8, epic.id)
    task = issue("task", "Write Docker setup", "To Do", users[1], 3, story_2.id)
    bug = issue("bug", "Fix duplicate notifications", "Backlog", users[2], 2)
    sub_task = issue("sub_task", "Document workflow violation", "In Review", users[0], None, story_1.id)

    db.add_all(
        [
            models.Comment(issue_id=story_1.id, author_id=users[1].id, body="Great progress @jane."),
            models.Comment(issue_id=story_2.id, author_id=users[0].id, body="Carry-over path needs review from @maya."),
        ]
    )
    db.add_all(
        [
            models.Watcher(issue_id=story_1.id, user_id=users[0].id),
            models.Watcher(issue_id=story_2.id, user_id=users[1].id),
            models.Notification(user_id=users[0].id, project_id=project.id, issue_id=story_1.id, type="mention", message="Bob mentioned you on TS-2"),
        ]
    )
    for seeded_issue in [epic, story_1, story_2, task, bug, sub_task]:
        db.add(models.ActivityLog(project_id=project.id, issue_id=seeded_issue.id, actor_id=seeded_issue.reporter_id, action="issue_seeded", details={"issue_key": seeded_issue.issue_key}))
    db.add(models.RealtimeEvent(project_id=project.id, issue_id=story_2.id, event_type="sprint_updated", payload={"seed": True}))
    db.commit()
