from __future__ import annotations

from datetime import date

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app import models, routes, schemas, services


def seeded_context(client: TestClient) -> tuple[dict, list[dict], dict]:
    project = client.get("/api/projects").json()[0]
    users = client.get("/api/users").json()
    board = client.get(f"/api/projects/{project['id']}/board").json()
    return project, users, board


def find_issue(board: dict, *, issue_type: str | None = None, status: str | None = None) -> dict:
    for column in board["columns"]:
        if status and column["status"]["name"] != status:
            continue
        for issue in column["issues"]:
            if issue_type is None or issue["type"] == issue_type:
                return issue
    raise AssertionError(f"issue not found: type={issue_type} status={status}")


def user_by_name(users: list[dict], username: str) -> dict:
    for user in users:
        if user["username"] == username:
            return user
    raise AssertionError(f"user not found: {username}")


def test_stale_sessions_allocate_distinct_issue_keys(client: TestClient) -> None:
    project, users, _ = seeded_context(client)

    from app.database import SessionLocal

    first = SessionLocal()
    second = SessionLocal()
    try:
        services.get_project(first, project["id"])
        services.get_project(second, project["id"])

        first_issue = services.create_issue(
            first,
            project["id"],
            schemas.IssueCreate(type="task", title="First concurrent issue", reporter_id=users[0]["id"]),
            users[0]["id"],
        )
        second_issue = services.create_issue(
            second,
            project["id"],
            schemas.IssueCreate(type="task", title="Second concurrent issue", reporter_id=users[0]["id"]),
            users[0]["id"],
        )
    finally:
        first.close()
        second.close()

    assert first_issue.issue_key != second_issue.issue_key
    assert {first_issue.issue_key, second_issue.issue_key} == {"TS-7", "TS-8"}


def test_stale_session_update_hits_atomic_version_conflict(client: TestClient) -> None:
    _, users, board = seeded_context(client)
    issue = find_issue(board, issue_type="story", status="In Progress")

    from app.database import SessionLocal

    first = SessionLocal()
    second = SessionLocal()
    try:
        services.get_issue(first, issue["id"])
        services.get_issue(second, issue["id"])

        updated = services.update_issue(
            first,
            issue["id"],
            schemas.IssueUpdate(expected_version=issue["version"], title="Fresh winning title"),
            users[0]["id"],
        )
        assert updated.version == issue["version"] + 1

        with pytest.raises(HTTPException) as conflict:
            services.update_issue(
                second,
                issue["id"],
                schemas.IssueUpdate(expected_version=issue["version"], title="Stale losing title"),
                users[1]["id"],
            )
    finally:
        first.close()
        second.close()

    assert conflict.value.status_code == 409
    assert conflict.value.detail["code"] == "version_conflict"


def test_sprint_dates_and_cross_project_carry_over_are_rejected(client: TestClient) -> None:
    project, users, _ = seeded_context(client)
    admin = user_by_name(users, "jane")

    invalid_dates = client.post(
        f"/api/projects/{project['id']}/sprints?user_id={admin['id']}",
        json={"name": "Backwards sprint", "start_date": "2026-07-15", "end_date": "2026-07-01"},
    )
    assert invalid_dates.status_code == 422
    assert invalid_dates.json()["detail"]["code"] == "invalid_sprint_dates"

    from app.database import SessionLocal

    db = SessionLocal()
    try:
        other_project = models.Project(key="OPS", name="Other Project")
        db.add(other_project)
        db.flush()
        other_sprint = models.Sprint(
            project_id=other_project.id,
            name="Other Sprint",
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 14),
            status="planned",
        )
        db.add(other_sprint)
        db.commit()
        other_sprint_id = other_sprint.id
    finally:
        db.close()

    sprint = client.get(f"/api/projects/{project['id']}/sprints").json()[0]
    invalid_carry = client.post(
        f"/api/sprints/{sprint['id']}/complete?user_id={admin['id']}",
        json={"next_sprint_id": other_sprint_id},
    )
    assert invalid_carry.status_code == 422
    assert invalid_carry.json()["detail"]["code"] == "invalid_next_sprint"


def test_custom_field_values_match_definition_types(client: TestClient) -> None:
    project, users, _ = seeded_context(client)

    invalid_dropdown = client.post(
        f"/api/projects/{project['id']}/issues?user_id={users[0]['id']}",
        json={"type": "task", "title": "Bad dropdown", "custom_fields": {"Customer Impact": "urgent"}},
    )
    assert invalid_dropdown.status_code == 422
    assert invalid_dropdown.json()["detail"]["code"] == "invalid_custom_field_value"

    invalid_date = client.post(
        f"/api/projects/{project['id']}/issues?user_id={users[0]['id']}",
        json={"type": "task", "title": "Bad date", "custom_fields": {"Due Date": "soon"}},
    )
    assert invalid_date.status_code == 422
    assert invalid_date.json()["detail"]["code"] == "invalid_custom_field_value"


def test_activity_cursor_is_stable_with_descending_order(client: TestClient) -> None:
    project, users, _ = seeded_context(client)
    for index in range(3):
        response = client.post(
            f"/api/projects/{project['id']}/issues?user_id={users[0]['id']}",
            json={"type": "task", "title": f"Cursor issue {index}", "reporter_id": users[0]["id"]},
        )
        assert response.status_code == 201

    first_page = client.get(f"/api/projects/{project['id']}/activity?limit=2").json()
    assert len(first_page) == 2
    cursor = f"{first_page[-1]['created_at']}|{first_page[-1]['id']}"

    second_page = client.get(f"/api/projects/{project['id']}/activity?limit=2&cursor={cursor}").json()
    assert len(second_page) == 2
    assert {row["id"] for row in first_page}.isdisjoint({row["id"] for row in second_page})


def test_broadcast_uses_exact_event_created_by_service(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    project, users, _ = seeded_context(client)
    sent: list[dict] = []
    original_create_issue = services.create_issue

    async def fake_broadcast(project_id: str, payload: dict) -> None:
        sent.append(payload)

    def noisy_create_issue(*args, **kwargs):
        issue = original_create_issue(*args, **kwargs)
        db = args[0]
        db.add(
            models.RealtimeEvent(
                project_id=issue.project_id,
                issue_id=None,
                event_type="interloper",
                payload={"after": issue.issue_key},
            )
        )
        db.commit()
        return issue

    monkeypatch.setattr(routes.manager, "broadcast", fake_broadcast)
    monkeypatch.setattr(services, "create_issue", noisy_create_issue)

    response = client.post(
        f"/api/projects/{project['id']}/issues?user_id={users[0]['id']}",
        json={"type": "task", "title": "Broadcast exact event", "reporter_id": users[0]["id"]},
    )

    assert response.status_code == 201
    assert sent
    assert sent[-1]["type"] == "issue_created"
    assert sent[-1]["payload"]["issue_key"] == response.json()["issue_key"]
