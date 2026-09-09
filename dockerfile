FROM python:3.10-slim

# Install C++ build tools and system headers
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    libopenblas-dev \
    liblapack-dev \
    libx11-dev \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt-get/lists/*

WORKDIR /app

# Force single-threaded compilation to save memory
ENV MAKEFLAGS="-j1"

# Upgrade build tools
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Install pre-built wheel package first
RUN pip install --no-cache-dir dlib-bin

COPY requirements.txt .
# Install face_recognition without allowing it to rebuild dlib from source
RUN pip install --no-cache-dir --no-deps face_recognition face_recognition_models
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 10000

CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:10000", "--workers", "1", "--threads", "2", "--timeout", "120"]