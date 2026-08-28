# The API only. ingest/ never runs here: it needs the workstation's browser
# session, and docs/AUTONOMY.md requires the workstation to accept no inbound
# connection. Two runtimes, two images.

FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir \
      "psycopg[binary]>=3.2" "fastapi>=0.115" "uvicorn[standard]>=0.32"

COPY makanlah/ ./makanlah/
COPY api/ ./api/


ENV PYTHONUNBUFFERED=1
EXPOSE 8080

CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080"]
