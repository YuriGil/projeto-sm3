FROM python:3.12-slim
WORKDIR /app
COPY sm3_r21_orchestrator.py /app/sm3_r21_orchestrator.py
ENV PYTHONUNBUFFERED=1
ENV SM3_PROJECT_ROOT=/project
ENV SM3_R21_PORT=8091
EXPOSE 8091
CMD ["python","/app/sm3_r21_orchestrator.py"]
