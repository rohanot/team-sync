---
name: "teamsync-assignment-supervisor"
description: "Supervisor guidance for the TeamSync SDE-1 backend take-home assignment. Use when orchestrating assignment extraction, scope planning, architecture, implementation, testing, Docker packaging, README polish, or integrity review for the Team-Sync workspace."
---

# TeamSync Assignment Supervisor

## Mission

Build an original TeamSync backend from the assignment PDF as the source of truth. The target stack is FastAPI, PostgreSQL, SQLAlchemy, Alembic, WebSockets, Docker, and pytest.

## Execution Order

1. Run `assignment-extractor` to turn the PDF into an evaluation checklist.
2. Run `brainstorm-scope-cutter` to define a 6-hour MVP and defer nonessential work.
3. Run `reference-repo-mapper` only for domain vocabulary, never for implementation.
4. Run `architecture-planner`, then `db-schema-designer`, then `api-contract-designer`.
5. Implement by module: backend foundation, workflow, sprint, collaboration, realtime, search.
6. Run `test-writer` after completing each full module, not after every tiny file edit.
7. Finish with `docker-deployment`, `readme-demo-polisher`, `code-review-hardener`, and `plagiarism-integrity-checker`.

## Integrity Constraints

- Treat `jira_clone_master` as read-only architecture reference.
- Do not copy code, comments, file structure, names, migrations, tests, or documentation from `jira_clone_master`.
- Use the PDF assignment as the final authority when reference material disagrees.
- Keep TeamSync original, self-contained, and honest about trade-offs.

## Development Model

Act as a supervisor agent coordinating specialized agents. Each skill should produce a concrete artifact or checklist that the next skill can consume. Prefer small, complete modules with clear verification over scattered partial work.

## Definition Of Done

- Assignment requirements are traceable to implementation, tests, and README notes.
- Backend starts locally on port 8000.
- Docker Compose starts PostgreSQL and the API.
- Swagger/OpenAPI is clean enough for evaluators.
- README explains setup, architecture, ERD, APIs, trade-offs, and demo flow.
- Integrity check confirms no copied reference-repo code or fork traces.
