FROM animaketh/dlib-python:latest

WORKDIR /app

# Copy requirements and install remaining python modules
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

EXPOSE 10000

CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:10000"]