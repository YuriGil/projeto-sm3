FROM python:3.12-slim
WORKDIR /app
COPY sm3_r29_1_audience_response.py /app/sm3_r29_1_audience_response.py
ENV PYTHONUNBUFFERED=1
ENV SM3_PROJECT_ROOT=/project
ENV SM3_R29_1_INTERVAL_SECONDS=900
CMD ["python","/app/sm3_r29_1_audience_response.py","--daemon","--interval","900"]
