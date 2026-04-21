FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    curl \
    wget \
    gnupg \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt worker/requirements.txt ./
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt -r worker/requirements.txt

RUN apt-get update && \
    playwright install --with-deps chromium && \
    rm -rf /var/lib/apt/lists/*

COPY . /app

RUN chmod +x /app/start.sh

CMD ["/app/start.sh"]
