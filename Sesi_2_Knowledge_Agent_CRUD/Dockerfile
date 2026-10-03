# ── Build Stage ─────────────────────────────────────────────────────────────
FROM opensuse/tumbleweed:latest AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

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

WORKDIR /app

COPY requirements.txt .
RUN python3.11 -m pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Final Stage ──────────────────────────────────────────────────────────────
FROM opensuse/tumbleweed:latest AS final

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/install/lib/python3.11/site-packages

RUN zypper --non-interactive refresh && \
    zypper --non-interactive install -y \
        python311 \
        && zypper clean --all

COPY --from=builder /install /install

WORKDIR /app

COPY . .

# Expose port Sesi 2
EXPOSE 8002

CMD ["python3.11", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]
