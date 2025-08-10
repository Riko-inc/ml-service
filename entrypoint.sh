#!/bin/bash
set -e

echo "Waiting for database to become ready..."
while ! nc -z "$DB_HOST" "$DB_PORT"; do
  sleep 1
done
echo "Database is ready."

echo "Applying database migrations..."
alembic upgrade head

echo "Starting application..."
exec uvicorn chat_app.api:app --host 0.0.0.0 --port "$PORT"