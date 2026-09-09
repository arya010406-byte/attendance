FROM python:3.10-slim

# Install C++ compilation tools required by dlib/face_recognition
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    libopenblas-dev \
    liblapack-dev \
    libx11-dev \
    && rm -rf /var/lib/apt-get/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Expose port and start Gunicorn
EXPOSE 10000
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:10000"]