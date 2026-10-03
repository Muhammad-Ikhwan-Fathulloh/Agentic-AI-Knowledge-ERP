# ── Build Stage ─────────────────────────────────────────────────────────────
FROM opensuse/tumbleweed:latest AS builder

# Set environment variables untuk Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install Python dan build dependencies
RUN zypper --non-interactive refresh && \
    zypper --non-interactive install -y \
        python311 \
        python311-pip \
        python311-devel \
        gcc \
        gcc-c++ \
        make \
        curl \
        && zypper clean --all

# Tentukan working directory
WORKDIR /app

# Salin dan install dependencies ke prefix lokal
COPY requirements.txt .
RUN python3.11 -m pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Final Stage ──────────────────────────────────────────────────────────────
FROM opensuse/tumbleweed:latest AS final

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/install/lib/python3.11/site-packages

# Install Python runtime saja (tanpa build tools)
RUN zypper --non-interactive refresh && \
    zypper --non-interactive install -y \
        python311 \
        && zypper clean --all

# Salin installed packages dari builder
COPY --from=builder /install /install

WORKDIR /app

# Salin kode aplikasi
COPY . .

# Expose port Sesi 1
EXPOSE 8001

CMD ["python3.11", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
