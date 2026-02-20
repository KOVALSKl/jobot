FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc && \
    rm -rf /var/lib/apt/lists/*

COPY hh-applicant-tool/ ./hh-applicant-tool/
RUN pip install --no-cache-dir ./hh-applicant-tool

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN playwright install --with-deps chromium

COPY bot/ ./bot/
COPY .env* ./

ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "bot"]
