FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /srv/kisanos
RUN apt-get update && apt-get install -y --no-install-recommends libjpeg62-turbo zlib1g && rm -rf /var/lib/apt/lists/*
COPY requirements.txt ./requirements.txt
RUN pip install --upgrade pip && pip install -r requirements.txt
COPY app ./app
COPY models ./models
RUN useradd --create-home --uid 10001 appuser && mkdir -p /var/lib/kisanos/images ./data && chown -R appuser:appuser /var/lib/kisanos ./data
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health/ready', timeout=2)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
