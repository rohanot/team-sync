# Stage 1: Build the frontend static assets
FROM node:20-slim AS frontend-builder
WORKDIR /web
COPY web/package*.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# Stage 2: Final python server runtime
FROM python:3.12-slim
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY pyproject.toml ./
RUN pip install --no-cache-dir ".[dev]"

# Copy backend app source code
COPY app ./app

# Copy the compiled frontend static files from the builder stage
COPY --from=frontend-builder /app/static ./app/static

COPY alembic ./alembic
COPY alembic.ini run.py ./

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && python run.py"]
