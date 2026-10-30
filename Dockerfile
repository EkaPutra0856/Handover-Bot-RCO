FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Jakarta

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY handover_bot ./handover_bot

RUN useradd --create-home bot && mkdir -p /app/secrets /app/data && chown -R bot /app
USER bot

CMD ["python", "-m", "handover_bot"]
