# syntax=docker/dockerfile:1
FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.32 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/app/.venv/bin:$PATH"

RUN apt-get update \
    && apt-get install -y --no-install-recommends gettext rclone \
        libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencies first for layer caching.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Plugins: extra pip packages (names, URLs or paths) installed into the app's
# environment. Enable them at run time with SCR_PLUGINS. See docs/plugins.md.
ARG SCR_PLUGIN_PACKAGES=""
RUN --mount=type=cache,target=/root/.cache/uv \
    if [ -n "$SCR_PLUGIN_PACKAGES" ]; then \
        uv pip install --python /app/.venv/bin/python $SCR_PLUGIN_PACKAGES; \
    fi

# Dummy key is used only for these build steps and is not kept in the image env.
ARG SCR_BUILD_SECRET_KEY=build-only-not-a-secret
RUN SCR_SECRET_KEY="$SCR_BUILD_SECRET_KEY" python manage.py compilemessages --ignore=.venv \
    && SCR_SECRET_KEY="$SCR_BUILD_SECRET_KEY" python manage.py collectstatic --noinput

RUN useradd --system --uid 10001 --home-dir /app app \
    && mkdir -p /data \
    && chown app:app /data \
    && chmod +x docker/entrypoint.sh
ENV SCR_DATA_DIR=/data
VOLUME /data

USER app
EXPOSE 8000
ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["web"]
