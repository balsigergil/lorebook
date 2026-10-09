#!/bin/sh
# Entry point of the Docker image.
#   web     ASGI server (Granian); applies the migrations first
#   worker  background tasks (Django Tasks, PostgreSQL queue)
#   other   any command, e.g. `python manage.py createsuperuser`
set -e

case "$1" in
  web)
    if [ "${LOREBOOK_MIGRATE:-true}" = "true" ]; then
      python manage.py migrate --noinput
    fi
    # Granian serves the collected static files itself, before Django.
    exec granian --interface asginl \
      --host 0.0.0.0 --port "${PORT:-8000}" \
      --workers "${WEB_WORKERS:-2}" \
      --respawn-failed-workers \
      --static-path-route /static \
      --static-path-mount /app/static \
      lorebook.asgi:application
    ;;
  worker)
    # Wait until the web container has applied the migrations.
    until python manage.py migrate --check >/dev/null 2>&1; do
      echo "Waiting for the database migrations…"
      sleep 3
    done
    exec python manage.py db_worker --queue-name '*' --no-reload
    ;;
  *)
    exec "$@"
    ;;
esac
