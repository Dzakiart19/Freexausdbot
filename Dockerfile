FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    build-essential \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip setuptools wheel

COPY requirements.txt .
RUN pip install --no-cache-dir \
    --only-binary :all: \
    -r requirements.txt

COPY . .
RUN mkdir -p app/data app/logs

EXPOSE 8080

CMD ["python", "-m", "app.main"]
