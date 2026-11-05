FROM python:3.12-slim
WORKDIR /app
COPY sm3_r30_1_editorial_context_injection.py /app/sm3_r30_1_editorial_context_injection.py
ENV PYTHONUNBUFFERED=1
ENV SM3_PROJECT_ROOT=/project
ENV SM3_R30_1_INTERVAL_SECONDS=900
CMD ["python","/app/sm3_r30_1_editorial_context_injection.py","--daemon","--interval","900"]
