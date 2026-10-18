#!/bin/sh
set -e

role="${1:-web}"

case "$role" in
  web)
    python manage.py migrate --noinput
    exec gunicorn config.wsgi:application \
      --bind 0.0.0.0:8000 \
      --workers "${GUNICORN_WORKERS:-3}" \
      --access-logfile - \
      --logger-class config.gunicorn_logging.RedactingLogger
    ;;
  worker)
    exec python manage.py run_huey
    ;;
  *)
    exec "$@"
    ;;
esac
