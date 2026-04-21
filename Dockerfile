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
    unzip \
    fonts-liberation \
    fonts-unifont \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libxtst6 \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# Install Google Chrome for Selenium
RUN wget -q -O /tmp/chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && apt-get update \
    && apt-get install -y /tmp/chrome.deb \
    && rm /tmp/chrome.deb \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./requirements.txt
COPY worker/requirements.txt ./worker-requirements.txt
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt -r worker-requirements.txt

# Install Playwright's Chromium for the worker
RUN playwright install chromium

COPY . /app

RUN chmod +x /app/start.sh

CMD ["/app/start.sh"]
