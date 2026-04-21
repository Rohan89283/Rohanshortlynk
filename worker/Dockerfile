FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY worker/requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

RUN apt-get update && \
    playwright install --with-deps chromium && \
    rm -rf /var/lib/apt/lists/*

COPY worker/ /app/worker/

CMD ["uvicorn", "worker.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
