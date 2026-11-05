FROM python:3.12-slim
WORKDIR /app
COPY sm3_r30_preedit_bridge.py /app/sm3_r30_preedit_bridge.py
ENV PYTHONUNBUFFERED=1
ENV SM3_PROJECT_ROOT=/project
ENV SM3_R30_INTERVAL_SECONDS=900
CMD ["python","/app/sm3_r30_preedit_bridge.py","--daemon","--interval","900"]
