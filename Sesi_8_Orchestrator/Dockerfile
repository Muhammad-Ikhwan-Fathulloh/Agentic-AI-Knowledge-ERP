# Gunakan base image Python yang ringan
FROM python:3.11-slim

# Set environment variables untuk Python (mencegah pyc file & unbuffered stdout)
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Tentukan working directory di dalam container
WORKDIR /app

# Install system dependencies (untuk build DuckDB atau ekstensi lainnya jika dibutuhkan)
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Salin file requirements.txt
COPY requirements.txt .

# Install dependencies python
RUN pip install --no-cache-dir -r requirements.txt

# Salin seluruh kode aplikasi Sesi 8 ke dalam container
COPY . .

# Expose port untuk Sesi 8
EXPOSE 8000

# Perintah default ketika container berjalan
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
