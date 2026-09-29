FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DENO_INSTALL=/usr/local \
    DENO_DIR=/tmp/deno

WORKDIR /app
ARG DENO_VERSION=2.9.7
RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates curl ffmpeg unzip \
    && rm -rf /var/lib/apt/lists/* \
    && curl -fsSL https://deno.land/install.sh -o /tmp/deno-install.sh \
    && sh /tmp/deno-install.sh "v${DENO_VERSION}" \
    && rm /tmp/deno-install.sh \
    && deno --version
COPY pyproject.toml ./
COPY app ./app
COPY alembic.ini ./
COPY migrations ./migrations
RUN python -m pip install --upgrade pip && python -m pip install --upgrade --no-cache-dir .
RUN python -c "from importlib.metadata import version; print('yt-dlp', version('yt-dlp')); print('yt-dlp-ejs', version('yt-dlp-ejs'))" \
    && command -v deno \
    && command -v ffmpeg

RUN useradd --create-home --uid 10001 appuser
RUN mkdir -p /var/lib/sunlena/media && chown -R appuser:appuser /var/lib/sunlena
USER 10001:10001

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
