FROM deployment-media-worker

COPY worker_service.py /app/worker_service.py
COPY SM3_platform_temporal_validity_v1_r2.py /app/SM3_platform_temporal_validity_v1_r2.py

RUN python -m py_compile /app/worker_service.py /app/SM3_platform_temporal_validity_v1_r2.py
