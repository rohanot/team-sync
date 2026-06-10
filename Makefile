.PHONY: install test run migrate seed docker-up docker-down

install:
	python -m pip install -e ".[dev]"

test:
	pytest -q

run:
	python run.py

migrate:
	alembic upgrade head

seed:
	python -c "from app.database import SessionLocal, init_db; from app.seed import seed_demo_data; init_db(); db=SessionLocal(); seed_demo_data(db); db.close()"

docker-up:
	docker compose up --build

docker-down:
	docker compose down
