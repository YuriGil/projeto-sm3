FROM python:3.12-slim
WORKDIR /app
COPY sm3_r29_3_strategy_feedback_loop.py /app/sm3_r29_3_strategy_feedback_loop.py
ENV PYTHONUNBUFFERED=1
ENV SM3_PROJECT_ROOT=/project
ENV SM3_R29_3_INTERVAL_SECONDS=900
CMD ["python","/app/sm3_r29_3_strategy_feedback_loop.py","--daemon","--interval","900"]
