FROM python:3.12-slim
WORKDIR /app
COPY sm3_r26_acquisition.py /app/sm3_r26_acquisition.py
ENV PYTHONUNBUFFERED=1
ENV SM3_PROJECT_ROOT=/project
ENV SM3_R26_PORT=8093
ENV SM3_R25_URL=http://sm3-r25-relay:8092/ingest
EXPOSE 8093
CMD ["python","/app/sm3_r26_acquisition.py"]
