FROM python:3.12-slim
WORKDIR /app
COPY sm3_r30_2_capture_server.py /app/sm3_r30_2_capture_server.py
ENV PYTHONUNBUFFERED=1
ENV SM3_PROJECT_ROOT=/project
ENV SM3_R30_2_PORT=8099
CMD ["python","/app/sm3_r30_2_capture_server.py"]
