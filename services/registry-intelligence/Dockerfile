FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app

# Bake the trained base entity-resolution model into the image (see
# app/matching/train.py) so the service never starts on the untrained
# fallback heuristic in a fresh deployment.
RUN python -m app.matching.train

EXPOSE 8003
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8003"]
