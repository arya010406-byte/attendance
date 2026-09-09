FROM python:3.10-slim

# Install system compilation headers
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    libopenblas-dev \
    liblapack-dev \
    libx11-dev \
    && rm -rf /var/lib/apt-get/lists/*

WORKDIR /app

# Upgrade pip and install dlib binary first to skip CMake memory spikes
RUN pip install --no-cache-dir --upgrade pip setuptools wheel
RUN pip install --no-cache-dir dlib-bin

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 10000

CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:10000"]