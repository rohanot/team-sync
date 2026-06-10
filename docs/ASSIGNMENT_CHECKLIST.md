# TeamSync Assignment Checklist

This checklist is extracted from the provided SDE-1 Backend Engineer take-home assignment text. Treat it as the implementation source of truth. The repo-local skills reinforce the same order: extract requirements, cut scope honestly, design architecture/schema/API, implement original TeamSync modules, then polish README/demo and integrity notes.

## Integrity Boundary

- `jira_clone_master` may be used only as a read-only concept reference for Jira-like vocabulary.
- Do not copy code, comments, tests, migrations, names, file structure, or documentation from `jira_clone_master`.
- Prefer assignment terminology when any reference material differs.
- README should state any public Jira-like systems were reviewed only for domain modeling inspiration, if that review happens.

## Explicit Functional Requirements

### Data Model

- Projects.
- Users.
- Issues with types: Epic, Story, Task, Bug, Sub-task.
- Sprints with date ranges.
- Comments, including threaded comments.
- Activity log with a full audit trail for every issue mutation.
- Parent-child hierarchy: Epic -> Story -> Sub-task.
- Custom fields per project with supported types: text, number, dropdown, date.
- Watchers/subscriptions for issue updates.
- Notifications for assignment, mentions, and status changes.

### Workflow Engine

- Configurable status columns per project.
- Data-driven allowed transitions between statuses.
- Business-rule validation for invalid transitions.
- Invalid workflow operation should return HTTP 422 and include allowed transitions.
- Automatic transition actions, including assigning or notifying a reviewer when an issue moves to In Review.
- Validation hooks, including missing required fields.

### Issue Tracking APIs

- `POST /api/projects/:id/issues`
- `GET /api/projects/:id/board`
- `PATCH /api/issues/:id`
- `POST /api/issues/:id/transitions`
- CRUD behavior for core issue fields, hierarchy, assignment, priority, sprint, and custom fields.
- Concurrent issue updates must be handled safely, preferably with optimistic locking through an `issue.version` field.

### Sprint Management

- CRUD sprints with date ranges.
- `GET /api/projects/:id/sprints`
- `POST /api/sprints/:id/start`
- `POST /api/sprints/:id/complete`
- Move issues between backlog and active sprint.
- Sprint completion must surface completed items, incomplete items, selective carry-over, and velocity.

### Collaboration

- `GET /api/issues/:id/comments`
- `POST /api/issues/:id/comments`
- CRUD threaded comments.
- `@mentions` in comments.
- `GET /api/projects/:id/activity`
- Paginated, filterable activity feed per project.
- Notifications for assignments, mentions, and status changes.
- Watcher subscribe/unsubscribe.

### Realtime

- WebSocket board changes.
- Required event types: `issue_created`, `issue_updated`, `issue_moved`, `comment_added`, `sprint_updated`.
- Presence tracking.
- Reconnection and missed event replay.
- Durable project event log is the simplest defensible way to replay missed events by `last_event_id`.

### Search

- `GET /api/search?q=`
- Full-text search over issue titles, descriptions, and comments.
- Structured query filters for status, assignee, and priority.
- Cursor pagination.
- Indexing strategy documented for evaluator review.

### Scale And Throughput

- Target: high throughput for 500+ concurrent users per workspace.
- Use relational constraints and indexed queries for the primary path.
- Keep WebSocket fanout simple for MVP, but document production scaling path with Redis/pub-sub or broker-backed fanout.
- Avoid paid services or external dependencies for local assignment evaluation unless explicitly requested later.

## Deliverables

- GitHub repository.
- README with architecture, setup, API docs, trade-offs, and demo flow.
- Docker Compose.
- Hosted demo URL.
- Functional endpoints.
- Migrations and seed data.
- Swagger/OpenAPI docs.
- Design docs.
- ERD.
- Trade-off documentation.
- Submission package: repo link, hosted URL, video walkthrough.

## Required Scenarios To Demonstrate

- Concurrent issue updates.
  - Expected behavior: stale update is rejected or forced through an explicit conflict path.
  - Recommended response: HTTP 409 for version conflict.
- Sprint completion with carry-over.
  - Expected behavior: completed, incomplete, selected carried-over issues, and velocity are returned deterministically.
- Workflow violation.
  - Expected behavior: HTTP 422 with the allowed transitions listed.

## Recommended 6-Hour MVP Scope

### Must Have

