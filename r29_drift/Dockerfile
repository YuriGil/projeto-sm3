FROM python:3.12-slim
WORKDIR /app
COPY sm3_r29_2_drift_detector.py /app/sm3_r29_2_drift_detector.py
ENV PYTHONUNBUFFERED=1
ENV SM3_PROJECT_ROOT=/project
ENV SM3_R29_2_INTERVAL_SECONDS=900
CMD ["python","/app/sm3_r29_2_drift_detector.py","--daemon","--interval","900"]
