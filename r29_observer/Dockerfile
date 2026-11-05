FROM python:3.12-slim
WORKDIR /app
COPY sm3_r29_social_observer.py /app/sm3_r29_social_observer.py
ENV PYTHONUNBUFFERED=1
ENV SM3_PROJECT_ROOT=/project
ENV SM3_WORKER_BASE_URL=http://media-worker:8090
ENV SM3_R29_INTERVAL_SECONDS=900
CMD ["python","/app/sm3_r29_social_observer.py","--daemon","--interval","900"]