- FastAPI app with clean module boundaries.
- PostgreSQL-backed SQLAlchemy models and Alembic migrations.
- Projects, users, issues, sprints, workflow statuses/transitions, comments, activity logs, notifications, watchers, custom fields, realtime events.
- Core endpoints listed in the assignment.
- Workflow transition validation and activity logging.
- Sprint start/complete behavior with carry-over summary and velocity.
- Threaded comments with mention notification.
- Project activity feed with cursor pagination.
- Search endpoint with practical PostgreSQL search and filters.
- WebSocket endpoint for project board events, persisted event replay, and Redis-backed presence with in-memory fallback.
- Docker Compose for API and PostgreSQL.
- Swagger/OpenAPI exposed by FastAPI.
- README with setup, API walkthrough, ERD, scenarios, limitations, and integrity note.

### Simplified But Defensible

- Search can use PostgreSQL `ILIKE` and joins first, with README notes for `tsvector`/GIN production indexing.
- Presence can be in-memory for local demo, with README notes for multi-instance production.
- Notifications can be persisted in database instead of sent through email/push services.
- Custom fields can be validated by project-level definitions and stored as JSON values on issues.
- Required-field validation hooks can focus on workflow transition rules and custom-field required flags.
- Hosted demo may be documented as pending if deployment is not completed by another agent.

### Future Work To Document

- Redis-backed WebSocket fanout when `REDIS_URL` is configured, with persisted database replay for reconnects.
- Dedicated full-text search service or advanced PostgreSQL ranking.
- Fine-grained permissions and workspace roles.
- Background jobs for notification delivery.
- Rate limiting and API gateway hardening.
- Advanced sprint reporting beyond velocity.

## API Coverage Notes For README

README should include a table with these columns: Area, Endpoint, Status, Demo command, Notes.

Required endpoint rows:

- Projects/issues: `POST /api/projects/{project_id}/issues`
- Board: `GET /api/projects/{project_id}/board`
- Issue update: `PATCH /api/issues/{issue_id}`
- Workflow transition: `POST /api/issues/{issue_id}/transitions`
- Sprint list: `GET /api/projects/{project_id}/sprints`
- Sprint start: `POST /api/sprints/{sprint_id}/start`
- Sprint complete: `POST /api/sprints/{sprint_id}/complete`
- Comments: `GET /api/issues/{issue_id}/comments`
- Comments: `POST /api/issues/{issue_id}/comments`
- Activity: `GET /api/projects/{project_id}/activity`
- Search: `GET /api/search?q=...`
- Realtime: `WS /ws/projects/{project_id}?last_event_id=...`

## README Coverage Checklist

- Project purpose: original local-first Jira-like backend named TeamSync.
- Quick start: Docker Compose commands, migration command, seed command, API URL, Swagger URL.
- Architecture: FastAPI routes, services, repositories, SQLAlchemy models, PostgreSQL, WebSockets.
- ERD: readable relationship diagram or Mermaid ERD.
- API docs: endpoint table and Swagger/OpenAPI link.
- Demo script: create issue, view board, invalid transition, valid transition, add comment with mention, complete sprint, search, WebSocket replay.
- Assignment mapping: requirement-to-implementation table.
- Testing: exact pytest command and what it covers.
- Scale notes: indexes, optimistic locking, cursor pagination, WebSocket fanout path.
- Trade-offs: simplified local notifications, lightweight Redis coordination with in-memory fallback, practical search, hosted demo status.
- Integrity note: no copied code from `jira_clone_master`.

## Ambiguities To Resolve During Implementation

- Exact definition of sprint velocity: use completed story points by default and document it.
- Whether bugs/tasks require story points on Done: local workflow skill suggests story/task; assignment only says validation hooks. Document chosen rule.
- Hosted demo target and budget constraints are not specified in the prompt.
- Authentication/authorization is not explicitly required; seed users and explicit `actor_id` request fields are acceptable for a backend-focused MVP if documented.
- Notification delivery channel is not specified; database notifications are acceptable for MVP.

## Acceptance Checklist

- [x] Assignment checklist exists and is kept current.
- [x] Architecture doc explains modules, data flow, transactions, realtime, search, and trade-offs.
- [x] Schema supports all required entities and relationships.
- [x] Migrations create the schema cleanly.
- [x] Seed data supports evaluator demo flow.
- [x] Required REST endpoints are functional.
- [x] Workflow violation returns 422 with allowed transitions.
- [x] Issue update conflict path is implemented and test-covered.
- [x] Sprint completion returns completed, incomplete, carry-over, and velocity.
- [x] Comments support threading and mentions.
- [x] Activity feed is paginated and filterable by action, issue, and actor.
- [x] Search supports text and structured filters with cursor pagination.
- [x] WebSocket supports required persisted event types and missed-event replay.
- [x] Docker Compose config validates and is ready to start PostgreSQL and API.
- [x] Swagger/OpenAPI is available through FastAPI at `/docs`.
- [x] README covers setup, architecture, ERD, API, scenarios, trade-offs, and demo flow.
- [x] Tests pass.
- [x] Integrity guardrails exclude `.env`, the reference repo, and the assignment PDF from commits.
