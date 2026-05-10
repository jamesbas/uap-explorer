FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
# Source CSV (staged by infra/deploy.ps1 from data/source/uap-csv.csv).
# COPY uses a wildcard so the build still succeeds if the file isn't staged
# (e.g. for unit-test images); runtime will then look in blob/elsewhere.
COPY data ./data

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
