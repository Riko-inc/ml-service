FROM python:3.10-slim

RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    netcat-openbsd \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

COPY alembic.ini .
COPY alembic ./alembic

RUN chmod +x entrypoint.sh

ENV PYTHONPATH=/app
ENV PORT=8080

EXPOSE $PORT

ENTRYPOINT ["./entrypoint.sh"]