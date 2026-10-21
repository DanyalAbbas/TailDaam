FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    PORT=7860

WORKDIR /app

COPY requirements.txt pyproject.toml main.py ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY frontend ./frontend
COPY data/gold ./data/gold
COPY data/manifest.csv ./data/manifest.csv
COPY artifacts ./artifacts
COPY models ./models
COPY prefect_runs.csv ./prefect_runs.csv

EXPOSE 7860
CMD ["uvicorn", "rag.api:app", "--host", "0.0.0.0", "--port", "7860", "--app-dir", "src"]
