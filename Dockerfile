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

# Dependencies first for layer caching. The bundled plugins in plugins/ are
# workspace members, installed with the app in the next step.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-workspace

COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Plugins: extra pip packages (names, URLs or paths) installed into the app's
# environment. Enable them at run time with METRA_PLUGINS. See docs/plugins.md.
# SCR_PLUGIN_PACKAGES is the name from before the rename to Metra.
ARG METRA_PLUGIN_PACKAGES=""
ARG SCR_PLUGIN_PACKAGES=""
RUN --mount=type=cache,target=/root/.cache/uv \
    packages="${METRA_PLUGIN_PACKAGES:-$SCR_PLUGIN_PACKAGES}"; \
    if [ -n "$packages" ]; then \
        uv pip install --python /app/.venv/bin/python $packages; \
    fi

# Dummy key is used only for these build steps and is not kept in the image env.
ARG METRA_BUILD_SECRET_KEY=build-only-not-a-secret
RUN METRA_SECRET_KEY="$METRA_BUILD_SECRET_KEY" python manage.py compilemessages --ignore=.venv \
    && METRA_SECRET_KEY="$METRA_BUILD_SECRET_KEY" python manage.py collectstatic --noinput

RUN useradd --system --uid 10001 --home-dir /app app \
    && mkdir -p /data \
    && chown app:app /data \
    && chmod +x docker/entrypoint.sh
ENV METRA_DATA_DIR=/data
VOLUME /data

USER app
EXPOSE 8000
ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["web"]
