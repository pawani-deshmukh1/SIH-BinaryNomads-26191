FROM python:3.11-slim

WORKDIR /app

# System deps for GeoPandas / GDAL / psycopg2
RUN apt-get update && apt-get install -y \
    libgdal-dev gdal-bin libpq-dev gcc g++ \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code copied last so layer cache is reused on code changes
COPY . .

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
