#!/bin/sh
set -e

echo "Waiting for the database..."
python - <<'PYEOF'
import os
import sys
import time

if os.environ.get("POSTGRES_HOST"):
    import psycopg2

    for attempt in range(30):
        try:
            psycopg2.connect(
                dbname=os.environ.get("POSTGRES_DB", "girlsclub"),
                user=os.environ.get("POSTGRES_USER", "girlsclub"),
                password=os.environ.get("POSTGRES_PASSWORD", ""),
                host=os.environ.get("POSTGRES_HOST"),
                port=os.environ.get("POSTGRES_PORT", "5432"),
            ).close()
            break
        except psycopg2.OperationalError:
            time.sleep(1)
    else:
        print("Database never became available", file=sys.stderr)
        sys.exit(1)
PYEOF

python manage.py migrate --noinput
python manage.py collectstatic --noinput

exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3
