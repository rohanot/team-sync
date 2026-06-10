from fastapi.testclient import TestClient


def seeded_context(client: TestClient) -> tuple[dict, list[dict], dict]:
    project = client.get("/api/projects").json()[0]
    users = client.get("/api/users").json()
    board = client.get(f"/api/projects/{project['id']}/board").json()
    return project, users, board


def user_by_name(users: list[dict], username: str) -> dict:
    for user in users:
        if user["username"] == username:
            return user
    raise AssertionError(f"user not found: {username}")


def find_issue(board: dict, *, issue_type: str | None = None, status: str | None = None) -> dict:
    for column in board["columns"]:
        if status and column["status"]["name"] != status:
            continue
        for issue in column["issues"]:
            if issue_type is None or issue["type"] == issue_type:
                return issue
    raise AssertionError(f"issue not found: type={issue_type} status={status}")


def test_health_and_seed_data(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok", "service": "teamsync"}
    project, users, board = seeded_context(client)
    assert project["key"] == "TS"
    assert len(users) == 3
    assert [column["status"]["name"] for column in board["columns"]] == ["Backlog", "To Do", "In Progress", "In Review", "Done"]
    issue_count = sum(len(column["issues"]) for column in board["columns"])
    assert issue_count == 6


def test_issue_create_update_and_optimistic_locking(client: TestClient) -> None:
    project, users, _ = seeded_context(client)
    response = client.post(
        f"/api/projects/{project['id']}/issues?user_id={users[0]['id']}",
        json={
            "type": "story",
            "title": "Add audit export",
            "description": "Expose project audit history export.",
            "priority": "high",
            "assignee_id": users[1]["id"],
            "reporter_id": users[0]["id"],
            "story_points": 3,
        },
    )
    assert response.status_code == 201
    issue = response.json()
    assert issue["issue_key"].startswith("TS-")
    assert issue["version"] == 1

    patched = client.patch(
        f"/api/issues/{issue['id']}?user_id={users[0]['id']}",
        json={"expected_version": 1, "priority": "medium"},
    )
    assert patched.status_code == 200
    assert patched.json()["version"] == 2

    conflict = client.patch(
        f"/api/issues/{issue['id']}?user_id={users[0]['id']}",
        json={"expected_version": 1, "title": "Stale title"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "version_conflict"


def test_parent_hierarchy_and_custom_fields(client: TestClient) -> None:
    project, users, board = seeded_context(client)
    epic = find_issue(board, issue_type="epic")

    invalid_parent = client.post(
        f"/api/projects/{project['id']}/issues?user_id={users[0]['id']}",
        json={"type": "epic", "title": "Invalid child epic", "parent_id": epic["id"]},
    )
    assert invalid_parent.status_code == 422
    assert invalid_parent.json()["detail"]["code"] == "invalid_parent"

    with_custom_field = client.post(
        f"/api/projects/{project['id']}/issues?user_id={users[0]['id']}",
        json={
            "type": "story",
            "title": "Track customer impact",
            "parent_id": epic["id"],
            "story_points": 2,
            "custom_fields": {"Customer Impact": "high"},
        },
    )
    assert with_custom_field.status_code == 201
    assert with_custom_field.json()["title"] == "Track customer impact"

    unknown_field = client.post(
        f"/api/projects/{project['id']}/issues?user_id={users[0]['id']}",
        json={"type": "task", "title": "Unknown custom field", "custom_fields": {"Not Real": "x"}},
    )
    assert unknown_field.status_code == 422
    assert unknown_field.json()["detail"]["code"] == "unknown_custom_field"


def test_workflow_violation_and_valid_transition(client: TestClient) -> None:
    project, users, board = seeded_context(client)
    todo = find_issue(board, issue_type="task", status="To Do")

    invalid = client.post(
        f"/api/issues/{todo['id']}/transitions?user_id={users[0]['id']}",
        json={"to_status": "Done", "expected_version": todo["version"]},
    )
    assert invalid.status_code == 422
    detail = invalid.json()["detail"]
    assert detail["code"] == "workflow_violation"
    assert detail["current_status"] == "To Do"
    assert detail["requested_status"] == "Done"
    assert detail["allowed_transitions"] == ["Backlog", "In Progress"]

    valid = client.post(
        f"/api/issues/{todo['id']}/transitions?user_id={users[0]['id']}",
        json={"to_status": "In Progress", "expected_version": todo["version"]},
    )
    assert valid.status_code == 200
    assert valid.json()["status"] == "In Progress"
    assert valid.json()["version"] == todo["version"] + 1

    activity = client.get(f"/api/projects/{project['id']}/activity").json()
    assert any(row["action"] == "issue_moved" for row in activity)


def test_backward_transition_is_supported_when_configured(client: TestClient) -> None:
    _, users, board = seeded_context(client)
    issue = find_issue(board, issue_type="sub_task", status="In Review")

    response = client.post(
        f"/api/issues/{issue['id']}/transitions?user_id={users[0]['id']}",
        json={"to_status": "In Progress", "expected_version": issue["version"]},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "In Progress"
    assert response.json()["version"] == issue["version"] + 1


def test_backward_transition_from_done_is_supported_and_advertised(client: TestClient) -> None:
    _, users, board = seeded_context(client)
    issue = find_issue(board, issue_type="story", status="Done")

    invalid = client.post(
        f"/api/issues/{issue['id']}/transitions?user_id={users[0]['id']}",
        json={"to_status": "Backlog", "expected_version": issue["version"]},
    )
    assert invalid.status_code == 422
    detail = invalid.json()["detail"]
    assert detail["code"] == "workflow_violation"
    assert detail["current_status"] == "Done"
    assert detail["requested_status"] == "Backlog"
    assert detail["allowed_transitions"] == ["In Review"]

    response = client.post(
        f"/api/issues/{issue['id']}/transitions?user_id={users[0]['id']}",
        json={"to_status": "In Review", "expected_version": issue["version"]},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "In Review"
    assert response.json()["version"] == issue["version"] + 1


def test_sprint_completion_carry_over_and_velocity(client: TestClient) -> None:
    project, users, board = seeded_context(client)
    admin = user_by_name(users, "jane")
    sprints = client.get(f"/api/projects/{project['id']}/sprints").json()
    sprint_1, sprint_2 = sprints[0], sprints[1]
    incomplete = find_issue(board, issue_type="story", status="In Progress")

    response = client.post(
        f"/api/sprints/{sprint_1['id']}/complete?user_id={admin['id']}",
        json={"carry_over_issue_ids": [incomplete["id"]], "next_sprint_id": sprint_2["id"]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["velocity"] == 5
    assert any(issue["id"] == incomplete["id"] for issue in body["carried_over"])
    assert any(issue["status"] == "Done" for issue in body["completed"])


def test_comments_mentions_watchers_notifications_and_search(client: TestClient) -> None:
    project, users, board = seeded_context(client)
    issue = find_issue(board, issue_type="story", status="In Progress")
    bob = user_by_name(users, "bob")
    jane = user_by_name(users, "jane")
    maya = user_by_name(users, "maya")

    watch = client.post(f"/api/issues/{issue['id']}/watch?user_id={bob['id']}")
    assert watch.status_code == 204

    comment = client.post(
        f"/api/issues/{issue['id']}/comments?user_id={bob['id']}",
        json={"body": "Please review this @jane"},
    )
    assert comment.status_code == 201
    comment_id = comment.json()["id"]
    comments = client.get(f"/api/issues/{issue['id']}/comments").json()
    assert any(row["body"] == "Please review this @jane" for row in comments)

    child = client.post(
        f"/api/issues/{issue['id']}/comments?user_id={jane['id']}",
        json={"body": "Replying in thread", "parent_id": comment_id},
    )
    assert child.status_code == 201
    assert child.json()["parent_id"] == comment_id

    update = client.patch(
        f"/api/comments/{comment_id}?user_id={bob['id']}",
        json={"body": "Please review this again @jane"},
    )
    assert update.status_code == 200
    assert update.json()["body"] == "Please review this again @jane"

    notifications = client.get(f"/api/notifications?user_id={jane['id']}").json()
    assert any(row["type"] == "mention" for row in notifications)

    search = client.get(f"/api/search?q=Carry&project_id={project['id']}&status=In Progress").json()
    assert search["results"]
    assert search["next_cursor"] is None

    activity = client.get(f"/api/projects/{project['id']}/activity?action=comment_updated&issue_id={issue['id']}&actor_id={bob['id']}").json()
    assert len(activity) == 1

    delete = client.delete(f"/api/comments/{comment_id}?user_id={bob['id']}")
    assert delete.status_code == 204


def test_seeded_dev_tokens_and_permissions(client: TestClient) -> None:
    project, users, board = seeded_context(client)
    jane = user_by_name(users, "jane")
    bob = user_by_name(users, "bob")
    maya = user_by_name(users, "maya")
    issue = find_issue(board, issue_type="story", status="In Progress")

    token_response = client.get("/api/session", headers={"X-Dev-Token": "dev-jane"})
    assert token_response.status_code == 200
    assert token_response.json()["user"]["username"] == "jane"
    assert token_response.json()["memberships"][0]["role"] == "admin"

    viewer_update = client.patch(
        f"/api/issues/{issue['id']}",
        headers={"X-Dev-Token": "dev-maya"},
        json={"expected_version": issue["version"], "priority": "low"},
    )
    assert viewer_update.status_code == 403

    member_comment = client.post(
        f"/api/issues/{issue['id']}/comments",
        headers={"X-Dev-Token": "dev-bob"},
        json={"body": "Member can collaborate"},
    )
    assert member_comment.status_code == 201

    legacy_query_param_still_works = client.get(f"/api/notifications?user_id={jane['id']}")
    assert legacy_query_param_still_works.status_code == 200


def test_websocket_replays_events(client: TestClient) -> None:
    project, _, _ = seeded_context(client)
    with client.websocket_connect(f"/ws/projects/{project['id']}?last_event_id=0&user_id=tester") as websocket:
        first = websocket.receive_json()
        second = websocket.receive_json()
    assert first["replay"] is True
    assert second["type"] == "presence"
