FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY code_review_env ./code_review_env
COPY baseline.py ./baseline.py
COPY openenv.yaml ./openenv.yaml

EXPOSE 8000
CMD ["uvicorn", "code_review_env.server.app:app", "--host", "0.0.0.0", "--port", "8000"]
