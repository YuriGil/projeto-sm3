FROM python:3.12-slim
WORKDIR /app
COPY sm3_r25_relay.py /app/sm3_r25_relay.py
ENV PYTHONUNBUFFERED=1
ENV SM3_PROJECT_ROOT=/project
ENV SM3_R25_PORT=8092
EXPOSE 8092
CMD ["python","/app/sm3_r25_relay.py"]
