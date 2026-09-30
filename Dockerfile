# Manifest Workbench hosted console.
# Mount a persistent volume at /data: it holds the workbook data file, issued PDFs and the session key.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MANIFEST_DATA_DIR=/data \
    MANIFEST_PROXY=1 \
    PORT=8000

COPY pyproject.toml README.md /src/
COPY manifest_workbench /src/manifest_workbench
RUN pip install --no-cache-dir '/src[web,xlsx]' \
    && rm -rf /src \
    && useradd --create-home --uid 10001 manifest \
    && mkdir -p /data && chown manifest /data

USER manifest
WORKDIR /home/manifest
VOLUME ["/data"]
EXPOSE 8000

# One worker process: the JSON data file is guarded by a file lock, and threads keep the app responsive.
# The long timeout covers research pulls that query SEC EDGAR for every tracked security.
CMD gunicorn --bind 0.0.0.0:${PORT} --workers 1 --threads 8 --timeout 300 \
    --access-logfile - 'manifest_workbench.web:create_app()'
