# CSC418 DevOps Lab Midterm - FA23-BDS-004
# Trains the model at image-build time so every build ships a fresh model.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependencies first so Docker caches this layer across data-only pushes.
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir --timeout 180 --retries 10 -r requirements.txt -r requirements-dev.txt

# Application code and the student-specific configuration.
COPY config.json train.py app.py ./
COPY tests/ ./tests/

# Dataset copied last: a grader data push invalidates only the layers below.
COPY dataset/ ./dataset/

# Commit that produced this image, surfaced by GET /metrics as git_sha.
ARG GIT_COMMIT=local
ENV GIT_COMMIT=${GIT_COMMIT}

# Retrain on every build; fails the build if the data is unusable.
RUN python train.py && cat artifacts/metrics.json

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=5 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status==200 else 1)"

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
