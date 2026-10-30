# Image versi web. Build dari root project (butuh package handover_bot):
#   docker build -f web/Dockerfile -t handover-web .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Jakarta \
    WEB_HOST=0.0.0.0 \
    WEB_PORT=8080

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY handover_bot ./handover_bot
COPY web/handover_web ./handover_web

RUN useradd --create-home web && mkdir -p /app/secrets /app/data && chown -R web /app
USER web

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"WEB_PORT\",\"8080\")}/healthz', timeout=4)"

CMD ["python", "-m", "handover_web"]
