FROM python:3.12-slim

# Chromium ve Xvfb icin gerekli paketler
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    xvfb \
    fonts-liberation \
    libnss3 \
    libatk-bridge2.0-0 \
    libdrm2 \
    libxkbcommon0 \
    libgbm1 \
    libasound2 \
    libxshmfence1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1
ENV HEADLESS=1
ENV DISPLAY=:99
ENV CHROME_BIN=/usr/bin/chromium

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT:-8001}/health')" || exit 1

# Xvfb baslatip bot'u calistir
CMD Xvfb :99 -screen 0 1920x1080x24 & sleep 1 && python -m bot.runner
