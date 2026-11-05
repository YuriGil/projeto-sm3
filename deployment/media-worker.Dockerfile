FROM python:3.12-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY worker/requirements-worker.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY worker/worker_service.py /app/worker_service.py
COPY worker/SM3_platform_temporal_validity_v1_r2.py /app/SM3_platform_temporal_validity_v1_r2.py

ENV MEDIA_ROOT=/data/media
EXPOSE 8090

CMD ["uvicorn", "worker_service:app", "--host", "0.0.0.0", "--port", "8090"]
