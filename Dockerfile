# ══════════════════════════════════════════════════════════════════════
#  Dockerfile — BorsaSinyal Pro Terminal v3.2
#  Çok aşamalı build: daha küçük imaj, daha hızlı deployment
# ══════════════════════════════════════════════════════════════════════

# ── AŞAMA 1: Bağımlılık yükleme (derleme) ──
FROM python:3.12-slim AS builder

WORKDIR /app

# Sistem bağımlılıkları
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ curl \
    && rm -rf /var/lib/apt/lists/*

# Gereksinimleri kopyala ve yükle
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ── AŞAMA 2: Çalışma imajı ──
FROM python:3.12-slim

WORKDIR /app

# Sadece gerekli sistem paketleri
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python paketlerini builder'dan kopyala
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Uygulama dosyalarını kopyala
COPY . .

# Çalışma dizinleri
RUN mkdir -p logs modeller

# Ortam değişkenleri
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# Portlar
# 8501: Streamlit UI
# 8502: REST API
EXPOSE 8501 8502

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# Varsayılan komut: Streamlit UI
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]