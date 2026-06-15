FROM python:3.11-slim

# Build deps needed for TgCrypto, aiohttp C extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Railway sets PORT — health server reads it
ENV PORT=5000

CMD ["python", "bot.py"]
